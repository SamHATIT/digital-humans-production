#!/usr/bin/env python3
"""
Salesforce Data Migration Agent - Aisha
Dual Mode: spec (for SDS) | build (for real migration artifacts)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (DataMigrationAgent.run()) or CLI (python salesforce_data_migration.py --mode ...).
"""

import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# LLM imports - clean imports for direct import mode
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# RAG Service
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
except ImportError:
    LLM_LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs): pass

# Prompt Service for externalized prompts
from prompts.prompt_service import PromptService
PROMPT_SERVICE = PromptService()


# ============================================================================
# PROMPTS
# ============================================================================

SPEC_PROMPT = """# DATA MIGRATION - SPECIFICATION MODE

You are Aisha, an expert Salesforce Data Migration Specialist.
Generate comprehensive data migration SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## DELIVERABLES
1. **Data Assessment** - Source systems, volumes, quality
2. **Migration Strategy** - Approach, tools, phases
3. **Data Mapping** - Source to target field mappings
4. **Transformation Rules** - Data cleansing, enrichment
5. **Validation Plan** - Pre/post migration checks
6. **Rollback Strategy** - Recovery procedures

## FORMAT
Use clear markdown with detailed specifications.
"""


BUILD_PROMPT = """# DATA MIGRATION ARTIFACTS - BUILD MODE

You are Aisha, generating REAL data migration artifacts.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## CRITICAL OUTPUT FORMAT
Generate complete migration artifacts. For EACH file, use this format:

For CSV Templates:
```csv
// FILE: data/migration/ObjectName_template.csv
Id,Field1__c,Field2__c,Relationship__r.ExternalId__c
,Value1,Value2,REF-001
```

For Data Loader Process Conf:
```xml
<!-- FILE: data/config/ObjectName-insert.process-conf.xml -->
<!DOCTYPE process>
<process>
    <operation>insert</operation>
    <mappingFile>ObjectName_mapping.sdl</mappingFile>
    <csvFile>ObjectName_data.csv</csvFile>
</process>
```

For Mapping Files:
```
// FILE: data/config/ObjectName_mapping.sdl
# Salesforce Data Loader Mapping
Field1__c=Source_Field1
Field2__c=Source_Field2
```

For Validation Queries:
```sql
// FILE: data/validation/ObjectName_validation.sql
-- Pre-migration count
SELECT COUNT(*) FROM SourceTable;

-- Post-migration validation
SELECT COUNT(*) FROM ObjectName__c WHERE Migration_Batch__c = 'BATCH001';
```

For Apex Data Scripts (if needed):
```apex
// FILE: scripts/apex/DataMigration_ObjectName.apex
// Anonymous Apex for complex transformations
List<ObjectName__c> records = new List<ObjectName__c>();
// ... logic
insert records;
```

## MIGRATION BEST PRACTICES
1. Include External ID fields for upserts
2. Handle relationships via External IDs
3. Include validation queries
4. Batch large volumes (10k records max)
5. Document transformation logic

## GENERATE THE ARTIFACTS NOW:
"""


# ============================================================================
# BUILD V2 - DATA SOURCES INTEGRATION (utility functions, kept module-level)
# ============================================================================

def format_data_sources(data_sources: list) -> str:
    """
    Formate les sources de donnees configurees pour le prompt.

    Args:
        data_sources: Liste des configurations de sources de donnees

    Returns:
        Texte formate pour injection dans le prompt
    """
    if not data_sources:
        return "Aucune source de donnees configuree. Generez des templates generiques."

    lines = ["## SOURCES DE DONNEES CONFIGUREES\n"]

    for i, source in enumerate(data_sources, 1):
        lines.append(f"### Source {i}: \"{source.get('name', 'Unknown')}\"")
        lines.append(f"  - **Objet cible**: {source.get('target_object', 'N/A')}")
        lines.append(f"  - **Format**: {source.get('source_type', 'csv').upper()}")

        config = source.get('config', {})
        if config.get('file_path'):
            lines.append(f"  - **Fichier**: {config.get('file_path')}")
        if config.get('columns'):
            lines.append(f"  - **Colonnes**: {', '.join(config.get('columns', []))}")

        mapping = source.get('column_mapping', {})
        if mapping:
            lines.append("  - **Mapping predefini**:")
            for src_col, sf_field in list(mapping.items())[:5]:
                lines.append(f"      {src_col} -> {sf_field}")

        lines.append("")

    lines.append("""
## INSTRUCTIONS SPECIFIQUES
1. Generez un fichier SDL pour CHAQUE source configuree
2. Le mapping doit correspondre aux colonnes indiquees
3. Respectez l'ordre d'import (import_order) - parents avant enfants
4. Incluez des requetes SOQL de validation pour chaque objet
""")

    return "\n".join(lines)


