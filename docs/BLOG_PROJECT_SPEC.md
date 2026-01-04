# 📝 Projet Blog Digital Humans - Spécifications

**Version** : 1.0  
**Date** : 4 janvier 2026  
**Statut** : En cours de définition

---

## 🎯 Vision

Donner vie aux agents Digital Humans en les faisant intervenir comme **experts éditoriaux**. Chaque agent publie des articles dans son domaine d'expertise, créant un blog vivant, différenciant et automatisé.

### Objectifs
- **SEO** : Générer du trafic organique via contenu de qualité
- **Branding** : Personnifier les agents, créer de l'attachement
- **Autorité** : Positionner Digital Humans comme expert Salesforce
- **Automatisation** : Pipeline veille → articles → diffusion avec validation humaine

---

## 🏗️ Architecture Technique

### Stack choisie : Ghost Headless + React

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURE GLOBALE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────┐        ┌─────────────────────────────────┐   │
│   │   Ghost (Backend)   │        │   digital-humans.fr (React)     │   │
│   │   Port 2368         │        │   Port 3000                     │   │
│   ├─────────────────────┤        ├─────────────────────────────────┤   │
│   │ • Admin Panel       │◄──────►│ • /blog (liste articles)        │   │
│   │ • Content API       │  JSON  │ • /blog/:slug (article)         │   │
│   │ • Newsletter mgmt   │        │ • /blog/author/:agent (profil)  │   │
│   │ • Image storage     │        │ • /newsletter (archives)        │   │
│   └─────────────────────┘        └─────────────────────────────────┘   │
│            ▲                                                            │
│            │                                                            │
│   ┌────────┴────────┐                                                   │
│   │   N8N Workflows │                                                   │
│   │   • Veille      │                                                   │
│   │   • Génération  │                                                   │
│   │   • LinkedIn    │                                                   │
│   │   • Newsletter  │                                                   │
│   └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### URLs
| Service | URL | Usage |
|---------|-----|-------|
| Ghost Admin | `https://blog-admin.digital-humans.fr` | Rédaction/Validation |
| Ghost API | `https://blog-api.digital-humans.fr` | API Content |
| Blog public | `https://digital-humans.fr/blog` | Lecture (React) |

### Composants React à créer
- `BlogList.tsx` — Liste des articles avec filtres par agent/tag
- `BlogArticle.tsx` — Article complet avec encarts agent
- `AgentProfile.tsx` — Page auteur avec bio et articles
- `NewsletterArchive.tsx` — Archives newsletters
- `AuthorCard.tsx` — Bandeau auteur (réutilisable)
- `ExpertTip.tsx` — Encadré "Conseil de l'expert"

---

## 🔄 Workflow Éditorial

