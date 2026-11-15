# Smoke de bout en bout — 15/11/2026 — SDS + BUILD réel sur `sandbox-build`

Session menée avec Sam. Compte de test `smoke@digital-humans.fr` (user 19), passé en Team (100 000 crédits) le temps du test puis remis en Pro (15 000 inclus, 6 999 consommés). Org de test : `sandbox-build` = `orgfarm-34b993836d-dev-ed` (`00DgK00000VvwqDUAR`, Developer Edition). Le CRM de Sam (`00Dfj00000VIwy9EAD`) n'a jamais été ciblé.

## 1. Ce qui a tourné

| Exécution | Projet | Objet | Issue | Coût |
|---|---|---|---|---|
| 183 | 122 — Qualification des leads (Agentforce) | SDS | annulée : « Event loop is closed » (corrigé `62d7166`) | 1,20 $ |
| 184 | 124 — Service client (greenfield) | SDS (tâche programmée de 16h07) | annulée : doublon du 186, sans org (décision Sam) ; relancée seule par ARQ au redémarrage du worker | 4,51 $ |
| 185 | 122 — Qualification des leads | SDS | **terminé** (28 exigences, portes BR et architecture validées par pilote) | 10,23 $ |
| 186 | 125 — Support client (Service Cloud + Agentforce) | SDS | **terminé** (29 exigences), sur `sandbox-build` | 12,18 $ |
| 185 | 122 | BUILD (4 lancements) | **phase 1 déployée pour de vrai** ; phase 2 Apex refusée 3× par Elena ; arrêt (décision Sam) | ≈ 13,60 $ |

Total exécution 185 (SDS + BUILD) : 23,84 $. Crédits consommés par smoke@ pendant la session : 31 302.

SDS (Word) : `backend/outputs/SDS_Exec185.docx` et `SDS_Exec186.docx` (liens temporaires donnés à Sam sous `/apercu-2026/sds-<jeton>/`, à supprimer — chemin noté dans `/root/backups/2026-11-15/liens_temporaires.txt`).

## 2. Résultats du SDS

- **Marcus voit maintenant l'existant** (correctif du 05/11 confirmé) : l'as-is cite les 7 champs déjà présents (Score_Qualification__c, Detail_Score__c, Tier_Vise__c, Source_DH__c, MRR__c, Relance_En_Retard__c, Date_Prochaine_Relance__c).
- **Mais il ne les réutilise pas** : il les remplace volontairement par des champs anglais (Qualification_Score__c, Target_Offer__c, Follow_Up_Overdue__c…) au nom de sa règle de nommage (ARCH-001), avec migration puis suppression. Argumenté, mais inacceptable pour un client qui a déjà ses champs.
- **Incohérence de nommage** dans la conception : `Market_Signal__c` (68 mentions) et `Signal_Marche__c` (67) pour le même objet.
- **Plafond Opus GL-22 atteint** sur 185 à ~70 % (6 720 crédits acceptés ; un SDS réel en consomme ~9 000) : Olivia est passée en Sonnet pour 2 appels, exécution marquée dégradée. Plafond relevé à 16 000 pour 185 et 186 (accord Sam, sauvegarde `/root/backups/2026-11-15/opus_consents_185_186_avant.csv`).
- **Cache** : 0 jeton lu ou écrit — les prompts système (< 2 000 jetons) sont sous le seuil de mise en cache.
- Tous les jetons sont bien facturés en crédits (708 k jetons sur 185 = somme des `credit_transactions`).

## 3. Résultats du BUILD (exécution 185, projet 122)

1. **Lancement 1 (18h17)** — phase 1 refusée par la validation à blanc Salesforce : défauts du générateur XML de Raj → corrigés `bfcb6b4` ; les 53 opérations rejouées passent la validation à blanc (53/53, 0 erreur).
2. **Lancement 2 (18h47)** — **phase 1 déployée dans l'org** : `Market_Signal__c`, `Lead_Score_Detail__c`, `Lead_Scoring_Rule__mdt` + 36 champs (dont Lead.Score__c, Source_Lead__c, Synthese__c ; Opportunity.Follow_Up_Status__c, Last_Contact_Date__c, Next_Step_Date__c…) + 2 règles de validation. Aucun champ existant supprimé ni modifié. Phase 2 : Diego tronqué à 16 000 jetons → tests absents → Elena FAIL ×3 → corrigé `25a0e63` (32 000).
3. **Lancement 3 (19h31)** — la relance a refait la phase 1 ; nouveau plan de Raj incompatible avec l'org (« Duplicate label: Économie ») → corrigé `50353d7` (reprise sans refaire une phase déployée ; registre de la phase 1 reconstruit depuis l'org, le journal du worker étant tronqué à 48 Ko).
4. **Lancement 4 (19h57)** — reprise OK (phase 1 non refaite, Diego directement). Elena FAIL ×3 sur des défauts réels : `LeadScoringService` sans test, trois moteurs de scoring divergents, `Callable` attendu mais non implémenté, double `Test.startTest()`, test de batch bulk faux. Diego réécrit tout à chaque tentative au lieu de corriger les fichiers signalés : il ne converge pas.

