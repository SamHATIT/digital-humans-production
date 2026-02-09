# Backlog — Digital Humans Refonte 2026

## P10 — Agent Architecture Debt (Post E2E #140)

**Sévérité :** Majeur (dette technique)
**Découvert :** 9 février 2026 — absent des audits initiaux (angle mort)
**Effort estimé :** M (2-3 jours, 1 prompt Claude Code)

### Problème

Les 11 agents (`backend/agents/roles/salesforce_*.py`) ont été développés organiquement
sans classe de base commune. Résultat :

- **Pas de `BaseAgent`** imposant un contrat d'interface
- **3 patterns différents** pour appeler le LLM :
  - Pattern A (BA, PM, DevOps, QA...) : `_execute()` → `_call_llm()` → `generate_llm_response()`
  - Pattern B (Trainer) : appel direct `generate_llm_response()` sans wrapper
  - Pattern C (Admin) : 4 appels dispersés, pas de `_call_llm()` centralisé
- **`execution_id` transmis différemment** : paramètre de `_execute()`, `self.execution_id`, ou absent
- **Pas de gestion d'erreur standardisée** : chaque agent a son propre try/except
- **Logging incohérent** : formats et niveaux variables entre agents
- **11 fichiers de 400-900 lignes** avec beaucoup de duplication

### Solution cible

```python
class BaseAgent(ABC):
    """Base class for all Digital Humans agents."""

    def __init__(self, execution_id: int, project_id: int, config: dict = None):
        self.execution_id = execution_id
        self.project_id = project_id
        self.logger = logging.getLogger(f"agent.{self.agent_id}")

    @property
    @abstractmethod
    def agent_id(self) -> str: ...

    @property
    @abstractmethod
    def agent_type(self) -> str: ...  # LLM tier: "orchestrator", "ba", "worker"

    @abstractmethod
    def _execute(self, mode: str, input_data: dict) -> dict: ...

    def _call_llm(self, prompt: str, system_prompt: str,
                  max_tokens: int = 8000, temperature: float = 0.4) -> dict:
        """Standardized LLM call with budget tracking and error handling."""
        return generate_llm_response(
            prompt=prompt,
            agent_type=self.agent_type,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            execution_id=self.execution_id,
        )

    def run(self, task_data: dict) -> dict:
        """Entry point — parses input, runs _execute, handles errors."""
        try:
            mode = task_data.get("mode", "default")
            return self._execute(mode, task_data)
        except Exception as e:
            self.logger.error(f"Agent {self.agent_id} failed: {e}")
            return {"success": False, "error": str(e)}
```

### Migration (par agent)

1. Hériter de `BaseAgent`
2. Remplacer tous les `generate_llm_response()` directs par `self._call_llm()`
3. Supprimer le boilerplate CLI argparse (centralisé dans `BaseAgent.run()`)
4. Uniformiser les signatures de `_execute()`

### Ordre de migration

Sophie (PM) en pilote → valider le pattern → les 10 autres en parallèle.
