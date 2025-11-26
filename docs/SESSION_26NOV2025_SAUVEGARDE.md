# SESSION 26 NOVEMBRE 2025 - SAUVEGARDE COMPLÈTE

## 📊 ÉTAT ACTUEL DU SYSTÈME

### Architecture V2 implémentée

```
┌─────────────────────────────────────────────────────────────┐
│                    DIGITAL HUMANS V2                         │
├─────────────────────────────────────────────────────────────┤
│  API V2 Endpoints                                           │
│  ├── /api/v2/artifacts      ✅ CRUD artifacts               │
│  ├── /api/v2/gates          ✅ 6 validation gates           │
│  ├── /api/v2/questions      ✅ inter-agent Q&A              │
│  ├── /api/v2/graph          ✅ dependency visualization     │
│  └── /api/v2/orchestrator   ✅ phase execution              │
├─────────────────────────────────────────────────────────────┤
│  Agents V2                                                  │
│  ├── PM Agent (Sophie)      ✅ orchestrateur                │
│  ├── BA Agent (Olivia)      ✅ BR + UC                      │
│  ├── Architect Agent (Marcus) ✅ ADR + SPEC                 │
│  └── Worker Agents          ⏳ À faire                      │
├─────────────────────────────────────────────────────────────┤
│  Database Tables                                            │
│  ├── execution_artifacts    ✅ créée                        │
│  ├── validation_gates       ✅ créée                        │
│  └── agent_questions        ✅ créée                        │
└─────────────────────────────────────────────────────────────┘
```

### Commits Git

Production (main): `4542949`
- https://github.com/SamHATIT/digital-humans-production

Gemini (main): `9c7dd7e`  
- https://github.com/SamHATIT/digital-humans-gemini

---

## ✅ TODO LIST - CE QUI RESTE À FAIRE

### 🔴 PRIORITÉ 1 : Test réel avec GPT-4

1. **Exécuter le workflow V2 complet**
   - Execution ID: 40 (déjà initialisée avec 6 gates)
   - Utiliser les requirements du projet 31 (concessionnaire auto)

2. **Étapes du test:**
   ```
   POST /api/v2/orchestrator/phase/pm-analysis
   → Vérifier REQ + PLAN créés
   
   POST /api/v2/orchestrator/phase/analysis  
   → Vérifier BR + UC créés
   → Vérifier PM review (REVIEW-001)
   
   POST /api/v2/orchestrator/gate/approve
   → Gate 1 approved
   
   POST /api/v2/orchestrator/phase/architecture
   → Vérifier itérations Q&A si besoin
   → Vérifier ADR + SPEC créés
   
   POST /api/v2/orchestrator/gate/approve
   → Gate 2 approved
   ```

3. **Comparer avec le SDS de ce matin** (note 4/10)
   - Est-ce plus spécifique ?
   - Y a-t-il des vrais objets Salesforce ?
   - Les Use Cases sont-ils détaillés ?

### 🟡 PRIORITÉ 2 : Agents Workers

1. **Diego (Apex Developer)** - Produit CODE artifacts
2. **Zara (LWC Developer)** - Produit CODE artifacts  
3. **Raj (Admin)** - Produit CONFIG artifacts
4. **Elena (QA)** - Produit TEST artifacts
5. **Jordan (DevOps)** - Validation déploiement
6. **Aisha (Data)** - Migration données
7. **Lucas (Trainer)** - Produit DOC artifacts

### 🟢 PRIORITÉ 3 : Interface Frontend

1. Page de visualisation des artifacts
2. Timeline des gates avec progression
3. Graphe de dépendances interactif
4. Interface de validation gates

### ⚪ PRIORITÉ 4 : Améliorations

1. Export SDS depuis artifacts (Word/PDF)
2. RAG integration dans les prompts agents
3. Notifications temps réel (SSE)
4. Historique des versions artifacts

---

## 📝 REQUIREMENTS POUR LE TEST

**Projet:** Réseau de concessionnaires automobiles
**Execution ID:** 40
**Project ID:** 31

### Texte complet:

