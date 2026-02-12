# E2E #143 — Post-Mortem Report
**Date**: 2026-02-12
**Status**: STOPPED (manual) at Phase 3 — Architecture Validation HITL
**Duration**: ~55 min (19:55 → 20:50 UTC)
**Cost (app)**: $0.75 | **Cost (Anthropic dashboard)**: ~$3.37

## Objective
First E2E test with:
- PROMPTS-001→006 rewrites (Marcus, Emma, Olivia, Lucas)
- TRUNC-001: Marcus design split into 2 calls (core + technical)
- TRUNC-002: Section writer batch size 100→50
- BUG-016b: Gap analysis mode added to 32K max_tokens
- COST-001: Real cost_usd propagation from LLM router

## Timeline

| Time | Phase | Event | Result |
|------|-------|-------|--------|
| 19:55 | 1 | Sophie extracts BRs | ✅ 28 BRs, $0.22, ~75s |
| 20:00 | 1 | BR Validation (HITL) | ✅ Approved by Sam |
| 20:00 | 2 | Olivia generates UCs | ✅ 83 UCs |
| 20:16 | 2 | Emma UC Digest | ✅ 19K tokens, 144s |
| 20:16 | 3.1 | Marcus As-Is (greenfield) | ✅ Placeholder |
| 20:16 | 3.2 | Marcus Design (split) | ✅ 122K chars, 72K tokens |
| 20:28 | 3.3 | Emma Coverage Check | ❌ **45%** — triggers auto-revision |
| 20:38 | 3.3r1 | Marcus Revision 1 | 77K chars, 82K tokens |
| 20:38 | 3.3r1 | Emma Re-validate | ❌ **64.8%** — triggers revision 2 |
| 20:48 | 3.3r2 | Marcus Revision 2 | ? |
| 20:48 | 3.3r2 | Emma Re-validate | ❌ **54.8%** — regression, HITL gate |
| 20:50 | HITL | Sam stops execution | 92 "critical gaps" shown |

## Key Findings

### 1. TRUNC-001 Split Design — WORKED
Marcus split into 2 calls produced 122K chars (vs ~30K single-shot in E2E #142).
Design metadata confirms `"design_mode": "split_2_calls"`.
The merged design contains all 10 expected sections.

### 2. COVERAGE Scoring — CRITICALLY BROKEN (3 bugs found)

#### Bug A: UC Format Mismatch
- Emma's `calculate_coverage_score()` expected: `uc['salesforce_components']['objects']`
- Olivia actually produces: `uc['sf_objects']` (flat keys)
- Result: `uc_objects = {}` → data_model score = 0%

#### Bug B: Weight Imbalance
- Old weights: obj=0.35, auto=0.25, ui=0.20, trace=0.20
- UC traceability (the most meaningful metric) only counted 20%
- Object matching (prone to false negatives) counted 35%

#### Bug C: Automation Type Mismatch
- UCs list generic types: "Flow", "Apex", "Validation Rule"
- Marcus lists specific names: "Email_to_Case_Enrichment", "CaseTrigger"
- No intersection possible → automation score always 0%

#### Fix Impact (same Marcus design):
```
BEFORE FIX:  45.0% (REJECTED)
  data_model:      0.0%  → BUG: uc_objects empty
  automation:    100.0%  → BUG: false positive (empty vs empty)
  ui_components: 100.0%  → OK (both empty)
  uc_traceability: 0.0%  → BUG: object-only matching

AFTER FIX:   90.3% (NEEDS_MINOR_REVISION)
  data_model:     54.8%  → Real: 34/62 filtered objects match
  automation:    100.0%  → Real: SD has flows+triggers covering generic reqs
  ui_components: 100.0%  → OK
  uc_traceability: 98.8% → Real: 82/83 UCs in traceability map
```

### 3. Cost Tracking — PARTIAL FIX
- App showed $0.75 vs Anthropic dashboard $3.37 (22% capture rate)
- Marcus now propagates cost_usd from router ✅
- BUT: Emma, Olivia, and other agents still use _calculate_cost() heuristic
- AND: agent_execution_status shows tok=0 for all agents (not updated)
- Root cause: _track_tokens only called for some code paths

### 4. Frontend Gaps Display — BUG
- 92 critical gaps shown as `[high]` / `[medium]` with NO description text
- Data Model tab shows "Not Found"
- Likely: frontend reads gap.category/gap.description but Emma's report
  uses different keys, or gaps are empty objects

### 5. Revision Regression (64.8% → 54.8%)
- Rev1 improved from 45% → 64.8%
- Rev2 REGRESSED to 54.8%
- Likely cause: Marcus regenerates full design (not incremental), and
  second revision lost some elements that first revision added

## Commits This Session

```
3b2d070 fix(COVERAGE): scoring system rewrite — UC format compat + fair weights
61bbeda fix(TRUNC+COST): Marcus design split 2 calls, batch 50, real cost tracking
```

## Files Modified

### salesforce_research_analyst.py (coverage scoring)
- `calculate_coverage_score()`: Support both UC formats (nested + flat)
- UC traceability: Check `uc_traceability` map, not just object overlap
- Filter SF infra objects (User, Queue, Report, etc.) from comparison
- Handle generic automation types vs specific names
- Rebalance weights: trace=0.55, obj=0.20, auto=0.15, ui=0.10
- Extract `apex_triggers` and `scheduled_jobs` from solution design

### salesforce_solution_architect.py (Marcus design split)
- `get_design_prompt()`: New `design_focus` parameter (core/technical)
- Focus instructions scope output to subset of JSON sections
- Technical focus receives data_model_context from core call
- `_call_llm()`: Returns 6-tuple with cost_usd
- `_build_prompt()`: Passes design_focus through to prompt

### pm_orchestrator_service_v2.py (orchestrator)
- Phase 3.2: Split into 2 sequential calls (core + technical)
- Deep merge logic for combining both design halves
- Fallback to single-shot if core call fails
- `_track_tokens()`: Use real cost_usd from router when available

### sds_section_writer.py
- UC_BATCH_SIZE: 100 → 50

## Backlog Updates

| ID | Priority | Status | Description |
|----|----------|--------|-------------|
| TRUNC-001 | P1 | ✅ FIXED | Marcus design split 2 calls |
| TRUNC-002 | P1 | ✅ FIXED | Section writer batch 100→50 |
| BUG-016b | P2 | ✅ FIXED | Gap analysis 32K max_tokens |
| COST-001 | P2 | 🟡 PARTIAL | Only Marcus propagates cost_usd |
| **COVERAGE-001** | **P0** | **✅ FIXED** | **Scoring UC format mismatch** |
| **COVERAGE-002** | **P0** | **✅ FIXED** | **Weight rebalancing** |
| **COVERAGE-003** | **P0** | **✅ FIXED** | **Automation type matching** |
| FRONTEND-001 | P3 | NEW | Gap descriptions not displayed |
| FRONTEND-002 | P3 | NEW | Data Model tab "Not Found" |
| COST-002 | P2 | NEW | Only 22% cost captured (all agents need cost_usd) |
| REVISION-001 | P2 | NEW | Rev2 regresses vs Rev1 (non-incremental) |

## Next Steps — Prompt Review
Before E2E #144, systematic review needed:
1. **Marcus design prompt** — Verify split instructions produce complete output
2. **Emma validate prompt** — LLM scoring vs programmatic scoring alignment
3. **Emma validate: what LLM actually sees** — Is merged design passed correctly?
4. **Olivia UC format** — Should UCs include salesforce_components for compat?
5. **Revision prompt** — Why does rev2 regress? Is previous_design passed?