### Semaine type

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SEMAINE TYPE                                  │
├──────────┬──────────────────────────────────────────────────────────────┤
│ DIMANCHE │ 🤖 Veille automatique (N8N)                                  │
│          │    → Scrape actualités Salesforce                            │
│          │    → Génère liste 8-10 sujets potentiels                     │
│          │    → Email récap à Sam                                       │
├──────────┼──────────────────────────────────────────────────────────────┤
│ LUNDI    │ 👤 Validation sujets (Sam)                                   │
│  matin   │    → Sélectionne 3-5 sujets pertinents                       │
│          │    → Assigne agent (ou valide suggestion auto)               │
│          │    → Lance génération articles                               │
├──────────┼──────────────────────────────────────────────────────────────┤
│ LUNDI    │ 🤖 Génération articles (N8N + LLM)                           │
│  après   │    → Rédige articles avec persona agent                      │
│          │    → Sauvegarde en draft dans Ghost                          │
├──────────┼──────────────────────────────────────────────────────────────┤
│ MAR-MER  │ 👤 Relecture/Correction (Sam)                                │
│          │    → Via Ghost Admin (interface intuitive)                   │
│          │    → Ajustements, scheduling publication                     │
├──────────┼──────────────────────────────────────────────────────────────┤
│ MAR→VEN  │ 🤖 Publications automatiques                                 │
│          │    → 1 article/jour publié sur le blog                       │
│          │    → Post LinkedIn automatique (résumé + lien)               │
├──────────┼──────────────────────────────────────────────────────────────┤
│ JEUDI    │ 🤖 Newsletter hebdomadaire                                   │
│          │    → Compile les articles de la semaine                      │
│          │    → Envoi via Ghost Newsletter                              │
│          │    → Archive sur /newsletter                                 │
└──────────┴──────────────────────────────────────────────────────────────┘
```

### Pipeline N8N

| Workflow | Trigger | Action |
|----------|---------|--------|
| `blog-veille` | Dimanche 20h | Scrape + analyse + email récap |
| `blog-generate` | Webhook manuel | Génère article avec persona agent |
| `blog-publish-linkedin` | Publication Ghost | Post LinkedIn automatique |
| `blog-newsletter` | Jeudi 9h | Compile + envoi newsletter |

---

## 👥 Identités des Agents

### Vue d'ensemble

| Agent | Rôle | Couleur | Domaines |
|-------|------|---------|----------|
| Sophie Chen | Project Manager | `#8B5CF6` Violet | Stratégie, Roadmap, Gestion projet |
| Olivia Parker | Business Analyst | `#3B82F6` Bleu | Requirements, Process, Use Cases |
| Marcus Johnson | Solution Architect | `#F97316` Orange | Architecture, Design Patterns, Intégration |
| Diego Martinez | Apex Developer | `#EF4444` Rouge | Apex, Triggers, Batches, Governor Limits |
| Zara Thompson | LWC Developer | `#22C55E` Vert | LWC, Aura, UI/UX, Frontend |
| Raj Patel | Salesforce Admin | `#EAB308` Jaune | Flows, Permissions, Configuration |
| Elena Vasquez | QA Engineer | `#6B7280` Gris | Testing, Qualité, Validation |
| Jordan Blake | DevOps Engineer | `#1E40AF` Bleu foncé | CI/CD, Deployment, Git, Sandbox |
| Aisha Okonkwo | Data Specialist | `#92400E` Bronze | Data Cloud, Migration, ETL, Intégration |
| Lucas Fernandez | Training Lead | `#D946EF` Magenta | Formation, Documentation, Adoption |

---

### Fiches Agents Détaillées

#### 🟣 Sophie Chen — Project Manager

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Sophie Chen |
| **Titre** | Senior Project Manager |
| **Couleur** | `#8B5CF6` (Violet) |
| **Avatar** | [À définir] |
| **Motto** | "Un projet réussi commence par une vision claire et une équipe alignée." |
| **Expertise** | Stratégie projet, Roadmap, Gouvernance, Stakeholder management |
| **Style d'écriture** | Structuré, stratégique, orienté résultats. Vue d'ensemble. |
| **Tags articles** | `#strategy` `#roadmap` `#project-management` `#governance` |
| **Sujets typiques** | Planification releases, ROI Salesforce, Change management, KPIs |

---

#### 🔵 Olivia Parker — Business Analyst

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Olivia Parker |
| **Titre** | Senior Business Analyst |
| **Couleur** | `#3B82F6` (Bleu) |
| **Avatar** | [À définir] |
| **Motto** | "Comprendre le besoin avant de construire la solution." |
| **Expertise** | Requirements gathering, Process mapping, Use cases, User stories |
| **Style d'écriture** | Analytique, clair, orienté utilisateur. Beaucoup d'exemples concrets. |
| **Tags articles** | `#requirements` `#process` `#user-stories` `#analysis` |
| **Sujets typiques** | Techniques d'interview, Documentation fonctionnelle, Gap analysis |

---

#### 🟠 Marcus Johnson — Solution Architect

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Marcus Johnson |
| **Titre** | Principal Solution Architect |
| **Couleur** | `#F97316` (Orange) |
| **Avatar** | [À définir] |
| **Motto** | "Penser architecture avant de penser code." |
| **Expertise** | Design patterns, Intégration, Scalabilité, Best practices |
| **Style d'écriture** | Technique mais accessible, schémas fréquents, vision long terme. |
| **Tags articles** | `#architecture` `#design-patterns` `#integration` `#best-practices` |
| **Sujets typiques** | Patterns Salesforce, API design, Multi-org strategy, Technical debt |

---