```
Contexte métier : Gestion avancée de pipelines pour un réseau de concessionnaires automobiles

Un grand réseau de concessionnaires souhaite moderniser et automatiser la gestion de ses pipelines de vente, intégrant la vente de véhicules neufs et d'occasion, la gestion des reprises, le suivi des leads multicanal, des prévisions avancées et la personnalisation des offres (financement, assurances…).

________________________________________
Objectifs fonctionnels

• Permettre la saisie, le suivi et la qualification des leads via plusieurs canaux (site web, téléphone, email, portails partenaires).
• Automatiser la répartition intelligente des leads selon l'emplacement du véhicule, les disponibilités des vendeurs, et le scoring comportemental.
• Gérer des cycles de vente complexes incluant :
  o Plusieurs produits/groupes de produits par opportunité (ex. : véhicule + extensions + services complémentaires)
  o Reprise intégrée, avec workflow de soumission, estimation, acceptation/refus
  o Montage et simulation d'offres personnalisées (financement, contrats additionnels, assurance)
• Offrir un reporting consolidé par agence, marque, véhicule, segment client, et source de lead.
• Intégration de la gestion des territoires, avec prise en compte d'exceptions et de réaffectations dynamiques suivant les stocks.
• Automatiser la génération et l'envoi des devis contractuels adaptatifs, avec champs conditionnels selon la typologie de deal (ex. clause spéciale pour véhicule d'occasion > 5 ans).
• Workflow d'approbation multiniveau pour les remises exceptionnelles, les déstockages et les offres sur-mesure.
• Prévision commerciale dynamique, incluant réajustement automatique du pipeline selon taux de concrétisation réel.

________________________________________
Spécifications techniques

• Utilisation avancée des objets standards et personnalisés Salesforce pour modéliser véhicules, options, reprises, financements, et partenaires.
• Conception de processus automatisés (flows, process builder) pour :
  o Affectation automatique des leads
  o Calcul dynamique des marges selon la composition de l'offre
  o Déclenchement de notifications et validations à étapes multiples selon critères évolutifs
• Développement de composants Lightning Web Components pour l'édition des offres en mode "panier", intégrant calculs complexes et édition instantanée de l'offre globale.
• Intégration avec une solution externe d'estimation de reprise via API REST, synchronisation bidirectionnelle des statuts.
• Génération de documents PDF dynamiques avec branding multi-concession et engagement électronique.
• Sécurité : gestion des accès hiérarchisés selon type d'agence, rôle utilisateur, et scoping sur visibilité des opportunités/clients.
• Connecteurs pour synchronisation avec système DMS (gestion de stock, facturation, livraison) du concessionnaire.
• Reporting avancé avec tableaux de bord personnalisés, indicateurs temps réel sur la transformation des leads, alertes seuil et projections.

________________________________________
Contraintes et exigences complémentaires

• Multilinguisme (pilotage FR/EN/ES), adaptation automatique des modèles et documents.
• Suivi d'audit détaillé sur toutes les modifications d'offres et pipelines.
• Réversibilité des données en fin de projet.
• Formation des utilisateurs clés avec trame de tests qualité détaillée.
• Support de la continuité via sandbox full et procédure de rollback rapide.
```

---

## 🛠️ COMMANDES POUR CONTINUER

### Dans la prochaine conversation :

```bash
# 1. Vérifier l'état
curl -s "http://localhost:8002/api/v2/orchestrator/status/40" | python3 -m json.tool

# 2. Lancer Phase 0 (PM Analysis)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/pm-analysis" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40, "project_requirements": "[COLLER LES REQUIREMENTS]"}'

# 3. Lancer Phase 1 (BA)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/analysis" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 4. Approuver Gate 1
curl -X POST "http://localhost:8002/api/v2/orchestrator/gate/approve" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 5. Lancer Phase 2 (Architect)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/architecture" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'
```

---

## 📁 FICHIERS CLÉS

```
backend/
├── agents_v2/
│   ├── __init__.py
│   ├── base_agent.py         # Classe de base
│   ├── pm_agent.py           # Sophie (PM)
│   ├── ba_agent.py           # Olivia (BA)
│   ├── architect_agent.py    # Marcus (Architect)
│   └── orchestrator.py       # Coordination
├── app/
│   ├── api/routes/
│   │   ├── artifacts.py      # CRUD artifacts
│   │   └── orchestrator_v2.py # Phase endpoints
│   ├── models/
│   │   └── artifact.py       # SQLAlchemy models
│   ├── schemas/
│   │   └── artifact.py       # Pydantic schemas
│   └── services/
│       └── artifact_service.py # Business logic
```

---

## 📋 TRANSCRIPTS LIÉS

- `/mnt/transcripts/2025-11-26-12-28-06-architecture-refactoring-decisions-nov26.txt`
- `/mnt/transcripts/2025-11-26-13-29-03-architecture-v2-workflow-gemini-repo-sync.txt`

---

*Sauvegardé le 26 novembre 2025 à ~14:45 UTC*
