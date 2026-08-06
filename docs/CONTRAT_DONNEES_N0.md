# Contrat de données — Poste de pilotage (N0 / N1)

**Décision de rattachement** : DEC-2026-0716-02 (vues de lecture du comité) et le handoff de conception « Poste de pilotage — Digital·Humans ».
**Établi le** : 05/08/2026 · **Auteur** : session `session/2026-08-05-decisions-accordees`
**Statut** : document d'analyse. **Aucune modification de code.** L'interface n'est pas implémentée dans cette session — le design n'est pas validé par Sam en conditions réelles, et le handoff précise lui-même que `Poste de pilotage.dc.html` est une référence de design, pas du code de production.

---

## 1. Pourquoi ce document

Le handoff signale deux réserves non résolues (README, § Fidélité) :

> — Les indicateurs numériques de Delivery (exécutions, couverture de logs, etc.) et les textes de « rapport du jour » sont **inventés** faute de vraies données.
> — Les scores par direction (63, 88, 50, 39…) et les âges de décision (19 j, 20 j) sont des **exemples**, pas les vraies données.

Sans contrat écrit, on paierait deux fois : une fois pour créer les vues, une fois pour découvrir qu'elles ne fournissent pas ce que l'interface attend. Ce document établit la correspondance **indicateur par indicateur**.

**Résultat en une phrase** : sur les 51 emplacements de donnée recensés, **27 sont alimentables aujourd'hui**, **14 demandent une agrégation ou un calcul à écrire**, et **10 n'ont aucune source** (dont 3 valeurs purement inventées) — les manques les plus structurants étant l'historique des scores, le compteur de relances et trois des quatre emplacements de la direction Juridique.

---

## 2. Méthode et sources consultées

| Repère | Base / fichier | Accès |
|---|---|---|
| **PG** | `digital_humans_db` (production plateforme) — vues `v_deos_*` | rôle `deos_ro`, lecture seule |
| **CO** | `dh_comite` (conteneur `dh-comite`) — tables `deos_state`, `decisions` | `$COMITE_DB_DSN` |
| **FS** | fichiers du VPS (`/var/log/digital-humans/`, `/workspace/config/`) | lecture |

Croisements effectués :
- README du handoff, § 6a, 6b et 6c à 6h ; brief de conception § « Ce que doit contenir le N0 », § « page de direction (N1) » et § « Données réelles à utiliser » ;
- les 8 captures `screenshots/6a` à `6h`, lues une par une — elles font foi sur les libellés affichés ;
- `SELECT valeur->'besoin_interface' FROM deos_state WHERE cle LIKE 'rapport_%'` — 5 directions ont exprimé un besoin (**commercial, cos, cs, delivery, marketing**). **Il n'existe aucune clé `rapport_juridique`** : la 6ᵉ direction n'a pas exprimé de besoin et n'a pas de source.

**Convention d'état**
- `disponible` — une requête existe aujourd'hui et rend la valeur. À câbler, rien à construire.
- `en_construction` — la matière existe mais l'indicateur demande une agrégation, un calcul ou un champ à ajouter.
- `absent` — aucune source. Un prérequis doit être créé avant tout affichage.

**Règle du handoff qui gouverne tout le reste** (§ Principe directeur) : un emplacement sans donnée affiche un **état explicite** (« accès en attente », « historique en construction »), **jamais un zéro trompeur ni une valeur inventée**, et se remplit sans changement de mise en page. Les états `absent` et `en_construction` ci-dessous ne bloquent donc pas l'implémentation — ils désignent les emplacements qui doivent partir en état explicite.

---

