# Backlog — Digital Humans Production
# Updated: 2026-02-11 after E2E #142

## Priority 1 — Deploy Before E2E #143

| ID | Description | Commit | File |
|----|-------------|--------|------|
| BUG-015 | uc_digest extraction: reads content directly, not content.digest | fe0cb64 | pm_orchestrator_service_v2.py:518 |
| BUG-016 | Section writer max_tokens 16K→16384 | f225baf | sds_section_writer.py |
| BUG-007 | Accumulate LLM cost on execution after each agent call | 861d24d | pm_orchestrator_service_v2.py |

## Priority 2 — Fix Before Next E2E

| ID | Description | Severity | Notes |
|----|-------------|----------|-------|
| BUG-016b | Gap analysis mode not in 32K max_tokens list | MEDIUM | salesforce_solution_architect.py:972 — add 'gap' to 32K modes |
| BUG-014b | Resume phase3 replays Phase 2/2.5 (no checkpoint guard) | MEDIUM | Only phase1 checks resume_from variable |
| COST-001 | Cost counter always $0.00 | MEDIUM | tokens_used=0 in all agent_status entries |

## Priority 3 — UX Improvements

| ID | Description | Severity | Notes |
|----|-------------|----------|-------|
| UX-003 | Coverage gaps show only severity tag, not description | MINOR | Frontend renders severity but not element_type/recommendation |
| UX-004 | Active Agent: .find() → .filter() for parallel agents | MINOR | ExecutionMonitoringPage.tsx:544 |
| COST-002 | Budget $50 hardcoded | MINOR | Should come from project settings |

## Priority 4 — Quality/Polish

| ID | Description | Severity | Notes |
|----|-------------|----------|-------|
| PROMPT-001 | Emma recommends Einstein Bots (hallucination) | MINOR | Prompt guardrail needed |
| ROUTER-001 | Phase 4 experts use mixed models (Haiku/Sonnet4/Sonnet4.5) | MINOR | LLM router config inconsistency |
| TRUNC-001 | Marcus design v1 hits 32K cap — JSON truncated | ARCH | Need chunked design or more concise output |
| TRUNC-002 | Section writer batch 2 hits 16K cap + 3 continuations | ARCH | Continuation loop wastes ~$1 per run |

## Completed (E2E #142 session)

| ID | Description | Commit | Verified |
|----|-------------|--------|----------|
| ARCH-002 | Pass uc_digest + previous_design to Marcus revision | 84b33e0 | ✅ E2E #142 |
| ARCH-002b | Truncation 12K→40K for previous_design | 84b33e0 | ✅ E2E #142 |
| BUG-013 | HITL instead of crash when coverage < 70% | 84b33e0 | ✅ E2E #142 (buttons appeared) |
| BUG-012 | Async LLM path for Phase 5 | e02f102 | ✅ E2E #142 |
| BUG-011 | phase3_complete transition in resume | e02f102 | ✅ E2E #142 |
| BUG-006 | flush→commit | 86aa448 | ✅ E2E #142 |
| BUG-008 | Ghost job guard | 86aa448 | ✅ E2E #142 |
| BUG-010 | Auto-resume checkpoints | 86aa448 | ✅ E2E #142 |

