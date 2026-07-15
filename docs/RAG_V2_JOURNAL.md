# RAG V2 — Journal des décisions (annexe vivante de GUIDELINE_RAG_VEILLE_SF.md)

| Date | Décision | Justification / preuve |
|---|---|---|
| 12/07 | Abandon ré-ingestion complète du corpus existant | Baseline hit@5 92% global (results_v1_baseline.json) — kill switch |
| 12/07 | Pipeline v2 sur contenu neuf uniquement (~9 270 p.) | Idem ; levier n°1 = apex_collection 1 594 chunks → x5-10 via Apex Ref Guide |
| 12/07 | Défense anti-obsolescence 4 couches ; couche 2 (platform_state) livrée en premier | Gate 0bis mergé badf5b8, test réel Sonnet 5 : with sharing généré |
| 12/07 | Veille : N8N + CDN resources.docs.salesforce.com (206/404 versionnés), pas d agent navigateur | Tests HTTP du 12/07 ; RN seules = récup manuelle (404 CDN) |
| 12/07 | Fix certif CDN : bundle intermédiaire DigiCert (sf_ca_bundle.pem), jamais -k | Chaîne incomplète servie par Akamai, prouvé openssl |
| 12/07 | **PARSE = docling** ; pypdf écarté (fallback urgence) ; Zparse clos | Triple-test pilote : docling 53 tables MD reconstruites, 0 header intercalé, 2,3 s/p CPU ; pypdf tables éclatées + 31 headers/tranche ; Zparse trial sans template PDF turnkey (friction >> valeur), clauses réversibilité §6 guideline inchangées |
| 12/07 | Qualité Haiku validée pour METADATA/SCORE/contexte | Pilote 45 chunks : scoring discriminant (2 copyright → 9 release update), contextes pertinents |
| 12/07 | Fix METADATA : croiser titre pdfinfo + filename + premières pages ; injecter platform_state dans les prompts pipeline | Tranche RN mal classée (départ p.145) ; Haiku a écrit « Data Cloud » au lieu de « Data 360 » |
| 12/07 | Seuil de drop scoring : < 3 (au lieu de < 4) pour le full run, garde-fou 5-25% juge en dernier | Échantillon pilote : <4 droppait 29% (biais chapitre intro) |
| 12/07 | **Plan coût full run < 10 €** : contexte déterministe par chemin de titres pour les guides de référence (77% du volume, 0 appel), 1 appel combiné contexte+score, Batch API -50%, cache ≥ 2 048 tokens | Pilote : cache non engagé (bloc 1,5K < min 2 048) → extrapolation 90 $ sans cache ; référence embedding avril ~0,32 $/9 900 chunks |
| 14/07 | **BASCULE PROD corpus v2 — validée par Sam.** Mécanisme : drop-in systemd `chroma-v2.conf` (DH_CHROMA_PATH → chromadb_v2, 161 856 chunks). Rollback : suppression du drop-in + restart (~30 s). `chromadb_data` (v1, 2,9 G) conservée en backup froid — ne pas supprimer avant fin de période de recouvrement (proposition : post-Winter 27). Réserve APEX-09 maintenue au journal. Preuves : Gate 2 stratifié (96 % global, 100 % release-sensitive), Gate 3 SDS 162 (marqueurs Summer 26 dans le livrable), RAG HEALTH OK en continu depuis le 13/07. |