## 3. Écran 6a — N0, téléphone (393×852)

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6a | *(en-tête)* « Rapports 07:12 » | pastille + heure | CO `SELECT max(updated_at) FROM deos_state WHERE cle LIKE 'rapport_%'` | disponible | Vérifié : 07:12:40 le 05/08. |
| 6a | Score de santé « 63 » | jauge arc SVG | CO `SELECT valeur->'sante'->>'score' FROM deos_state WHERE cle='brief'` | disponible | Valeur réelle au 05/08 = **65** (le 63 du handoff est un exemple proche). Seuils du handoff : vert ≥75, ambre 55–74, rouge <55 — cohérents avec le `statut` « ambre » déjà calculé en base. |
| 6a | Tendance « ▲ 4 » | delta chiffré | CO `valeur->'sante'->>'tendance'` | en_construction | Le champ existe mais c'est du **texte libre** (« en légère baisse, NON strictement comparable… »), pas un delta numérique. Il faut soit stocker le score de la veille, soit dériver du futur historique (§ 10.2). |
| 6a | « 3 incidents » | compteur rouge | CO `SELECT count(*) FROM jsonb_array_elements(valeur->'alertes') a WHERE a->>'gravite'='haute'` sur `cle='brief'` | disponible | `gravite` et `domaine` sont bien structurés dans `brief->alertes`. Conforme au brief : « alertes de gravité haute uniquement » au N0. |
| 6a | « 2 actes » | compteur laiton | CO `SELECT count(*) FROM decisions WHERE statut='attente_sam'` | disponible | Vérifié = **2** au 05/08. |
| 6a | « Historique en construction » | micro-courbe 15 j | — | **absent** | Voir § 10.2. Le handoff demande explicitement une courbe de tendance, pas un texte statique. |
| 6a | Acte — intitulé | liste, chiffres romains | CO `SELECT id, texte FROM decisions WHERE statut='attente_sam' ORDER BY date` | disponible | |
| 6a | Acte — âge « 19 j » + filet | barre de progression | CO `now()::date - date::date` | disponible | **Les âges 19 j / 20 j du handoff ne correspondent à rien en base.** L'âge maximal réel d'un acte en attente est de **1 jour**. Les deux exemples du handoff sont des reformulations de `DEC-2026-0716-03` (statut `clos`) et `DEC-2026-0716-01` (statut `accordee`) — ni l'une ni l'autre n'est un acte à trancher. Seuils du handoff : ambre à 7 j, rouge à 14 j, filet 2px au-delà. |
| 6a | Acte — direction porteuse | libellé mono | CO `decisions.origine` | en_construction | La colonne existe mais vaut `'sam'` pour les 6 actes en attente — elle porte l'**émetteur**, pas la direction concernée. Le handoff affiche « CHIEF OF STAFF », « COMMERCIAL ». Il manque un champ `domaine` sur `decisions` (ou un mapping depuis `porte_sur`). |
| 6a | Accorder / Refuser / Complément | boutons | CO `UPDATE decisions SET statut=…` | disponible | Chemin d'écriture existant. Contrainte en base : `clos_avec_preuve` interdit `statut='clos'` sans `preuve`. Un trigger interdit la suppression. |
| 6a | Refus — motif obligatoire + 3 chips | panneau de saisie | — | **absent** | **Aucune colonne de motif de refus** sur `decisions`. Le handoff impose un motif bloquant. Prérequis : ajouter une colonne (ex. `motif_refus text`) — sinon le motif saisi est perdu. |
| 6a | Partition — 6 directions | ligne + mini-jauge | CO `valeur->>'domain_score'` sur `cle IN ('rapport_delivery','rapport_commercial','rapport_marketing','rapport_cs','rapport_cos')` | disponible **(5/6)** | Vérifié : delivery 88, commercial 50, marketing 60, cos 39, cs = chaîne « non calculable… » → rend l'état « n. c. » hachuré du handoff. **Juridique : aucune clé `rapport_juridique`** — voir § 9. |

---

## 4. Écran 6b — N0, ordinateur, panneau latéral (1440×900)