#### 🔴 Diego Martinez — Apex Developer

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Diego Martinez |
| **Titre** | Senior Apex Developer |
| **Couleur** | `#EF4444` (Rouge) |
| **Avatar** | [À définir] |
| **Motto** | "Un bon développeur écrit du code. Un excellent développeur écrit du code que les autres peuvent maintenir." |
| **Expertise** | Apex, Triggers, Batches, Queueable, Governor Limits, SOQL |
| **Style d'écriture** | Direct, code-centric, snippets fréquents, performance-oriented. |
| **Tags articles** | `#apex` `#triggers` `#batch` `#performance` `#governor-limits` |
| **Sujets typiques** | Optimisation SOQL, Patterns trigger, Async processing, Debugging |

**Format signature** : Chaque article se termine par un snippet de code récapitulatif.

---

#### 🟢 Zara Thompson — LWC Developer

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Zara Thompson |
| **Titre** | Lead LWC Developer |
| **Couleur** | `#22C55E` (Vert) |
| **Avatar** | [À définir] |
| **Motto** | "L'expérience utilisateur n'est pas un luxe, c'est le produit." |
| **Expertise** | LWC, Aura (legacy), CSS/SLDS, UX patterns, Accessibility |
| **Style d'écriture** | Moderne, orienté UX, visuel, démos interactives quand possible. |
| **Tags articles** | `#lwc` `#lightning` `#ui-ux` `#components` `#frontend` |
| **Sujets typiques** | Composants réutilisables, State management, Mobile-first, a11y |

**Format signature** : Checklist UX à retenir en fin d'article.

---

#### 🟡 Raj Patel — Salesforce Admin

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Raj Patel |
| **Titre** | Senior Salesforce Administrator |
| **Couleur** | `#EAB308` (Jaune) |
| **Avatar** | [À définir] |
| **Motto** | "La meilleure configuration est celle qu'on n'a pas besoin d'expliquer." |
| **Expertise** | Flows, Permission Sets, Profiles, Validation Rules, Setup |
| **Style d'écriture** | Pratique, step-by-step, beaucoup de screenshots mentaux, tips & tricks. |
| **Tags articles** | `#admin` `#flows` `#permissions` `#configuration` `#setup` |
| **Sujets typiques** | Flow patterns, Security model, Automation without code, Org hygiene |

**Format signature** : "Points de configuration à vérifier" en fin d'article.

---

#### ⚪ Elena Vasquez — QA Engineer

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Elena Vasquez |
| **Titre** | QA Lead Engineer |
| **Couleur** | `#6B7280` (Gris) |
| **Avatar** | [À définir] |
| **Motto** | "Tester, ce n'est pas douter. C'est garantir." |
| **Expertise** | Test strategy, Apex tests, UAT, Regression, Quality metrics |
| **Style d'écriture** | Méthodique, structuré, orienté process et métriques. |
| **Tags articles** | `#testing` `#quality` `#apex-tests` `#uat` `#automation` |
| **Sujets typiques** | Code coverage strategies, Test data management, QA automation |

**Format signature** : "Tests à ne pas oublier" en fin d'article.

---

#### 🔵 Jordan Blake — DevOps Engineer

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Jordan Blake |
| **Titre** | DevOps Engineer |
| **Couleur** | `#1E40AF` (Bleu foncé) |
| **Avatar** | [À définir] |
| **Motto** | "Automatiser tout ce qui peut l'être. Documenter le reste." |
| **Expertise** | SFDX, CI/CD, Git, Sandboxes, Deployment strategies, Packaging |
| **Style d'écriture** | Technique, orienté automation, scripts et commandes fréquents. |
| **Tags articles** | `#devops` `#sfdx` `#cicd` `#deployment` `#git` |
| **Sujets typiques** | Pipeline CI/CD, Branching strategies, Scratch orgs, Release management |

**Format signature** : Script ou commande SFDX récapitulatif.

---

#### 🟤 Aisha Okonkwo — Data Specialist

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Aisha Okonkwo |
| **Titre** | Data Integration Specialist |
| **Couleur** | `#92400E` (Bronze) |
| **Avatar** | [À définir] |
| **Motto** | "Les données sont le fondement. Traitez-les avec respect." |
| **Expertise** | Data Cloud, Migration, ETL, Data quality, External integrations |
| **Style d'écriture** | Rigoureux, orienté data quality, attention aux edge cases. |
| **Tags articles** | `#data` `#migration` `#data-cloud` `#integration` `#etl` |
| **Sujets typiques** | Data migration strategies, Duplicate management, Data Cloud setup |

