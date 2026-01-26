# Digital Humans - État Actuel

**Dernière mise à jour:** 26 janvier 2026

---

## ⚠️ État Réel du Projet

| Domaine | État | Commentaire |
|---------|------|-------------|
| **SDS** | 🟡 Partiel | Pipeline existe, génère documents, mais qualité insuffisante pour client |
| **BUILD** | 🔴 Non validé | Code jamais déployé sur Salesforce réel |
| **Tests** | 🔴 Aucun | Aucun test end-to-end validé sur org SF |
| **Coûts** | 🟡 Élevés | ~10-12€/SDS, BUILD inconnu |
| **Business** | 🔴 Incomplet | Pas de SIRET, paiement, facturation |

---

## 📊 Métriques Features

| Métrique | Valeur |
|----------|--------|
| Features totales | 172 |
| Complétées | 142 (83%) |
| En cours | SDS v3 micro-analyse |

---

## 🎯 Priorité P0 : SDS v3 Micro-Analyse

**Objectif:** Réduire coût de 10-12€ à ~2€ + améliorer qualité

### Progression

| Étape | Action | Durée est. | Statut |
|-------|--------|------------|--------|
| 1 | `llm_router_service.py` + config YAML | 2h | ✅ Done |
| 2 | Table `uc_requirement_sheets` | 30min | ✅ Done |
| 3 | Prompt "Fiche Besoin" pour Nemo | 1h | ✅ Done |
| 4 | Tester sur 5+ UCs avec Nemo | 30min | ✅ Done (8 UCs) |
| 5 | Créer prompt synthèse Claude | 1h | ⏳ À faire |
| 6 | Tester synthèse sur les fiches | 15min | ⏳ À faire |
| 7 | Comparer qualité avec SDS v2 | 30min | ⏳ À faire |

**Résultat test étape 4:** 8/8 UCs analysés, 18 min, $0 (Mistral local)

---

## 🚧 Ce qui manque pour commercialiser

### Côté Client (B2B)
- [ ] Profil entreprise (SIRET, TVA, adresse facturation)
- [ ] Gestion multi-utilisateurs par entreprise
- [ ] Rôles/permissions (admin, utilisateur, viewer)

### Côté Monétisation
- [ ] Système de paiement (Stripe)
- [ ] Facturation automatique
- [ ] Gestion abonnements (free/premium)
- [ ] Système tokens/crédits pour LLM
- [ ] Suivi consommation temps réel

### Côté Produit
- [ ] Qualité SDS suffisante pour facturer
- [ ] BUILD validé en production SF
- [ ] Success story démontrable

---

## 🔧 Services Actifs

| Service | Port | État |
|---------|------|------|
| Backend FastAPI | 8002 | ✅ |
| Frontend React | 3000 | ✅ |
| PostgreSQL | 5432 | ✅ |
| Ollama (Mistral) | 11434 | ✅ |
| Ghost CMS | 2368 | ✅ |
| N8N | 5678 | ✅ |

---

## 🚀 Commandes Rapides

```bash
# Vérifier services
curl -s http://localhost:8002/health
curl -s http://localhost:11434/api/tags | jq

# Token user 2 (expire 27/01)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzY5NTM4ODI3fQ.ezj-NJnptM6K0yIrFjhPV5JbSt8V-v6tsSLZ_jSjqCI"

# Micro-analyse
curl -X POST "http://localhost:8002/api/pm-orchestrator/execute/{id}/microanalyze" -H "Authorization: Bearer $TOKEN"

# Consulter fiches générées
curl "http://localhost:8002/api/pm-orchestrator/execute/{id}/requirement-sheets" -H "Authorization: Bearer $TOKEN"
```

---

*Historique complet: `docs/archives/`*