Même contenu que 6a en deux colonnes. **Aucun indicateur supplémentaire** : le contrat de 6a s'applique intégralement.

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6b | « Acte du jour · Mardi 5 août » | libellé daté | CO `valeur->>'date'` sur `cle='brief'` | disponible | |
| 6b | La partition — 6 lignes avec repère | jauges horizontales à marqueur | idem 6a | disponible (5/6) | Le marqueur se positionne sur l'échelle 0–100. Pour `cs` (« n. c. ») et `juridique` (« dem. ») le handoff prévoit un trait pointillé sans marqueur — cohérent avec la règle « jamais un zéro trompeur ». |
| 6b | « Demander un complément » (libellé long) | bouton | — | disponible | Différence de libellé seulement (mobile : « Complément » + infobulle). |

---

## 5. Écran 6c — Delivery (N1)

C'est l'écran que le handoff signale comme **le plus inventé**.

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6c | Score « 88 / 100 » | grand chiffre | CO `rapport_delivery → domain_score` | disponible | Valeur réelle 88. Le calcul est tracé dans `rapport_delivery → calcul_score`. |
| 6c | « Historique en construction » | micro-courbe | — | **absent** | § 10.2. |
| 6c | « 3 / 3 » Exécutions saines · 7 j | compteur fractionnaire | PG `SELECT count(*) FILTER (WHERE status='COMPLETED'), count(*) FROM v_deos_executions WHERE created_at > now()-interval '7 days'` | disponible | **Chiffre inventé dans le handoff.** Valeur réelle : **0 exécution sur 7 jours** — la requête rend `0 / 0`. C'est précisément le cas que la règle « jamais un zéro trompeur » vise : afficher « aucune exécution sur la période », pas « 0 / 0 ». |
| 6c | « 14 % » Couverture des logs 24 h | barre de remplissage | FS `/var/log/digital-humans/backend-24h.log` | en_construction → **disponible après la tâche 3** | Réclamé en `indispensable` par le Delivery (« aucun outil ne fait ce calcul, je le fais à la main par grep à chaque ronde »). La tâche 3 de cette session ajoute une ligne d'en-tête portant les bornes réelles et le nombre de lignes : l'interface lira cet en-tête au lieu de reparser le fichier. Le Delivery demande en plus le **nombre de rafales** et la **durée cumulée** — non couverts par l'en-tête, à ajouter si l'on veut l'indicateur complet. |
| 6c | « 1 » Décisions portées sans preuve | compteur | CO `SELECT count(*) FROM decisions WHERE statut IN ('accordee','en_execution') AND preuve IS NULL` | en_construction | Le **comptage global fonctionne** (valeur réelle : **22**). Ce qui manque est le **filtre par porteur/domaine** — la colonne n'existe pas (même manque qu'en 6a). Sans elle, impossible de rendre « portées par le Delivery ». |
| 6c | Pastille « BLOQUÉ » / « Verdict en cours » | pastille d'état | croisement PG `v_deos_executions.state_updated_at` × `v_deos_build_phases.attempt_count` × log backend × `GET :8002/api/pm-orchestrator/workers/health` | **absent** | C'est le verdict DH-DEL-003, `indispensable` n° 1 du Delivery. Les quatre sources existent **séparément** ; le calcul croisé (silence réel > 2× la baseline de phase) n'existe nulle part. Prérequis : écrire ce calcul, ce n'est pas un widget d'affichage. |
| 6c | « Exécution #482 bloquée — dépendance manquante, en attente depuis 6 jours. » | texte | — | **absent (inventé)** | L'exécution 482 n'existe pas. La plus haute observée est **165**. Ce texte doit être remplacé par la sortie du verdict ci-dessus. |
| 6c | Actes à trancher « 0 » | compteur + état vide | CO `decisions WHERE statut='attente_sam'` + filtre domaine | en_construction | Même dépendance au champ `domaine` manquant. |
| 6c | Alertes — « Correctif d'un bug bloquant non appliqué » | liste à pastilles | CO `rapport_delivery → alertes` | disponible | Structuré avec `gravite` et `domaine`. Le N1 affiche **toutes gravités** (le N0 seulement les hautes). |
| 6c | Rapport du jour | texte | CO `rapport_delivery → faits` / `→ statut` | en_construction | La matière existe (17 433 caractères). Il manque un champ court destiné à l'affichage : aujourd'hui il faudrait résumer côté interface, ce qui est un traitement, pas une lecture. |