Doublon fonctionnel créé par Raj : `Lead.Score__c` à côté de `Score_Qualification__c` existant.

## 4. Correctifs livrés (branche `claude/vague-c-20260906`, déployés)

`62d7166` client Anthropic par boucle · `1eaaaa2` crédits incluant le cache · `bfcb6b4` XML Raj + Jordan sans Git · `25a0e63` plafond 32 000 Diego/Zara · `50353d7` reprise de BUILD. Tests ajoutés : `tests/services/test_sf_admin_xml_build185.py`, `tests/services/test_reprise_build_phase_deployee.py`, `test_client_async_par_boucle.py`, `test_emma_libelles_sf.py`. Suites liées vertes (130 + 180 tests).

## 5. État laissé

- `DH_SALESFORCE_WRITES_ENABLED` retiré de `backend/.env` ; garde vérifiée fermée (`SalesforceWritesDisabled`) ; backend et worker redémarrés, `/health` sain.
- smoke@ remis en Pro, 15 000 / 6 999 (`/root/backups/2026-11-15/smoke_user19_avant.txt`).
- Projet 122 : statut `build_in_progress`, exécution 185 FAILED ; phase 1 `completed` avec registre. L'org `sandbox-build` contient le modèle de données de la phase 1.
- Comité Spark toujours en pause (depuis 15/11, `docker stop dh-comite dh-comite-web`, crons commentés « PAUSE COMITE 15/11 (Sam) »).
- Journaux et scripts : `/root/smoke_185/` (pilote, `build/journal.log`, `build/resultat_*.txt`, `build/paquet/` = paquet rejoué, `build/dryrun.json`), `/root/smoke_186/`, `/root/smoke_sav/` (184), `/root/smoke_support/` (brief support client).

## 6. À reprendre (par priorité)

1. **Retry ciblé de Diego** : sur FAIL d'Elena, ne régénérer que les fichiers signalés (garder le reste), plafond 64 000 ; sinon la phase 2 ne converge pas. Option alternative : Opus pour le BUILD.
2. **Estimation GL-22** trop basse (6 720 annoncés pour ~9 000 réels) : le client qui accepte Opus bascule en Sonnet sans l'avoir choisi. Mieux estimer ou proposer un complément en cours d'exécution.
3. **Marcus/Olivia remplacent les champs existants** au lieu de les réutiliser ; doublon `Market_Signal__c`/`Signal_Marche__c` ; Raj crée `Score__c` à côté de `Score_Qualification__c`.
4. **Projet bloqué en `build_in_progress`** après un BUILD en échec : le client ne peut pas relancer (contourné ici par `approve-sds`).
5. **Reprise ARQ automatique au redémarrage du worker** (184 relancé seul, Marcus refait et payé deux fois, doublons UC).
6. **Appels d'Emma sans `execution_id`** en phase 4 (186) : passés en Sonnet et facturés hors SDS.
7. Annulation affichée `FAILED` au lieu de `CANCELLED` (184).
8. Worker : `/usr/local/bin/sfdx` 2.113 (« project retrieve start is not a sf command ») ; utiliser le CLI 2.157 (`/root/skills_sf/cli`).
9. Haiku figé en 4.5 (MOD40 signale la 5.5).
10. Cache : regrouper le contexte stable pour dépasser le seuil de mise en cache.
11. Agent Script non activé dans `sandbox-build` (Agentforce non déployable en l'état).
12. Supprimer les liens temporaires des SDS une fois récupérés par Sam.

Ensuite (approuvé, non commencé) : tests des modèles NVIDIA sur le Spark (Super VL 120B-A12B, Bolt) avec llama.cpp v1.0.0 compilé à part.
