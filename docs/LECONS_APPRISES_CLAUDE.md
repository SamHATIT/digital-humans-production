# Leçons Apprises - Méthode de Travail Claude

**Créé** : 4 décembre 2025
**Mis à jour** : En continu

---

## 🔴 Erreurs à Ne Plus Répéter

### 1. Dire "c'est fait" sans tester réellement
- **Problème** : J'ai affirmé que la génération DOCX était corrigée, mais je n'ai pas vérifié qu'elle fonctionnait en conditions réelles
- **Solution** : Toujours tester le code après modification, même si ça semble fonctionner en théorie
- **Règle** : Pas de "c'est corrigé" sans preuve concrète (log, fichier généré, test API)

### 2. Ne pas vérifier la cohérence frontend/backend
- **Problème** : Le frontend appelle `/api/projects/{id}` mais cet endpoint n'existe pas
- **Solution** : Avant de développer un frontend, lister les endpoints requis et vérifier qu'ils existent
- **Règle** : Pour chaque page frontend, documenter les endpoints utilisés et les tester

### 3. Études d'impact superficielles
- **Problème** : J'ai fait des "études d'impact" qui n'ont pas identifié les vrais problèmes
- **Solution** : Une étude d'impact doit inclure :
  - Test réel du code modifié
  - Vérification des dépendances (qui appelle quoi)
  - Simulation du parcours utilisateur complet
- **Règle** : Une étude d'impact sans test = pas d'étude d'impact

### 4. Fallback silencieux qui masque les erreurs
- **Problème** : Le fallback Markdown cache l'échec de génération DOCX
- **Solution** : Logger clairement les erreurs, ne pas "réussir" silencieusement avec un résultat dégradé sans avertissement
- **Règle** : Un fallback doit toujours loguer un WARNING visible

---

## ✅ Bonnes Pratiques à Maintenir

### 1. Database-first
- Les données en DB permettent de regénérer sans relancer tout le workflow
- Exemple : On peut régénérer le SDS depuis les deliverables sans refaire les appels API agents

### 2. Commits fréquents avec messages clairs
- Permet de tracer ce qui a été fait et quand

### 3. Documentation des sessions (CR)
- Aide à la continuité entre sessions

---

## 📋 Checklist Avant de Dire "C'est Fait"

- [ ] Le code compile/s'exécute sans erreur
- [ ] J'ai testé manuellement le cas nominal
- [ ] J'ai testé au moins un cas d'erreur
- [ ] Les logs montrent le comportement attendu
- [ ] Les endpoints frontend ont leur backend correspondant
- [ ] Pas de fallback silencieux qui masque des erreurs


---

## 📝 TODO - Prochaine Session

### Troncature des descriptions dans les tableaux SDS
- **Problème** : Les colonnes "Description" dans les tableaux Word sont tronquées (ex: "Apex service layer for AI integration, conver...")
- **Cause** : Le code limite les textes avec `[:50]`, `[:60]`, `[:80]` etc.
- **Solution** : Soit augmenter les limites, soit utiliser des cellules multi-lignes, soit mettre les descriptions complètes en dehors des tableaux
- **Fichier** : `/backend/app/services/document_generator.py`