---

## 6. Écran 6d — Commercial (N1)

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6d | Score « 50 / 100 » | grand chiffre | CO `rapport_commercial → domain_score` | disponible | Valeur réelle 50. |
| 6d | Pipeline par stade — 0 / 0 / 0 / 0 | barres réservées par stade | CO `deos_state.pipeline_commercial → stades` | disponible | Les **7 stades** existent en base (`lead, qualifie, demo, proposition, negociation, signe, perdu`), tous à liste vide, `maj` au 14/07. Le handoff n'en affiche que 4 — arbitrage d'affichage à confirmer. Conforme au principe : la barre est dimensionnée pour la donnée cible même à 0. |
| 6d | « 27 jours » avant lancement | compte à rebours | CO `objectifs_commerciaux → regime_B_lancement → des_le` (`2026-09-01`) moins la date du jour | disponible | Vérifié : 01/09 − 05/08 = **27 jours**. Indicateur **exact** dans le handoff. |
| 6d | « 11 / 15 » Bibliothèque de cas d'usage | barre de remplissage | FS comptage de `/workspace/config/commercial/cas_usage/` ; cible dans CO `objectifs_commerciaux → regime_A → jalons → bibliotheque_cas` (« 15 avant le 31/08 ») | en_construction | Le **dénominateur 15 est sourcé** en base. Le numérateur est un comptage de fichiers **hors base** — il faut soit l'exposer par une API, soit le remonter dans `deos_state`. Le Commercial le classe en `souhaitable`. |
| 6d | Flux de leads entrants — « Donnée non disponible — accès en attente » | emplacement explicite | PG `SELECT id, company, source, created_at, verified, subscribed_newsletter, score, scored_at FROM v_deos_leads ORDER BY created_at DESC` | **disponible depuis la tâche 2** | **Cet emplacement peut désormais être rempli.** Voir la réserve détaillée en § 10.3. |
| 6d | Actes à trancher « 1 » | liste | CO `decisions` + filtre domaine | en_construction | Même dépendance au champ `domaine`. |

---

## 7. Écran 6e — Chief of Staff (N1, ordinateur)

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6e | Score « 39 / 100 » | grand chiffre | CO `rapport_cos → domain_score` | disponible | Valeur réelle 39. |
| 6e | « 3 » Décisions accordées sans preuve, *triées par âge depuis le dernier signe d'activité* | grand compteur central | CO `count(*) … WHERE statut IN ('accordee','en_execution') AND preuve IS NULL` | en_construction | **Le compteur est disponible** (valeur réelle **22**, pas 3). **Le tri ne l'est pas** : le CoS écrit lui-même que « la donnée *dernier signe d'activité réel* n'existe NULLE PART aujourd'hui de façon structurée : je la reconstruis à la main à chaque ronde ». `decisions.updated_at` ne rend que l'horodatage du dernier changement de statut, ce que le CoS refuse explicitement comme approximation. **Prérequis : une colonne ou une vue dérivée**, pas un widget. |
| 6e | « 4 » Relances émises | compteur | — | **absent** | Le CoS le classe en `souhaitable` et précise : « aujourd'hui je le retiens dans mon narratif de ronde, pas dans une structure interrogeable ». Aucune table de relances. |
| 6e | « 142 000 € » Trésorerie — solde déclaré | grand chiffre + date | CO `cash_suivi → solde_declare` et `→ date_declaration` | disponible | **Valeur réelle : 0 €**, déclarée le 14/07. Le 142 000 € du handoff est inventé. L'écart est important : l'écran donne une impression de confort de trésorerie que la base contredit. |
| 6e | « Surveillance inactive » / Seuil d'alerte | pastille d'état | CO `cash_suivi → seuil_alerte_solde` (vaut `null`) + âge de `date_declaration` | disponible | La règle du CoS est explicite : au-delà de 14 j sans mise à jour → « surveillance cash inactive ». Au 05/08 : **22 jours** sans mise à jour et **seuil jamais fixé** → l'état affiché par le handoff est le bon, pour les bonnes raisons. |
| 6e | Dispositif de reporting du jour — 6 pastilles (DEL/COM/MKT/CS/COS/JUR + heure) | rangée de pastilles | CO `SELECT cle, updated_at FROM deos_state WHERE cle LIKE 'rapport_%'` | disponible **(5/6)** | Vérifié au 05/08 : delivery 07:08, commercial 07:06, marketing 07:05, cs 07:02, cos 07:12. **Le handoff affiche « MKT — » et « CS — » (silencieux) alors que les deux avaient rapporté** : incohérence de la maquette. « JUR à la dem. » est correct — pas de clé, régime à la demande. Règle du CoS à implémenter : 2 domaines manquants sur 5 le même jour → escalade automatique. |
| 6e | Rapport du jour | texte | CO `brief → recommandation` / `rapport_cos` | en_construction | Même remarque qu'en 6c : matière abondante (17 540 caractères), pas de champ court d'affichage. Le texte du handoff (« runway 94 jours », « sur cinq décisions accordées, deux exécutées ») est **inventé** — les chiffres réels sont 22 décisions sans preuve et un solde déclaré à 0. |

