# BRIEFING AGENT D — Hygiene & Cleanup

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md`
**Branches Claude Code** : `chore/agent-d-cleanup`

---

## 1. Mission

Nettoyer les **dettes de maintenance** accumulées : chemins hardcodés, fichiers backup traînants, code mort, imports inutiles, secrets en dur, docs obsolètes. Travail peu glamour mais qui réduit la surface d'attaque et la charge cognitive des futurs développements.

**Objectif concret** : après ce chantier, le repo est **propre** — pas de `.backup_*`, pas de chemins `/home/sam/...`, pas de dead code orphelin, pas de secrets en clair, pas de F401, CHANGELOG à jour.

**Critère de sortie** : un nouveau contributeur peut cloner le repo et comprendre l'état courant en lisant uniquement `README.md` + `docs/architecture.md` + `CHANGELOG.md` (pas besoin de lire l'audit v3).

---

## 2. Périmètre & inventaire

### Chantier P2 — Chemins absolus hardcodés (52 occurrences)

À trouver par grep :
```bash
cd backend
grep -rn "/root/\|/home/\|/tmp/.*/digital-humans\|C:\\\\" --include="*.py" --exclude-dir=venv --exclude-dir=__pycache__ | head -60
```

**Types à traiter** :
- Paths absolus dans des strings (`"/root/workspace/..."`)
- `Path("/home/...")` littéraux
- `subprocess.run(["/usr/bin/..."])` → remplacer par `shutil.which` ou var env
- Paths Windows dans des fallbacks (si existants)

**Pattern de remplacement** :
```python
# AVANT
CHROMA_PATH = "/root/workspace/digital-humans-production/backend/rag_chroma_db"

# APRÈS
from app.config import settings
CHROMA_PATH = settings.CHROMA_PATH  # lu depuis env var avec default relatif
```

Dans `app/config.py`, ajouter un resolveur robuste :
```python
from pathlib import Path
import os

class Settings:
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    @property
    def CHROMA_PATH(self) -> Path:
        return Path(os.environ.get("DH_CHROMA_PATH", self.BASE_DIR / "rag_chroma_db"))

    @property
    def RAG_ENV_PATH(self) -> Path:
        return Path(os.environ.get("DH_RAG_ENV_PATH", self.BASE_DIR / ".env.rag"))

    @property
    def LLM_CONFIG_PATH(self) -> Path:
        return Path(os.environ.get("DH_LLM_CONFIG_PATH", self.BASE_DIR / "config/llm_routing.yaml"))

    # ...
```

---

### Chantier backup files (Méta-3)

**Fichiers à supprimer** :
```bash
backend/app/services/pm_orchestrator_service.py.backup_artifacts   # 43K
backend/app/services/rag_service.py.backup_pre_bug043              # 12K
```

**Procédure** :
1. Vérifier que le contenu est bien sauvegardé dans git history (pas unique) :
   ```bash
   git log --all --full-history -- app/services/pm_orchestrator_service.py.backup_artifacts
   ```
2. Si couvert par git : `rm` + commit
3. Si pas couvert : créer un tag `legacy/backup-snapshot-20260418` sur le commit courant avant suppression

**DoD** : `find backend -name "*.backup*"` retourne 0 résultat.

---

### Chantier dead code (SDS V3 endpoints orphelins)

**Fichiers** : `backend/app/api/routes/orchestrator/sds_v3_routes.py` (728 L)

**Finding** : 6 endpoints sur 8 ne sont jamais appelés par le frontend (confirmé via `grep sds_v3 frontend/src/services/api.ts` qui ne matche que `/generate-sds-v3` et `/download-sds-v3`).

**Endpoints orphelins** (à décider : supprimer ou conserver pour debug) :
- `POST /execute/{id}/microanalyze`
- `GET /execute/{id}/requirement-sheets`
- `POST /execute/{id}/synthesize`
- `GET /execute/{id}/sds-preview`
- `GET /execute/{id}/domains-summary`
- `POST /execute/{id}/generate-docx`

**DÉCISION SAM (2026-04-18)** : **suppression pure et simple** des 6 endpoints orphelins + du service `sds_synthesis_service.py`. Le pipeline SDS V3 Mistral PASS 1 n'est pas activé et ne le sera pas dans ce cycle. Si besoin futur, restauration depuis git history.

**Endpoints à supprimer** :
- `POST /execute/{id}/microanalyze`
- `GET /execute/{id}/requirement-sheets`
- `POST /execute/{id}/synthesize`
- `GET /execute/{id}/sds-preview`
- `GET /execute/{id}/domains-summary`
- `POST /execute/{id}/generate-docx`

**Fichiers à supprimer** :
- `backend/app/services/sds_synthesis_service.py` (528 L)
- Les 6 endpoints dans `backend/app/api/routes/orchestrator/sds_v3_routes.py` — le fichier conserve uniquement les 2 endpoints actifs (`/generate-sds-v3` et `/download-sds-v3`)

**Procédure** :
```bash
# Tag avant suppression (safety net)
git tag legacy/sds_v3_synthesis_before_removal

