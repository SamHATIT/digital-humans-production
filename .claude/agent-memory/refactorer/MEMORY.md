# Refactorer Agent Memory - P3 subprocess to import

## Completed Migrations
| # | Agent | File | Status | Date |
|---|-------|------|--------|------|
| 1 | Sophie (PM) | salesforce_pm.py | DONE | 2026-02-07 |

## Key Patterns Established

### Agent Class Pattern (used for PMAgent, template for others)
- Module-level `try/except` for `llm_service` and `llm_logger` imports (safety)
- `PMAgent` class with `run(task_data: dict) -> dict` as main entry point
- `task_data` keys: `mode`, `input_content`, `execution_id`, `project_id`
- Return format: `{"success": True, "agent_id": "...", "content": {...}, "metadata": {...}}`
- Error format: `{"success": False, "error": "..."}`
- Private methods: `_execute()`, `_call_llm()`, `_parse_response()`, `_log_interaction()`
- `if __name__ == "__main__"` block for CLI backward compat with `sys.path` setup

### agent_executor.py Integration Pattern
- `MIGRATED_AGENTS: Dict[str, type]` registry at module level
- Import with `try/except` for safety (fallback to subprocess)
- `execute_agent()`: early-return branch for migrated agents using `asyncio.to_thread()`
- `run_agent_task()`: early-return check before subprocess code
- `input_content = json.dumps(input_data)` to maintain parity with file-based flow

## Key Lessons
- **sys.path**: Removed `sys.path.insert(0, "/app")` from module level. In CLI mode, use `Path(__file__).resolve().parent.parent.parent` for dynamic backend path.
- **No circular imports**: agents -> llm_service -> json_cleaner chain has no cycles
- **Test env**: Production server has venv; CI env may lack psycopg2/cryptography. Use structural tests for validation.
- **Two AGENT_CONFIGs**: `agent_executor.py` uses "sophie"; `pm_orchestrator_service_v2.py` uses "pm". Different configs, different subprocess code. Orchestrator's `_run_agent()` is NOT in Refactorer scope.
- **agent_tester only caller**: `agent_executor.py` is imported only by `agent_tester.py` route. `run_agent_task()` is currently unused (dead).

## Files Modified in P3
- `backend/agents/roles/salesforce_pm.py` - class transformation
- `backend/app/services/agent_executor.py` - direct import support

## Next Agent: Lucas (Trainer) - salesforce_trainer.py
- 389 lines, 2 modes (sds_strategy, delivery)
- Simplest agent after Sophie
- Same pattern: TrainerAgent class + MIGRATED_AGENTS["lucas"] registration