---

## 8. Écrans 6f — Marketing et 6g — Customer Success (N1)

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6f | Score « 60 / 100 » | grand chiffre | CO `rapport_marketing → domain_score` | disponible | Valeur réelle 60. |
| 6f | Séquence éditoriale — 13 pas colorés | séquence segmentée | CO `deos_state.calendrier_editorial → sequence_lancement` | disponible | Vérifié : **exactement 13 rangs**, chacun avec `rang`, `titre`, `statut`, `date_cible`, `id_contenu`. La coloration par état individuel se déduit de `statut`. Excellente correspondance. |
| 6f | « 2 » Publiés non confirmés | compteur | CO `calendrier_editorial → publies` croisé avec `perf_contenu.disponible` | en_construction | `perf_contenu` porte `disponible: false` et `hypothese: true` — aucune publication confirmée. Le Marketing le classe en `indispensable` n° 2 et précise que la source est **absente** : « le compte LinkedIn Company Page n'est branché à aucun outil du comité ». Prérequis : accès API LinkedIn **ou** confirmation manuelle de Sam. |
| 6f | « En attente » — Conformité, réouverture du site | pastille + libellé | — | **absent** | `indispensable` n° 3 du Marketing : l'état d'avancement AI Act art. 50 (DEC-2026-0802-07) est produit par le Juridique/Delivery. Aucune clé ne le porte. Le Marketing demande explicitement que l'interface le **remonte depuis leur loge, pas le duplique**. |
| 6f | Alertes — « Aucune alerte haute » | liste + état vide | CO `rapport_marketing → alertes` | disponible | |
| 6g | « n. c. » hachuré | bloc d'état | CO `rapport_cs → domain_score` | disponible | La valeur en base **est** la chaîne « non calculable (0 compte client réel…) ». L'interface doit détecter le non-numérique et basculer en hachuré. Correspondance exacte avec le handoff. |
| 6g | « NON CÂBLÉ » — Canal de support | pastille d'état | CO `comptes_clients → canal_tickets_v1` / `canal_tickets_v2` | en_construction | `canal_tickets_v1` existe en texte libre (« à câbler avec SMTP-PROD-001 »). Le CS demande un **statut à trois valeurs** (actif / en cours de câblage / non câblé) qu'aucun champ ne porte. Prérequis : un drapeau, ou une vue `v_deos_cases` côté Salesforce une fois le BUILD livré. |
| 6g | « 54 » Préparation avant premier client | barre de remplissage % | — | **absent (inventé)** | Aucune source, et **le CS ne l'a pas demandé** — il ne figure dans aucun de ses trois `indispensable`. C'est un indicateur créé par le design. À supprimer ou à définir avec le CS avant implémentation. |
| 6g | « Aucun compte client à ce jour » — Comptes en risque | état vide explicite | CO `comptes_clients → comptes` (tableau vide) | disponible | Correct : 0 compte. La formule de santé et le seuil rouge < 60 sont définis dans le skill `dh-sante-comptes`, applicables dès le premier compte. |
| 6g | « — » Renouvellements < 45 j sans contact | compteur | CO `comptes_clients → comptes[].echeance_renouvellement` | disponible (structure) | Le champ est prévu dans le parcours d'onboarding (« Point renouvellement à J-45 »). Vide tant qu'il n'y a pas de compte. Se remplira sans changement de mise en page — conforme au principe directeur. |