# Suppression
git rm backend/app/services/sds_synthesis_service.py
# Puis éditer sds_v3_routes.py pour retirer les 6 endpoints orphelins
```

**Validation post-suppression** :
```bash
# Le frontend ne doit plus référencer ces endpoints
grep -rn "microanalyze\|requirement-sheets\|synthesize\|sds-preview\|domains-summary\|generate-docx" frontend/src --include="*.ts" --include="*.tsx"
# Doit retourner 0 lignes
```

---

### Chantier dead methods (N17e, N19a)

**Fichier** : `backend/agents/roles/salesforce_qa_tester.py`

- **N17e** : `QATesterAgent._execute_test` (L752-770) : après le fix A-2 du briefing A qui ajoute le dispatch dans `run()`, cette méthode devient **vivante**. Ne pas la supprimer.

**Fichier** : `backend/agents/roles/salesforce_trainer.py`

- **N19a** : les 2 `get_sds_strategy_prompt` et `get_delivery_prompt` (L46-57, L156-166) ont un `return f'''...'''` après un `return PROMPT_SERVICE.render(...)` — **code mort**. Supprimer les blocs `# FALLBACK: original f-string prompt` et leurs contenus.

---

### Chantier imports inutilisés (F401)

**Commande** :
```bash
cd backend && . venv/bin/activate
ruff check --select F401 --exclude venv,__pycache__,tests,migrations . 2>&1 | grep -E "^F401" | head -30
```

**Pattern de fix** : pour chaque F401, soit retirer l'import, soit marquer `# noqa: F401` avec commentaire expliquant (ex: re-export public API).

**Cas particulier** : `artifact_service.py` ligne 12 `ArtifactType` importé mais jamais utilisé — supprimer. Si utilisé pour re-export, ajouter `# noqa: F401 - re-export`.

---

### Chantier rotation secrets (P8)

**Statut actuel** : secrets probablement dans `backend/.env` ou dans systemd unit file. Pas de rotation automatique.

