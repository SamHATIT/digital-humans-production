# Refactorer Agent Memory - P3 subprocess to import

## P3 STATUS: COMPLETE (all 11 agents migrated)

## Completed Migrations
| # | Agent | File | Class | Status | Date |
|---|-------|------|-------|--------|------|
| 1 | Sophie (PM) | salesforce_pm.py | PMAgent | DONE | 2026-02-07 |
| 2 | Lucas (Trainer) | salesforce_trainer.py | TrainerAgent | DONE | 2026-02-07 |
| 3 | Jordan (DevOps) | salesforce_devops.py | DevOpsAgent | DONE | 2026-02-07 |
| 4 | Olivia (BA) | salesforce_business_analyst.py | BusinessAnalystAgent | DONE | 2026-02-07 |
| 5 | Aisha (Data) | salesforce_data_migration.py | DataMigrationAgent | DONE | 2026-02-07 |
| 6 | Elena (QA) | salesforce_qa_tester.py | QATesterAgent | DONE | 2026-02-07 |
| 7 | Zara (LWC) | salesforce_developer_lwc.py | LWCDeveloperAgent | DONE | 2026-02-07 |
| 8 | Diego (Apex) | salesforce_developer_apex.py | ApexDeveloperAgent | DONE | 2026-02-07 |
| 9 | Raj (Admin) | salesforce_admin.py | AdminAgent | DONE | 2026-02-07 |
| 10 | Marcus (Architect) | salesforce_solution_architect.py | SolutionArchitectAgent | DONE | 2026-02-07 |
| 11 | Emma (Research) | salesforce_research_analyst.py | ResearchAnalystAgent | DONE | 2026-02-07 |

## MIGRATED_AGENTS Registry (agent_executor.py) - 21 entries
```
sophie -> PMAgent
lucas, trainer -> TrainerAgent
jordan, devops -> DevOpsAgent
olivia, ba -> BusinessAnalystAgent
aisha, data -> DataMigrationAgent
elena, qa -> QATesterAgent
zara, lwc -> LWCDeveloperAgent
diego, apex -> ApexDeveloperAgent
raj, admin -> AdminAgent
marcus, architect -> SolutionArchitectAgent
emma, research_analyst -> ResearchAnalystAgent
```

## Key Patterns Established

### Agent Class Pattern (template for all)
- Module-level `try/except` for `llm_service`, `rag_service`, `llm_logger` imports (safety)
- `XxxAgent` class with `run(task_data: dict) -> dict` as main entry point
- `task_data` keys: `mode`, `input_content`, `execution_id`, `project_id`
- Return format: `{"success": True, "agent_id": "...", "content": {...}, "metadata": {...}}`
- Error format: `{"success": False, "error": "..."}`
- Private methods: `_execute_xxx()`, `_call_llm()`, `_get_rag_context()`, `_log_interaction()`
- `if __name__ == "__main__"` block for CLI backward compat with `sys.path` setup

### agent_executor.py Integration Pattern
- `MIGRATED_AGENTS: Dict[str, type]` registry at module level
- Import with `try/except` for safety (fallback to subprocess)
- `AGENT_DEFAULT_MODES: Dict[str, str]` for tester mode selection
- `execute_agent()`: early-return branch using `asyncio.to_thread()` + AGENT_DEFAULT_MODES
- `run_agent_task()`: early-return check before subprocess code
- `input_content = json.dumps(input_data)` to maintain parity with file-based flow

### Preserving Module-Level Functions for External Imports
- **Elena**: `structural_validation`, `PHASE_REVIEW_PROMPTS`, `get_phase_review_prompt`, `review_phase_output`, `generate_test`
- **Zara**: `validate_lwc_naming`, `validate_lwc_structure`, `parse_lwc_files_robust`, `generate_build`
- **Aisha**: `format_data_sources`, `get_project_data_sources`
- **Diego**: `generate_build`, `sanitize_apex_code`, `validate_apex_structure`, `_parse_code_files`
- **Raj**: `generate_build_v2`, `BUILD_V2_PHASE1/4/5_PROMPT`, `_parse_xml_files`, `generate_build`
- **Marcus**: `get_design_prompt`, `get_as_is_prompt`, `get_gap_prompt`, `get_wbs_prompt`, `get_fix_gaps_prompt`
- **Emma**: `parse_json_response`, `calculate_coverage_score`, `generate_coverage_report_programmatic`
- Pattern: class delegates to module-level function for BUILD, class has own implementation for SPEC

## Key Lessons
- **sys.path**: Removed from module level. In CLI mode, use `Path(__file__).resolve().parent.parent.parent`
- **No circular imports**: agents -> llm_service -> json_cleaner chain has no cycles
- **Test env**: CI env lacks psycopg2/cryptography. Use structural tests for validation
- **Two AGENT_CONFIGs**: agent_executor.py uses "sophie"; pm_orchestrator_service_v2.py uses "pm"
- **Module-level functions**: Must stay accessible for phased_build_executor.py direct imports

## Files Modified in P3
- `backend/agents/roles/salesforce_*.py` (all 11 agents)
- `backend/app/services/agent_executor.py` - direct import support + registry (21 entries)