---

## 9. Écran 6h — Juridique (N1) : la direction sans source

| Écran | Libellé affiché | Widget | Source | État | Note |
|---|---|---|---|---|---|
| 6h | « DEM. » (régime à la demande) | bloc d'état | CO `brief → fraicheur_rapports → legal` | en_construction | Seule trace existante : une chaîne de texte dans le brief (« à la demande — pas de ronde quotidienne, absence normale hors calcul de santé »). Suffit à afficher l'état « dem. », pas à alimenter la page. |
| 6h | Missions en cours — « Revue du contrat-cadre fournisseur » (4 j), « Clause de résiliation à négocier » (11 j) | liste + âge | CO `decisions` — les missions juridiques sont suivies comme `DEC-2026-0802-05` et `DEC-2026-0802-06` | en_construction | Les deux décisions **existent réellement** (citées dans `fraicheur_rapports → legal` comme « 2 missions juridiques en retard »). Les libellés et les âges du handoff sont des exemples. À câbler via un filtre par domaine — même manque de champ `domaine` qu'ailleurs. |
| 6h | « 18 j » Échéance réglementaire la plus proche — Renouvellement d'agrément CNIL | compte à rebours | — | **absent (inventé)** | Aucune clé d'échéances réglementaires. `cash_suivi → echeances_connues` existe mais est **vide** et concerne la trésorerie. Prérequis : créer une clé d'échéances réglementaires. |
| 6h | Rapport du jour | texte | — | **absent** | Pas de clé `rapport_juridique`. |

> **Constat de fond** : le Juridique est la seule des six directions à n'avoir **exprimé aucun besoin d'interface** et à n'avoir **aucune clé de rapport**. Le gabarit N1 fonctionne pour elle (le handoff le prouve), mais **trois de ses quatre emplacements sont vides de source**. Décision à prendre avant implémentation : soit créer une clé `rapport_juridique` alimentée à la demande, soit assumer une page réduite à l'état « à la demande » et aux missions filtrées depuis `decisions`.

---

## 10. Les trois points de vigilance

### 10.1 Les indicateurs marqués « inventés »

Le handoff signale honnêtement que les indicateurs Delivery et les « rapport du jour » sont inventés. Le relevé exact, après confrontation à la base :

| Valeur affichée | Écran | Réalité en base au 05/08 | D'où viendra la vraie valeur |
|---|---|---|---|
| « 3 / 3 » exécutions saines | 6c | **0 exécution sur 7 jours** | `v_deos_executions` — requête disponible, mais doit afficher un état explicite tant qu'il n'y a pas d'exécution |
| « 14 % » couverture des logs | 6c | mesurable, jamais mesuré automatiquement | en-tête du log ajouté en tâche 3 |
| « Exécution #482 bloquée » | 6c | l'exécution 482 **n'existe pas** (max = 165) | sortie du verdict DH-DEL-003, **à écrire** |
| « 1 » décision sans preuve (Delivery) | 6c | 22 au total, non filtrables par domaine | `decisions` + champ `domaine` **à ajouter** |
| « 3 » décisions sans preuve (CoS) | 6e | **22** | idem |
| « 4 » relances émises | 6e | aucune structure | **n'existe pas encore** — table à créer |
| « 142 000 € » trésorerie | 6e | **0 €**, déclaré le 14/07 | `cash_suivi → solde_declare`, alimenté par Sam seul |
| « 54 » préparation CS | 6g | aucune source, **non demandé par le CS** | **n'existe pas** — à définir ou supprimer |
| « 18 j » échéance CNIL | 6h | aucune clé d'échéances réglementaires | **n'existe pas** — clé à créer |
| Textes « rapport du jour » | 6c, 6e, 6g, 6h | matière présente, pas de champ court | champ d'affichage à ajouter aux clés `rapport_*` |
| Âges « 19 j » / « 20 j » | 6a, 6b | âge réel maximal d'un acte en attente : **1 jour** | `decisions` — calcul disponible, exemples à ne pas reprendre |
| Score global « 63 » | 6a, 6b | **65** | `brief → sante → score` — disponible |

