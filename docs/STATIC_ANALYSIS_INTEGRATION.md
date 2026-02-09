# Static Analysis Integration Guide

## Overview

`CodeAnalysisService` runs PMD (Apex) and ESLint (LWC) on generated code, then
builds fix prompts for agents to auto-correct violations. This creates a
feedback loop: generate → analyze → fix → re-analyze, up to 3 iterations.

## Prerequisites

| Tool   | Version | Purpose          |
|--------|---------|------------------|
| PMD    | 7.9.0   | Apex analysis    |
| ESLint | 10.x    | LWC/JS analysis  |
| Java   | 21+     | PMD runtime      |
| Node   | 22+     | ESLint runtime   |

## Configuration Files

- **PMD ruleset**: `backend/data/pmd-apex-rules.xml`
- **ESLint config**: `backend/data/.eslintrc.json`

## Integration Pattern

To integrate into `phased_build_executor.py` after an agent generates code:

```python
from app.services.code_analysis_service import CodeAnalysisService, MAX_FIX_ITERATIONS

analyzer = CodeAnalysisService()

# --- After Diego generates Apex code ---
violations = analyzer.analyze_apex(diego_output)
for iteration in range(MAX_FIX_ITERATIONS):
    if not violations:
        break
    fix_prompt = analyzer.build_fix_prompt(diego_output, violations, "apex")
    diego_output = await llm_service.generate(fix_prompt, tier="WORKER")
    violations = analyzer.analyze_apex(diego_output)

if violations:
    logger.warning(
        f"Apex: {len(violations)} violations remaining after {MAX_FIX_ITERATIONS} iterations"
    )

# --- After Zara generates LWC code ---
violations = analyzer.analyze_lwc(zara_output)
for iteration in range(MAX_FIX_ITERATIONS):
    if not violations:
        break
    fix_prompt = analyzer.build_fix_prompt(zara_output, violations, "javascript")
    zara_output = await llm_service.generate(fix_prompt, tier="WORKER")
    violations = analyzer.analyze_lwc(zara_output)

if violations:
    logger.warning(
        f"LWC: {len(violations)} violations remaining after {MAX_FIX_ITERATIONS} iterations"
    )
```

## How It Works

1. Agent generates code (Apex or LWC)
2. `CodeAnalysisService` writes code to a temp file and runs the appropriate linter
3. Results are parsed from JSON output into a list of violation dicts
4. If violations exist, `build_fix_prompt()` creates a targeted prompt
5. The LLM fixes the code, and the loop re-analyzes
6. After `MAX_FIX_ITERATIONS` (3), remaining violations are logged as warnings
   and the pipeline continues — static analysis is advisory, not blocking

## Violation Dict Format

### Apex (PMD)
```python
{"rule": "ApexCRUDViolation", "message": "...", "line": 12, "priority": 2}
```

### LWC (ESLint)
```python
{"rule": "no-unused-vars", "message": "...", "line": 5, "severity": 1}
```

## Customization

### Adding PMD rules
Edit `backend/data/pmd-apex-rules.xml`. Available categories:
- `category/apex/bestpractices.xml`
- `category/apex/errorprone.xml`
- `category/apex/security.xml`
- `category/apex/performance.xml`
- `category/apex/codestyle.xml`

### Adding ESLint rules
Edit `backend/data/.eslintrc.json`. Add rules to the `"rules"` object.

### Changing max iterations
Update `MAX_FIX_ITERATIONS` in `code_analysis_service.py`.