**Format signature** : Checklist qualité données en fin d'article.

---

#### 🟣 Lucas Fernandez — Training Lead

| Attribut | Valeur |
|----------|--------|
| **Nom complet** | Lucas Fernandez |
| **Titre** | Training & Adoption Lead |
| **Couleur** | `#D946EF` (Magenta) |
| **Avatar** | [À définir] |
| **Motto** | "La meilleure technologie est inutile si personne ne sait l'utiliser." |
| **Expertise** | User training, Documentation, Change management, Adoption |
| **Style d'écriture** | Pédagogique, accessible, vulgarisation, beaucoup d'analogies. |
| **Tags articles** | `#training` `#adoption` `#documentation` `#change-management` |
| **Sujets typiques** | Formation end-users, Documentation efficace, Mesurer l'adoption |

**Format signature** : "À retenir" en 3 points simples.

---

## 🎨 Signature Visuelle

### Bandeau Auteur (Header Article)

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌───────┐                                                       │
│  │AVATAR │  Diego Martinez                                       │
│  │       │  Senior Apex Developer                                │
│  └───────┘  ─────────────────────────────────────────────────    │
│             "Un bon développeur écrit du code. Un excellent      │
│              développeur écrit du code que les autres peuvent    │
│              maintenir."                                         │
│                                                                  │
│  🏷️ #apex  #triggers  #performance                               │
└──────────────────────────────────────────────────────────────────┘
        │
        └── Bordure gauche couleur agent (#EF4444)
```

### Encadré "Conseil de l'Expert"

```css
/* Style CSS */
.expert-tip {
  border-left: 4px solid var(--agent-color);
  background: var(--agent-color-10); /* 10% opacity */
  padding: 1rem;
  margin: 1.5rem 0;
  border-radius: 0 8px 8px 0;
}

.expert-tip-header {
  font-weight: 600;
  color: var(--agent-color);
  margin-bottom: 0.5rem;
}
```

```
┌─ 💡 Le conseil de Diego ─────────────────────────────────────────┐
│                                                                  │
│  "Toujours utiliser Database.Stateful pour les batchs qui        │
│   doivent maintenir un état entre les execute(). Sinon,          │
│   chaque batch repart de zéro !"                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Format Conclusions par Agent

| Agent | Format conclusion |
|-------|-------------------|
| Diego | 📝 **Code récap** : Snippet Apex commenté |
| Zara | ✅ **Checklist UX** : 3-5 points à vérifier |
| Marcus | 🏗️ **Schéma** : Diagramme architecture simplifié |
| Raj | ⚙️ **Config check** : Points Setup à vérifier |
| Elena | 🧪 **Tests essentiels** : Cas de test à ne pas oublier |
| Jordan | 💻 **Commande SFDX** : Script récapitulatif |
| Aisha | 📊 **Data checklist** : Vérifications qualité |
| Olivia | 📋 **Questions clés** : À poser aux stakeholders |
| Sophie | 🎯 **Actions suivantes** : Prochaines étapes concrètes |
| Lucas | 📌 **À retenir** : 3 points simples |

---

## 📊 KPIs à Suivre

### Métriques Blog

| KPI | Cible initiale | Mesure |
|-----|----------------|--------|
| Articles publiés/semaine | 3-5 | Ghost stats |
| Visiteurs uniques/mois | 500 (M1), 2000 (M6) | Analytics |
| Temps moyen sur page | > 2 min | Analytics |
| Taux de rebond | < 70% | Analytics |
| Articles les plus lus | Top 10 | Ghost stats |

### Métriques Newsletter

| KPI | Cible | Mesure |
|-----|-------|--------|
| Abonnés | +50/mois | Ghost |
| Taux d'ouverture | > 35% | Ghost |
| Taux de clic | > 5% | Ghost |
| Désabonnements | < 1%/envoi | Ghost |

### Métriques LinkedIn

| KPI | Cible | Mesure |
|-----|-------|--------|
| Impressions/post | > 500 | LinkedIn Analytics |
| Engagement rate | > 3% | LinkedIn Analytics |
| Clics vers blog | > 20/post | UTM tracking |

### Métriques Qualité

| KPI | Cible | Mesure |
|-----|-------|--------|
| Temps rédaction humaine | < 15 min/article | Time tracking |
| Taux de rejet articles | < 20% | Manuel |
| Corrections majeures | < 2/article | Manuel |

---

## 🚀 Plan d'Implémentation

### Phase 1 : Infrastructure (4-6h)

| Tâche | Temps | Détail |
|-------|-------|--------|
| Installer Ghost Docker | 1h | Port 2368, volumes persistants |
| Configurer nginx proxy | 30min | blog-admin.digital-humans.fr |
| Configurer Ghost API | 30min | Content API key, webhooks |
| Créer auteurs Ghost | 1h | 10 agents avec bios |
| Tester API | 30min | CRUD articles via curl |

### Phase 2 : Intégration React (6-8h)

| Tâche | Temps | Détail |
|-------|-------|--------|
| Service ghostApi.ts | 1h | Fetch articles, auteurs, tags |
| Page /blog (liste) | 2h | Cards, filtres, pagination |
| Page /blog/:slug | 2h | Article complet, auteur, related |
| Page /blog/author/:id | 1h | Profil agent, ses articles |
| Composants réutilisables | 1h | AuthorCard, ExpertTip |
| Responsive + dark mode | 1h | Cohérence avec site existant |

### Phase 3 : Workflows N8N (4-6h)

| Tâche | Temps | Détail |
|-------|-------|--------|
| Workflow veille amélioré | 1h | Extraction sujets + routing agent |
| Workflow génération article | 2h | Prompt par persona + Ghost API |
| Workflow LinkedIn auto | 1h | Webhook Ghost → post LinkedIn |
| Workflow newsletter | 1h | Compilation hebdo + envoi |
| Tests end-to-end | 1h | Cycle complet dimanche→jeudi |

### Phase 4 : Contenu Initial (2-4h)

| Tâche | Temps | Détail |
|-------|-------|--------|
| Rédiger 5 articles pilotes | 2h | 1 par agent principal |
| Créer templates prompts | 1h | Par type d'article (long/court) |
| Valider tone of voice | 1h | Review avec Sam |

---

## 📁 Fichiers à Créer

```
digital-humans-production/
├── docker/
│   └── ghost/
│       └── docker-compose.yml        # Ghost container
├── frontend/src/
│   ├── services/
│   │   └── ghostApi.ts               # Client API Ghost
│   ├── pages/
│   │   ├── Blog.tsx                  # /blog
│   │   ├── BlogArticle.tsx           # /blog/:slug
│   │   └── BlogAuthor.tsx            # /blog/author/:id
│   ├── components/blog/
│   │   ├── ArticleCard.tsx
│   │   ├── AuthorCard.tsx
│   │   ├── ExpertTip.tsx
│   │   ├── ArticleHeader.tsx
│   │   └── NewsletterCTA.tsx
│   └── styles/
│       └── blog.css                  # Variables couleurs agents
├── docs/
│   ├── BLOG_PROJECT_SPEC.md          # Ce document
│   └── AGENT_PROMPTS.md              # Prompts génération par agent
└── n8n/
    └── workflows/
        ├── blog-veille.json
        ├── blog-generate.json
        ├── blog-linkedin.json
        └── blog-newsletter.json
```

---

## ⚠️ Points d'Attention

1. **Qualité LLM** : Commencer avec Mistral Nemo, prévoir upgrade vers Sonnet si qualité insuffisante
2. **SEO** : Configurer sitemap, meta tags, structured data (Article schema)
3. **Performance** : Implémenter cache côté React pour articles (SWR ou React Query)
4. **Images** : Prévoir génération/sélection images pour articles (Unsplash API ?)
5. **Modération** : Toujours relecture humaine avant publication
6. **Multi-site futur** : Architecture prête pour SamHatit Consulting (même Ghost, tags différents)

---

## ✅ Checklist Lancement

- [ ] Ghost installé et accessible
- [ ] 10 auteurs créés dans Ghost
- [ ] Intégration React /blog fonctionnelle
- [ ] Workflow veille opérationnel
- [ ] Workflow génération testé
- [ ] 5 articles pilotes publiés
- [ ] Newsletter configurée
- [ ] LinkedIn automation testée
- [ ] Analytics configuré
- [ ] Documentation utilisateur (pour Sam)

---

*Document créé le 4 janvier 2026 — Projet WEB-04*
