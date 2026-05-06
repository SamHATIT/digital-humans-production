"""
BaseAgent — contrat commun aux 11 agents Salesforce de Digital Humans.

Avant ce module (P10 audit) : chaque agent réimplémentait son __init__,
son cost tracking et parfois son wrapper LLM. Résultat = ~400 lignes de
duplication + comportements potentiellement divergents sous charge.

Maintenant :
- __init__(config) standard (factorise 11 copies identiques)
- _total_cost / _track_cost / total_cost property (cost tracking unifié)
- _call_llm() default (utilisable par les agents qui n'ont pas leur propre wrapper)
- _log_interaction() default (no-op si llm_logger absent)
- Class attributes agent_id / agent_type / display_name à surcharger
- run() abstrait : signature commune (task_data: Dict) -> Dict

Migration progressive : les agents qui ont déjà un _call_llm / _log_interaction
plus spécifique le gardent (override) — pas de breaking change. La migration
peut se faire en plusieurs sprints sans casser les autres.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Soft imports — comme dans les agents existants, on tolère un environnement CLI
# sans le backend complet (les agents peuvent être lancés en standalone via CLI).
try:
    from app.services.llm_service import generate_llm_response  # noqa: F401
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

try:
    from app.services.llm_logger import log_llm_interaction
    _LOGGER_AVAILABLE = True
except ImportError:
    _LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs):  # type: ignore[no-redef]
        pass


class BaseAgent(ABC):
    """Contrat partagé par tous les agents Digital Humans.

    Subclasses MUST set :
      - ``agent_id`` (str)         : "sophie", "marcus", "lucas", …
      - ``agent_type`` (str)       : "pm", "architect", "trainer", …
      - ``display_name`` (str)     : "Sophie (PM)", "Marcus (Solution Architect)", …

    Subclasses MUST implement :
      - ``run(task_data) -> Dict``  : point d'entrée canonique

    Subclasses MAY override :
      - ``_call_llm(...)``       : si la signature standard ne convient pas
      - ``_log_interaction(...)`` : si l'agent veut logger autrement
    """

    # ─── Identité (à surcharger par chaque agent) ────────────────────────────
    agent_id: str = ""
    agent_type: str = ""
    display_name: str = ""

    # ─── Init standard (factorise les 11 copies identiques) ──────────────────
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._total_cost: float = 0.0
        # Sanity check au runtime : un agent SANS agent_id est presque toujours
        # un bug. On warn (pas raise) pour ne pas casser un sub-test qui ne
        # passe pas par run().
        if not self.agent_id:
            logger.warning(
                f"{type(self).__name__} doesn't define class attribute 'agent_id'"
            )

    # ─── Contract obligatoire ────────────────────────────────────────────────
    @abstractmethod
    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Point d'entrée canonique. Retourne un dict structuré."""
        ...

    # ─── Cost tracking (unifié) ──────────────────────────────────────────────
    def _track_cost(self, cost_usd: float) -> None:
        """Accumulate LLM cost. Called by _call_llm or by agent code directly."""
        try:
            self._total_cost += float(cost_usd or 0.0)
        except (TypeError, ValueError):
            logger.warning(f"Invalid cost value for {self.agent_id}: {cost_usd!r}")

    @property
    def total_cost(self) -> float:
        """Total LLM cost in USD accumulated since instantiation."""
        return self._total_cost

    # ─── LLM call (default helper) ───────────────────────────────────────────
    def _call_llm(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        execution_id: int = 0,
        max_tokens: int = 16000,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> Tuple[str, int, int, str, str]:
        """Default LLM wrapper. Returns (content, tokens_out, tokens_in, model, provider).

        Tracks cost automatically via ``_track_cost``.

        Agents who already have their own ``_call_llm`` (with different signature
        or behaviour) override this method.
        """
        if not _LLM_AVAILABLE:
            logger.error(f"[{self.agent_id}] llm_service not available")
            return ("", 0, 0, "unavailable", "unavailable")

        # system_prompt is accepted but not all generate_llm_response signatures
        # take it — we pass it via kwargs only if non-empty.
        call_kwargs: Dict[str, Any] = {
            "agent_type": self.agent_type or self.agent_id or "generic",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "execution_id": execution_id,
        }
        if system_prompt:
            call_kwargs["system_prompt"] = system_prompt
        call_kwargs.update(kwargs)

        response = generate_llm_response(prompt, **call_kwargs)
        self._track_cost(response.get("cost_usd", 0.0))
        return (
            response.get("content", ""),
            response.get("tokens_used", 0),
            response.get("input_tokens", 0),
            response.get("model", "unknown"),
            response.get("provider", "unknown"),
        )

    # ─── Logging (default no-op-safe) ────────────────────────────────────────
    def _log_interaction(
        self,
        execution_id: int,
        prompt: str,
        response: str,
        *,
        mode: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "unknown",
        provider: str = "unknown",
        execution_time: float = 0.0,
        success: bool = True,
        error_message: Optional[str] = None,
        **extras: Any,
    ) -> None:
        """Default INFRA-002 logger wrapper. No-op si llm_logger absent."""
        if not _LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id=self.agent_id or "unknown",
                prompt=prompt,
                response=response,
                execution_id=execution_id,
                task_id=extras.get("task_id"),
                agent_mode=mode,
                rag_context=extras.get("rag_context"),
                previous_feedback=extras.get("previous_feedback"),
                parsed_files=extras.get("parsed_files"),
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                model=model,
                provider=provider,
                execution_time_seconds=round(execution_time, 2),
                success=success,
                error_message=error_message,
            )
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to log LLM interaction: {e}")

    # ─── Repr utile pour le debug ────────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} agent_id={self.agent_id!r} "
            f"cost=${self._total_cost:.4f}>"
        )