Les scores par direction (88, 50, 60, 39, n. c.), en revanche, **sont exacts** : le handoff les présentait comme des exemples, ils correspondent aux valeurs réelles du 05/08. Le brief de conception les donnait d'ailleurs comme « les vraies » (§ Données réelles). La réserve du README est plus prudente que nécessaire sur ce point précis.

### 10.2 L'historique des scores — le manque le plus structurant

**Constat.** `deos_state` est une table clé/valeur : `UPDATE` sur la même clé à chaque ronde. La valeur du jour **écrase** celle de la veille. Seul `updated_at` survit, et il ne porte que le dernier passage. Il n'existe donc **aucune tendance sur 15 jours**, et le champ `sante → tendance` est du texte rédigé à la main qui compare de mémoire à la veille (« Hier 68… aujourd'hui 65 »).

**Conséquence sur l'interface.** Trois emplacements en dépendent, aujourd'hui tous en état explicite :
- le cadre « Historique en construction » du 6a et du 6b (micro-courbe 15 jours demandée par le handoff) ;
- le même cadre sur chaque page N1 (6c en montre un) ;
- le delta « ▲ 4 » à côté du score global.

Le Delivery l'a demandé nommément : *« Historique du domain_score Delivery sur les 15/30 derniers jours (tendance, pas juste la valeur du jour) »*, avec la mention *« historisation à ajouter, actuellement une seule valeur écrasée à chaque ronde »*.

**Ce qu'il faudrait pour l'obtenir.** Par ordre de coût croissant :

1. **Table d'historique** — la voie recommandée. Une table `deos_state_history (cle, valeur, capture_le)` alimentée par un trigger `AFTER UPDATE` sur `deos_state`. Coût faible, rétroactif à zéro : **la courbe ne commencera à exister qu'à partir de sa mise en place**. Posée aujourd'hui, elle donne 15 points le 20/08.
2. **Extraction ciblée** — n'historiser que les scores (`cle`, `domain_score`, `date`) plutôt que le JSON entier. Plus léger, suffisant pour la courbe et le delta, mais ferme la porte à toute autre tendance.
3. **Reconstruction rétrospective** — les rapports de ronde archivés (`rondes/*.json`, cités par le CoS) pourraient fournir des points passés. À vérifier : non exploré dans cette session, et l'antériorité réelle n'est pas garantie.

**Recommandation** : option 1, **et le plus tôt possible** — chaque jour de retard est un point de courbe définitivement perdu. C'est le seul prérequis de ce document dont le coût augmente avec l'attente.

### 10.3 Le flux de leads — ce que la vue restreinte permet, et ce qu'elle ne permet pas

`v_deos_leads` a été créée en tâche 2 de cette session, sous l'arbitrage RGPD de Sam du 04/08 : seuls les champs professionnels sont exposés.

**Colonnes disponibles** : `id`, `company`, `source`, `created_at`, `verified`, `subscribed_newsletter`, `score`, `scored_at`.
**Colonnes exclues** : `email`, `name`, téléphone (aucune colonne), contenu de conversation (aucune colonne), `score_reason`, `verification_token`, `verified_at`, `token_expires_at`.

**Confrontation au besoin exprimé par le Commercial** — *« Les nouveaux leads captés (société si connue, source, date, score /10) au fil de l'eau »* :

