-- =====================================================================
-- DEC-2026-0716-02 — Vues de lecture du comite (role deos_ro)
-- Cree le 05/08/2026. Base : digital_humans_db.
--
-- Complete les quatre vues preexistantes (v_deos_executions, v_deos_projects,
-- v_deos_sections, v_deos_build_phases) pour atteindre les neuf attendues.
--
-- Convention reprise des vues existantes : projection explicite des colonnes
-- (jamais SELECT *), afin qu'un ajout de colonne en amont n'elargisse pas
-- silencieusement ce qui est expose au comite.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. v_deos_blog_topics — aucune donnee personnelle
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_blog_topics AS
 SELECT id,
        title,
        description,
        source_url,
        source_name,
        suggested_agent,
        status,
        approved_agent,
        veille_date,
        approved_at,
        generated_at,
        ghost_post_id,
        created_at,
        notes
   FROM blog_topics;

COMMENT ON VIEW v_deos_blog_topics IS
 'DEC-2026-0716-02 (05/08) : sujets de blog, integralite. Aucune donnee personnelle.';

-- ---------------------------------------------------------------------
-- 2. v_deos_blog_articles — aucune donnee personnelle
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_blog_articles AS
 SELECT id,
        topic,
        title,
        meta_description,
        content,
        keywords,
        tone,
        word_count,
        status,
        generated_at,
        published_at,
        url
   FROM blog_articles;

COMMENT ON VIEW v_deos_blog_articles IS
 'DEC-2026-0716-02 (05/08) : articles de blog, integralite. Contenu editorial destine a publication.';

-- ---------------------------------------------------------------------
-- 3. v_deos_prospects — integralite, CONFORMEMENT A LA DEMANDE
--
-- RESERVE EXPLICITE (05/08) : contrairement a l'enonce de la decision, cette
-- table N'EST PAS exempte de donnees personnelles — elle porte name, title,
-- email et linkedin_url, soit des donnees identifiantes de personnes physiques.
-- La vue est neanmoins creee en integralite car c'est ce qui est demande, et
-- parce que la table est vide a ce jour (0 ligne au 05/08/2026) : l'exposition
-- est structurelle, pas encore effective.
-- L'arbitrage RGPD de Sam du 04/08 ne portait que sur `leads`. La meme logique
-- appliquee ici conduirait a retirer name, email et linkedin_url.
-- A ARBITRER PAR SAM AVANT QUE DES PROSPECTS NE SOIENT CHARGES.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_prospects AS
 SELECT id,
        name,
        title,
        company,
        email,
        linkedin_url,
        decision_maker_score,
        company_size,
        pain_points,
        approach_angle,
        industry,
        enriched_at,
        contacted_at,
        status
   FROM prospects;

COMMENT ON VIEW v_deos_prospects IS
 'DEC-2026-0716-02 (05/08) : prospects, integralite comme demande. RESERVE : expose name/title/email/linkedin_url, donnees personnelles identifiantes. L''arbitrage RGPD de Sam du 04/08 ne couvrait que la table leads. Table vide au 05/08 (0 ligne) : exposition structurelle, pas effective. A arbitrer avant chargement de donnees reelles.';

-- ---------------------------------------------------------------------
-- 4. v_deos_veille — aucune donnee personnelle
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_veille AS
 SELECT id,
        report_date,
        articles_count,
        articles,
        trends,
        opportunities,
        threats,
        actions,
        created_at
   FROM veille_reports;

COMMENT ON VIEW v_deos_veille IS
 'DEC-2026-0716-02 (05/08) : rapports de veille, integralite. Aucune donnee personnelle.';

-- ---------------------------------------------------------------------
-- 5. v_deos_leads — VUE RESTREINTE (arbitrage RGPD de Sam, 04/08/2026)
--
-- Seuls les champs PROFESSIONNELS sont exposes : societe, source, date de
-- creation, statut/stade, et un identifiant.
--
-- EXCLUS EXPLICITEMENT par l'arbitrage, et absents de cette projection :
--   - email            (donnee de contact personnelle)
--   - name             (identite de la personne)
--   - telephone        (aucune colonne de ce type dans la table a ce jour)
--   - contenu de conversation (aucune colonne de ce type dans la table ;
--                        score_reason est neanmoins ecarte car c'est du texte
--                        libre susceptible de citer la personne ou l'echange)
-- Egalement ecartes, non professionnels ou sensibles :
--   - verification_token, verified_at, token_expires_at
--     (secret et jalons du parcours de verification personnel)
--
-- La projection est volontairement explicite : un futur ajout de colonne dans
-- `leads` n'entrera pas dans cette vue sans decision.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_deos_leads AS
 SELECT id,                                   -- identifiant
        company,                              -- societe
        source,                               -- source d'acquisition
        created_at,                           -- date de creation
        verified,                             -- statut
        subscribed_newsletter,                -- statut
        score,                                -- stade de qualification
        scored_at                             -- date du stade
   FROM leads;

COMMENT ON VIEW v_deos_leads IS
 'DEC-2026-0716-02 — VUE RESTREINTE. Arbitrage RGPD de Sam du 04/08/2026 : seuls les champs professionnels sont exposes au comite (societe, source, date de creation, statut/stade, identifiant). Sont EXCLUS explicitement : email, nom de la personne, telephone, et tout contenu de conversation. score_reason est egalement exclu (texte libre pouvant citer la personne ou l''echange), ainsi que verification_token/verified_at/token_expires_at.';

-- ---------------------------------------------------------------------
-- Droits de lecture pour le comite
-- ---------------------------------------------------------------------
GRANT SELECT ON v_deos_blog_topics   TO deos_ro;
GRANT SELECT ON v_deos_blog_articles TO deos_ro;
GRANT SELECT ON v_deos_prospects     TO deos_ro;
GRANT SELECT ON v_deos_veille        TO deos_ro;
GRANT SELECT ON v_deos_leads         TO deos_ro;