**Livrables attendus** :
1. `docs/operations/secrets-rotation.md` — procédure manuelle documentée
2. Liste des secrets critiques inventoriés :
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY` (si gardé pour future)
   - `DATABASE_URL` (password)
   - `JWT_SECRET_KEY`
   - `GITHUB_TOKEN` (pour `jordan_deploy_service`)
   - `SALESFORCE_ACCESS_TOKEN` (SFDX auth JWT)
3. Script `scripts/rotate_anthropic_key.sh` qui :
   - Prend un nouveau key en argument
   - Le place dans l'env (via secret manager si dispo, sinon `.env`)
   - Restart systemd services
   - Teste un appel Anthropic
   - Rollback automatique si test fail

**Note** : intégration secret manager (Vault / AWS Secrets Manager) hors scope de ce chantier. Documenter comme "next step" dans `docs/operations/secrets-rotation.md`.

---

### Chantier logs fragmentés (P5)

**Problème** : chaque agent loggue avec son propre format. Journalctl mélange :
- `[Sophie]` / `[CR Service]` / `[PhasedBuild]` (préfixes inconsistants)
- Certains en INFO, d'autres en DEBUG pour des infos équivalentes
- Pas de request_id / execution_id systématique

**Livrables attendus** :
1. Dans `app/utils/logging_config.py`, définir un formatter centralisé qui injecte :
   - `timestamp` ISO8601
   - `level`
   - `logger_name`
   - `execution_id` (via contextvars si présent)
   - `agent_id` (via contextvars si présent)
   - `message`

2. Middleware FastAPI qui set `execution_id` dans contextvars sur chaque request ayant `{execution_id}` dans l'URL :
   ```python
   from contextvars import ContextVar
   from starlette.middleware.base import BaseHTTPMiddleware
   import re

   _execution_id_var: ContextVar[int] = ContextVar("execution_id", default=None)

   class ExecutionContextMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request, call_next):
           match = re.search(r"/execute/(\d+)", request.url.path)
           if match:
               token = _execution_id_var.set(int(match.group(1)))
               try:
                   return await call_next(request)
               finally:
                   _execution_id_var.reset(token)
           return await call_next(request)
   ```

3. Format JSON optionnel (derrière env var `DH_LOG_FORMAT=json`) pour faciliter ingestion ELK/Loki.

**Note** : ce chantier touche au même point que N72 (audit_service thread-safety). Le `contextvars.ContextVar` utilisé ici peut être réutilisé pour `audit_service._request_context`.

---

### Chantier archives CONTEXT_*.md (Méta-5)

**Fichiers** : 64 fichiers `archives/CONTEXT_YYYYMMDD.md` untracked dans git status.

**Options** :
- A : les ajouter à git pour archivage (si valeur historique)
- B : les ajouter au `.gitignore` (pattern `archives/CONTEXT_*.md`)
- C : les déplacer vers un stockage externe (Notion, Confluence)

**Recommandation** : option B — `.gitignore`. Ces fichiers sont des logs de session quotidiens, pas du code. Les garder en local sans pollué git status.

```bash
echo "archives/CONTEXT_*.md" >> .gitignore
git rm --cached archives/CONTEXT_*.md 2>/dev/null || true
git add .gitignore
git commit -m "chore: gitignore daily CONTEXT session logs"
```

---

### Chantier docs obsolètes

**Inventaire** à faire au début du chantier :
```bash
cd /root/workspace/digital-humans-production
find docs/ -name "*.md" -mtime +60 2>/dev/null | head  # fichiers > 60 jours
```

**Docs à mettre à jour** après les refontes A+B+C :
1. `docs/architecture.md` — reflet de la nouvelle structure (si existe, sinon créer)
2. `docs/agents.md` — lister les 11 agents (depuis `agents_registry.yaml`)
3. `docs/deployment.md` — ajouter la section multi-profile (cf. briefing C section 10)
4. `docs/api-reference.md` — mise à jour routes (supprimer orphelines, ajouter `/api/config/capabilities`)
5. `CHANGELOG.md` — entries détaillées par briefing (A/B/C/D)
6. `docs/ADR-001-llm-strategy.md` — nouveau (créé dans briefing C)
7. `docs/ADR-002-agents-registry.md` — nouveau (créé dans briefing B)

---

## 3. Plan d'exécution

### Sprint 1 (jour 1) — Cleanup mécanique
- Supprimer `.backup_*` files
- Supprimer dead code Lucas (N19a)
- Ajouter `.gitignore` pour archives/CONTEXT_*.md
- `ruff --fix --select F401` auto-remove imports inutiles

### Sprint 2 (jour 1-2) — Paths hardcodés (P2)
- Identifier les 52 occurrences
- Créer/enrichir `app/config.py` avec settings lazy
- Remplacer au fur et à mesure (un commit par fichier touché)

### Sprint 3 (jour 2-3) — Logs + observabilité (P5)
- `logging_config.py` avec formatter centralisé
- Middleware `ExecutionContextMiddleware`
- Option JSON logs derrière env var

### Sprint 4 (jour 3-4) — Secrets & docs (P8 + docs)
- `docs/operations/secrets-rotation.md`
- Script `rotate_anthropic_key.sh`
- Mise à jour des docs après A+B+C
- Review CHANGELOG global

### Sprint 5 (jour 4) — Dead routes SDS V3 (suppression)
- Tag de sauvegarde `legacy/sds_v3_synthesis_before_removal` avant `git rm`
- Suppression `backend/app/services/sds_synthesis_service.py` (528 L)
- Retrait des 6 endpoints orphelins dans `sds_v3_routes.py` (garder `/generate-sds-v3` et `/download-sds-v3`)
- Vérification frontend (grep sur les 6 endpoint names)

---

## 4. DoD — Definition of Done

```bash
# 1. Pas de backup files
find backend -name "*.backup*" -type f | wc -l
# Should be 0