| Élément demandé | Couvert ? | Détail |
|---|---|---|
| Société | ✅ | `company` |
| Source | ✅ | `source` |
| Date | ✅ | `created_at` |
| Score | ⚠️ | `score` est disponible mais sur une **échelle 0–100** (valeurs réellement observées : de 20 à 85), alors que le Commercial raisonne en **/10** et pilote sur des seuils « ≥ 7 » et « < 4 ». **Une conversion d'échelle doit être tranchée** : `score/10`, ou seuils réexprimés en 70 / 40. Sans cet arbitrage, l'interface affichera des scores que le Commercial lira à contresens. |
| Stade du pipeline | ❌ | `v_deos_leads` **ne porte pas de stade**. Le pipeline par stade du 6d vient d'une autre source, `deos_state.pipeline_commercial`, sans lien avec la table `leads`. Les deux ne se rejoignent nulle part aujourd'hui. |
| « Prochaine action » et « échéance » | ❌ | Demandés dans l'`indispensable` n° 1 du Commercial ; aucune colonne. Relèvent de `pipeline_commercial`, pas de `leads`. |

**Verdict** : ce qui reste après restriction **suffit pour l'emplacement « Flux de leads entrants » du 6d** — société, source, date, score. La restriction RGPD ne coûte rien à cet indicateur : le Commercial n'a jamais demandé ni l'email, ni le nom, ni de verbatim (il demandait explicitement « résumé + intention, pas de verbatim »).

**Deux réserves à signaler** :
1. **L'échelle du score doit être arbitrée** (voir ci-dessus) — c'est le seul point qui peut produire un affichage faux.
2. **Le contenu est aujourd'hui 100 % de test.** Les 7 lignes portent `Test Corp`, `N8N Test`, `tata`, et une ligne à `company` vide. L'accès est débloqué, mais **le pipeline reste vide de leads réels** — le blocage se déplace de l'accès vers la source. L'interface affichera donc légitimement un flux, mais un flux non représentatif : prévoir l'état explicite plutôt qu'une liste de données de test.

---

## 11. Synthèse — ce qu'il reste à construire avant implémentation

**Prérequis bloquants** (un emplacement du handoff ne peut pas exister sans eux) :

| # | Prérequis | Débloque | Coût estimé |
|---|---|---|---|
| P1 | Champ `domaine` sur `decisions` (ou mapping depuis `porte_sur`) | direction porteuse en 6a/6b ; actes et décisions sans preuve filtrés en 6c/6d/6e/6h — **6 emplacements** | faible |
| P2 | Historisation de `deos_state` (§ 10.2) | courbe 15 j sur tous les écrans + delta de tendance — **3 emplacements**, coût croissant avec l'attente | faible, **urgent** |
| P3 | Colonne de motif de refus sur `decisions` | le refus motivé du 6a, imposé comme bloquant par le handoff | faible |
| P4 | Calcul du verdict DH-DEL-003 | pastille « bloqué » et texte d'incident du 6c | moyen |
| P5 | « Dernier signe d'activité réel » par décision | tri du grand compteur du 6e — `indispensable` n° 1 du CoS | moyen |
| P6 | Champ court « rapport du jour » sur les clés `rapport_*` | 4 emplacements de texte | faible |
| P7 | Clé `rapport_juridique` + clé d'échéances réglementaires | 3 des 4 emplacements du 6h | faible |
| P8 | Arbitrage de l'échelle du score de lead (/10 ou /100) | évite un affichage faux en 6d | nul, décision |

**Indicateurs à retirer ou redéfinir avant implémentation** : « 54 % préparation » du 6g (inventé et non demandé par le CS), « 4 relances émises » du 6e (aucune structure, classé `souhaitable` par le CoS).

**Incohérence de maquette à corriger** : en 6e, MKT et CS sont affichés silencieux alors que les deux avaient rapporté à 07:05 et 07:02.

---

*Document établi le 05/08/2026 · toutes les valeurs « réelles » citées ont été relevées par requête sur `digital_humans_db` et `dh_comite` le jour même · aucune modification de code, aucune implémentation d'interface.*
