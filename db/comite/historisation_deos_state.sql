-- =====================================================================
-- Historisation de deos_state — base dh_comite
-- Etabli le 07/08/2026 (session/2026-08-05-decisions-accordees)
--
-- POURQUOI
-- deos_state est une table cle/valeur : chaque ronde ecrase la valeur de la
-- veille. Seul updated_at survit, et il ne porte que le dernier passage. Il
-- n'existe donc AUCUNE tendance : ni la micro-courbe 15 jours demandee par le
-- handoff (ecrans 6a, 6b et chaque page N1), ni le delta affiche a cote du
-- score global, ni l'historique du domain_score reclame par le Delivery.
--
-- CE QUI N'EST PAS RECUPERABLE
-- Verification faite le 07/08 : aucune table d'historique n'existe, brief->hier
-- est de la prose et non des valeurs, et les 220 fichiers de /workspace/rondes/
-- sont des transcriptions brutes du CLI ou le score n'est extractible que dans
-- 25 fichiers sur 101 — avec des valeurs manifestement fausses (customer-success
-- a 100 alors que son score est "non calculable"). Aucune amorce retrospective
-- n'est donc posee : elle melangerait du faux a du vrai dans la meme courbe.
-- L'historique demarre au 07/08. Premiere courbe de 15 points : 22/08.
--
-- COUT DE L'ATTENTE
-- Chaque jour sans ce dispositif est un point de courbe definitivement perdu.
-- C'est le seul prerequis du contrat de donnees dont le cout augmente avec le
-- temps.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. La table d'historique
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deos_state_history (
    id         bigserial   PRIMARY KEY,
    cle        text        NOT NULL,
    valeur     jsonb       NOT NULL,
    maj_par    text        NOT NULL,
    capture_le timestamptz NOT NULL DEFAULT now(),
    origine    text        NOT NULL DEFAULT 'trigger'
);

COMMENT ON TABLE deos_state_history IS
 'Historique de deos_state. Une ligne par ecriture REELLEMENT modifiante (une reecriture a l''identique n''insere rien). Alimente par trigger ; origine = trigger (capture automatique) ou amorce (valeur du jour posee a la mise en service). Ne contient aucune reconstruction retrospective : le passe anterieur au 07/08/2026 n''etait pas recuperable de facon fiable.';

CREATE INDEX IF NOT EXISTS ix_deos_state_history_cle_date
    ON deos_state_history (cle, capture_le DESC);

-- ---------------------------------------------------------------------
-- 2. Le trigger de capture
--
-- Capture la valeur NOUVELLE : c'est celle qui a fait foi a partir de cet
-- instant. La garde IS DISTINCT FROM evite d'empiler des doublons quand une
-- ronde reecrit une cle sans rien changer — sinon la courbe porterait du bruit
-- au lieu de mouvements reels.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION deos_state_historise() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.valeur IS NOT DISTINCT FROM OLD.valeur THEN
        RETURN NEW;                      -- reecriture a l'identique : rien a garder
    END IF;

    INSERT INTO deos_state_history (cle, valeur, maj_par, origine)
    VALUES (NEW.cle, NEW.valeur, NEW.maj_par, 'trigger');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deos_state_historise ON deos_state;
CREATE TRIGGER trg_deos_state_historise
    AFTER INSERT OR UPDATE ON deos_state
    FOR EACH ROW EXECUTE FUNCTION deos_state_historise();

-- ---------------------------------------------------------------------
-- 3. Amorce : la valeur du jour, pour que la courbe ait un premier point
--    sans attendre la ronde suivante.
-- ---------------------------------------------------------------------
INSERT INTO deos_state_history (cle, valeur, maj_par, capture_le, origine)
SELECT cle, valeur, maj_par, updated_at, 'amorce'
  FROM deos_state
 WHERE NOT EXISTS (SELECT 1 FROM deos_state_history h WHERE h.cle = deos_state.cle);

-- ---------------------------------------------------------------------
-- 4. Vue de lecture : la courbe des scores, prete pour l'interface
--
-- Un score par direction et par jour (le dernier du jour fait foi). Le score
-- peut etre non numerique — Customer Success vaut "non calculable (0 compte
-- client reel...)". La vue rend alors score = NULL et conserve le libelle dans
-- score_brut, pour que l'interface affiche l'etat hachure "n. c." plutot qu'un
-- zero trompeur, conformement au principe directeur du handoff.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_scores_histo AS
SELECT DISTINCT ON (cle, capture_le::date)
       cle,
       replace(cle, 'rapport_', '')                       AS direction,
       capture_le::date                                   AS jour,
       valeur->>'domain_score'                            AS score_brut,
       CASE WHEN valeur->>'domain_score' ~ '^[0-9]+$'
            THEN (valeur->>'domain_score')::int END       AS score,
       capture_le
  FROM deos_state_history
 WHERE cle LIKE 'rapport_%'
 ORDER BY cle, capture_le::date, capture_le DESC;

COMMENT ON VIEW v_deos_scores_histo IS
 'Courbe des scores par direction et par jour (dernier releve du jour). score est NULL quand le domain_score n''est pas numerique ; score_brut conserve alors le libelle (ex. Customer Success : "non calculable"). Alimente la micro-courbe 15 jours des ecrans 6a/6b et des pages N1.';

-- Le score global de sante suit le meme principe, depuis la cle brief.
CREATE OR REPLACE VIEW v_deos_sante_histo AS
SELECT DISTINCT ON (capture_le::date)
       capture_le::date                                   AS jour,
       (valeur->'sante'->>'score')::int                   AS score_global,
       valeur->'sante'->>'statut'                         AS statut,
       capture_le
  FROM deos_state_history
 WHERE cle = 'brief'
   AND valeur->'sante'->>'score' ~ '^[0-9]+$'
 ORDER BY capture_le::date, capture_le DESC;

COMMENT ON VIEW v_deos_sante_histo IS
 'Courbe du score de sante global et de son statut, par jour. Sert la jauge et le delta de tendance des ecrans 6a et 6b.';