# 2. Pas de chemins hardcodés /root/ ou /home/
grep -rn "\"/root/\|\"/home/" backend/app backend/agents --include="*.py" \
  | grep -v __pycache__ | grep -v test_ | wc -l
# Should be 0 (or a small list of legitimate exceptions documented)

# 3. Ruff F401 clean
ruff check --select F401 --exclude venv,__pycache__,tests,migrations backend/ 2>&1 | grep -c "^F401"
# Should be 0

# 4. YAML stubs remplis (dépendance briefing B)
for f in diego_apex zara_lwc raj_admin; do
  [ $(wc -l < backend/prompts/agents/${f}.yaml) -gt 50 ] && echo "✅" || echo "❌ $f"
done

# 5. Archives in gitignore
grep "archives/CONTEXT_" backend/.gitignore && echo "✅" || echo "❌"

# 6. Docs à jour
for doc in docs/architecture.md docs/agents.md docs/deployment.md docs/ADR-001-llm-strategy.md; do
  [ -f "$doc" ] && echo "✅ $doc" || echo "❌ missing $doc"
done

# 7. Logs structurés
DH_LOG_FORMAT=json journalctl -u digital-humans-backend --since "5 min ago" | head -1 | python -c "import sys, json; json.loads(sys.stdin.read().split(' ', 2)[-1])" && echo "✅ JSON logs parse" || echo "⚠ check"
```

---

## 5. Risques & points d'attention

1. **Chantier P2 peut casser le boot** : si un path hardcodé était en fait nécessaire pour un script externe (ex: cron, systemd), le remplacement par var env peut casser silencieusement. Tester chaque path modifié.

2. **Suppression backup files** : avant `rm`, vérifier que le contenu est accessible via `git log -- <file>` ou `git stash list`. Si quelqu'un a besoin du backup pour debug, il peut le restaurer depuis git.

3. **Ruff --fix auto-remove** : peut supprimer un import qui est en fait utilisé via `__all__` ou re-export. Review manuelle après auto-fix.

4. **Docs obsolètes** : ne pas supprimer, juste marquer `# ARCHIVED YYYY-MM-DD` en tête. Info historique utile.

5. **Suppression SDS V3** (décision actée) : avant le `git rm`, vérifier exhaustivement que le frontend ne référence plus les 6 endpoints supprimés. Le tag `legacy/sds_v3_synthesis_before_removal` permet restauration si besoin futur.

---

## 6. Livrables attendus

- `backend/.gitignore` enrichi
- `backend/app/config.py` avec settings lazy paths
- `backend/app/utils/logging_config.py` (refondu ou nouveau)
- `backend/app/middleware/execution_context.py` (nouveau)
- `docs/operations/secrets-rotation.md` (nouveau)
- `scripts/rotate_anthropic_key.sh` (nouveau)
- `docs/architecture.md` (mise à jour)
- `docs/agents.md` (nouveau, auto-généré depuis `agents_registry.yaml`)
- `docs/deployment.md` (mise à jour multi-profile)
- `docs/ADR-001-llm-strategy.md` (nouveau — déplacé depuis briefing C)
- `docs/ADR-002-agents-registry.md` (nouveau — depuis briefing B)
- `CHANGELOG.md` (major release notes)
- Suppression de : 2 backup files, `sds_synthesis_service.py`, 6 endpoints SDS V3 orphelins dans `sds_v3_routes.py`, F401, dead code Lucas

*Fin briefing Agent D*