async def get_project_data_sources(project_id: int, db) -> list:
    """
    Recupere les sources de donnees configurees pour un projet.

    Args:
        project_id: ID du projet
        db: Session SQLAlchemy

    Returns:
        Liste des configurations de sources de donnees
    """
    try:
        from sqlalchemy import text

        result = db.execute(
            text("""
                SELECT name, target_object, source_type, config, column_mapping, import_order
                FROM project_data_sources
                WHERE project_id = :project_id AND is_active = true
                ORDER BY import_order ASC
            """),
            {"project_id": project_id}
        )

        sources = []
        for row in result:
            sources.append({
                "name": row.name,
                "target_object": row.target_object,
                "source_type": row.source_type,
                "config": row.config or {},
                "column_mapping": row.column_mapping or {},
                "import_order": row.import_order or 0
            })

        return sources

    except Exception as e:
        logger.warning(f"Failed to get data sources: {e}")
        return []


# ============================================================================
# DATA MIGRATION AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class DataMigrationAgent:
    """
    Aisha (Data Migration) Agent - Spec + Build modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - spec: Generate data migration specifications for SDS document
        - build: Generate real migration artifacts (CSV, SDL, SQL, Apex)

    Usage (import):
        agent = DataMigrationAgent()
        result = agent.run({"mode": "spec", "input_content": "..."})

    Usage (CLI):
        python salesforce_data_migration.py --mode spec --input input.json --output output.json
    """

    VALID_MODES = ("spec", "build")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "spec" or "build"
                - input_content: string content (raw text for spec, JSON string for build)
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
            On success: full output dict with agent_id, content, metadata, etc.
            On failure: {"success": False, "error": "..."}
        """
        mode = task_data.get("mode", "spec")
        input_content = task_data.get("input_content", "")
        execution_id = task_data.get("execution_id", 0)
        project_id = task_data.get("project_id", 0)

        # Map sds_strategy alias to spec
        if mode == "sds_strategy":
            mode = "spec"

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            if mode == "spec":
                return self._execute_spec(input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"DataMigrationAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # SPEC MODE
    # ------------------------------------------------------------------
    def _execute_spec(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute spec mode: generate data migration specifications for SDS."""
        start_time = time.time()

        # Get RAG context
        rag_context = self._get_rag_context(project_id=project_id)

        # Build prompt - try PromptService first, fallback to constant
        prompt = PROMPT_SERVICE.render("aisha_data", "spec", {
            "requirements": input_content[:25000],
        })
        if rag_context:
            prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"

        logger.info(f"DataMigrationAgent mode=spec, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=16000, temperature=0.3, execution_id=execution_id
        )

        execution_time = time.time() - start_time
        logger.info(
            f"DataMigrationAgent spec generated {len(content)} chars in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction
        self._log_interaction(
            mode="spec",
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
            rag_context=rag_context,
        )

        return {
            "success": True,
            "agent_id": "aisha",
            "agent_name": "Aisha (Data Migration)",
            "mode": "spec",
            "execution_id": str(execution_id),
            "deliverable_type": "migration_specification",
            "content": {"raw_markdown": content},
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # BUILD MODE
    # ------------------------------------------------------------------
    def _execute_build(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute build mode: generate real migration artifacts."""
        start_time = time.time()

        # Parse input data
        try:
            input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            input_data = {"task": {"name": "Task", "description": str(input_content)}}

        task = input_data.get("task", input_data)
        task_id = task.get("task_id", "UNKNOWN")
        task_name = task.get("name", task.get("title", "Unnamed Task"))
        task_description = task.get("description", "")
        architecture_context = input_data.get("architecture_context", "")
        previous_feedback = input_data.get("previous_feedback", "")
        solution_design = input_data.get("solution_design")
        gap_context = input_data.get("gap_context", "")
        data_sources = input_data.get("data_sources")

        # Get RAG context
        rag_context = self._get_rag_context(project_id=project_id)

        # Build correction context
        correction_context = ""
        if previous_feedback:
            correction_context = f"""
## CORRECTION NEEDED - PREVIOUS ATTEMPT FAILED
Elena (QA) found issues:
{previous_feedback}

FIX THESE ISSUES.
"""

        # Build prompt - try PromptService first, fallback to constant
        prompt = PROMPT_SERVICE.render("aisha_data", "build", {
            "task_id": task_id,
            "task_name": task_name,
            "task_description": task_description,
            "architecture_context": architecture_context[:10000],
        })
        if rag_context:
            prompt += f"\n\n## MIGRATION BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"

        # BUILD V2: Include data sources configuration
        if data_sources:
            prompt += "\n\n" + format_data_sources(data_sources)

        # Add correction context if retry
        if correction_context:
            prompt += correction_context

        # BUG-044/046: Include Solution Design from Marcus
        if solution_design:
            sd_text = ""
            if solution_design.get("data_model"):
                sd_text += f"### Data Model\n{solution_design['data_model']}\n\n"
            if solution_design.get("data_migration"):
                sd_text += f"### Data Migration Plan\n{solution_design['data_migration']}\n\n"
            if solution_design.get("mappings"):
                sd_text += f"### Field Mappings\n{solution_design['mappings']}\n\n"
            if sd_text:
                prompt += f"\n\n## SOLUTION DESIGN (Marcus)\n{sd_text[:5000]}\n"

        # BUG-045: Include GAP context
        if gap_context:
            prompt += f"\n\n## GAP ANALYSIS CONTEXT\n{gap_context[:3000]}\n"

        logger.info(f"DataMigrationAgent mode=build, task={task_id}, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=8000, temperature=0.2, execution_id=execution_id
        )

        execution_time = time.time() - start_time
        files = self._parse_files(content)
        logger.info(
            f"DataMigrationAgent build generated {len(files)} file(s) in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction
        self._log_interaction(
            mode="build",
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            task_id=task_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
            rag_context=rag_context,
            previous_feedback=previous_feedback,
            parsed_files={"files": list(files.keys()), "count": len(files)},
            success=len(files) > 0,
        )

        return {
            "success": len(files) > 0,
            "agent_id": "aisha",
            "agent_name": "Aisha (Data Migration)",
            "mode": "build",
            "task_id": task_id,
            "execution_id": str(execution_id),
            "deliverable_type": "migration_artifacts",
            "content": {"raw_response": content, "files": files, "file_count": len(files)},
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # LLM / RAG / Logger helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self, prompt: str, max_tokens: int = 8000, temperature: float = 0.3,
        execution_id: int = 0
    ) -> tuple:
        """
        Call LLM service with fallback to direct OpenAI.

        Returns:
            (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=prompt,
                agent_type="data_migration",
                max_tokens=max_tokens,
                temperature=temperature,
                execution_id=execution_id,
            )
            content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)
            input_tokens = response.get("input_tokens", 0)
            model_used = response.get("model", "unknown")
            return content, tokens_used, input_tokens, model_used, "anthropic"

        # Fallback to OpenAI
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            tokens_used = resp.usage.total_tokens
            input_tokens = resp.usage.prompt_tokens
            return content, tokens_used, input_tokens, "gpt-4o-mini", "openai"
        except Exception as e:
            logger.error(f"LLM call failed (no provider available): {e}")
            raise

    def _get_rag_context(self, project_id: int = 0) -> str:
        """Fetch RAG context for data migration best practices."""
        if not RAG_AVAILABLE:
            return ""
        try:
            return get_salesforce_context(
                "Salesforce data migration data loader ETL",
                n_results=3,
                agent_type="data_migration",
                project_id=project_id or None,
            )
        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")
            return ""

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int = 0,
        tokens_used: int = 0,
        model_used: str = "",
        provider_used: str = "",
        execution_time: float = 0.0,
        rag_context: str = "",
        task_id: Optional[str] = None,
        previous_feedback: Optional[str] = None,
        parsed_files: Optional[Dict] = None,
        success: bool = True,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="aisha",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode=mode,
                rag_context=rag_context if rag_context else None,
                previous_feedback=previous_feedback if previous_feedback else None,
                parsed_files=parsed_files,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=success,
                error_message=None if success else "No files parsed",
            )
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")

    @staticmethod
    def _parse_files(content: str) -> Dict[str, str]:
        """Parse migration artifact files from LLM response."""
        files = {}
        patterns = [
            r'```(?:csv)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
            r'```(?:xml)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```',
            r'```(?:sql)\s*\n--\s*FILE:\s*(\S+)\s*\n(.*?)```',
            r'```(?:apex)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
            r'```\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for filepath, code in matches:
                if filepath.strip() and code.strip():
                    files[filepath.strip()] = code.strip()
        return files


# ============================================================================
# CLI MODE - Backward compatible subprocess entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Add backend root to sys.path for CLI mode
    _backend_root = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    parser = argparse.ArgumentParser(description='Aisha - Data Migration (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'build'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--execution-id', default='0')
    parser.add_argument('--project-id', default='unknown')
    parser.add_argument('--use-rag', action='store_true', default=True)
    args = parser.parse_args()

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()

        agent = DataMigrationAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))

    except Exception as e:
        error_result = {"agent_id": "aisha", "success": False, "error": str(e)}
        with open(args.output, 'w') as f:
            json.dump(error_result, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
