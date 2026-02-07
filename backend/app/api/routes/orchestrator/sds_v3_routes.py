"""
SDS V3 pipeline routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — Micro-analysis, synthesis, DOCX generation.
P7: Batch DB operations wrapped in try/except with rollback.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.config import settings
from app.utils.dependencies import get_current_user
from app.api.routes.orchestrator._helpers import verify_execution_project_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/execute/{execution_id}/microanalyze")
async def microanalyze_ucs(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SDS V3: Launch micro-analysis of UCs with local LLM (Mistral)."""
    from app.models.deliverable_item import DeliverableItem
    from app.services.uc_analyzer_service import get_uc_analyzer
    from app.models.uc_requirement_sheet import UCRequirementSheet

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    ucs = db.query(DeliverableItem).filter(
        DeliverableItem.execution_id == execution_id,
        DeliverableItem.item_type == "use_case",
    ).all()

    if not ucs:
        raise HTTPException(status_code=400, detail="No Use Cases found. Run Phase 2 (Olivia) first.")

    logger.info(f"[MicroAnalyze] Starting analysis of {len(ucs)} UCs for execution {execution_id}")

    uc_dicts = []
    for uc in ucs:
        parsed = uc.content_parsed or {}
        uc_dict = {
            "id": uc.item_id,
            "uc_id": uc.item_id,
            "title": parsed.get("title", ""),
            "parent_br_id": uc.parent_ref,
        }
        if isinstance(parsed, dict):
            uc_dict.update(parsed)
        uc_dicts.append(uc_dict)

    analyzer = get_uc_analyzer()
    results = await analyzer.analyze_batch(uc_dicts)

    # P7: Batch save all sheets in a single transaction
    saved_count = 0
    errors = []
    try:
        for (fiche, llm_response), uc_dict in zip(results, uc_dicts):
            try:
                existing = db.query(UCRequirementSheet).filter(
                    UCRequirementSheet.execution_id == execution_id,
                    UCRequirementSheet.uc_id == fiche.uc_id,
                ).first()

                if existing:
                    existing.uc_title = fiche.titre or uc_dict.get("title", "")
                    existing.sheet_content = fiche.to_dict()
                    existing.analysis_complete = not bool(fiche.error)
                    existing.analysis_error = fiche.error
                    if llm_response:
                        existing.llm_provider = llm_response.provider
                        existing.llm_model = llm_response.model_id
                        existing.tokens_in = llm_response.tokens_in
                        existing.tokens_out = llm_response.tokens_out
                        existing.cost_usd = llm_response.cost_usd
                        existing.latency_ms = llm_response.latency_ms
                else:
                    sheet = UCRequirementSheet(
                        execution_id=execution_id,
                        uc_id=fiche.uc_id,
                        uc_title=fiche.titre or uc_dict.get("title", ""),
                        parent_br_id=uc_dict.get("parent_br_id"),
                        sheet_content=fiche.to_dict(),
                        analysis_complete=not bool(fiche.error),
                        analysis_error=fiche.error,
                        llm_provider=llm_response.provider if llm_response else None,
                        llm_model=llm_response.model_id if llm_response else None,
                        tokens_in=llm_response.tokens_in if llm_response else 0,
                        tokens_out=llm_response.tokens_out if llm_response else 0,
                        cost_usd=llm_response.cost_usd if llm_response else 0.0,
                        latency_ms=llm_response.latency_ms if llm_response else 0,
                    )
                    db.add(sheet)

                if not fiche.error:
                    saved_count += 1
                else:
                    errors.append({"uc_id": fiche.uc_id, "error": fiche.error})

            except Exception as e:
                logger.error(f"[MicroAnalyze] Error saving {fiche.uc_id}: {e}")
                errors.append({"uc_id": fiche.uc_id, "error": str(e)})

        db.commit()
    except Exception:
        db.rollback()
        raise

    stats = analyzer.get_stats()

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    agent_distribution = {}
    for sheet in sheets:
        if sheet.sheet_content:
            agent = sheet.sheet_content.get("agent_suggere", "unknown")
            agent_distribution[agent] = agent_distribution.get(agent, 0) + 1

    logger.info(f"[MicroAnalyze] Completed: {saved_count}/{len(ucs)} UCs analyzed")

    return {
        "execution_id": execution_id,
        "total_ucs": len(ucs),
        "analyzed": saved_count,
        "failed": len(errors),
        "errors": errors[:5] if errors else [],
        "agent_distribution": agent_distribution,
        "cost_usd": round(stats.get("total_cost_usd", 0), 4),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
        "success_rate": stats.get("success_rate", 0),
        "llm_provider": "ollama/mistral" if saved_count > 0 else None,
    }


@router.get("/execute/{execution_id}/requirement-sheets")
def get_requirement_sheets(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get requirement sheets generated by micro-analysis."""
    from app.models.uc_requirement_sheet import UCRequirementSheet

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id
    ).order_by(UCRequirementSheet.uc_id).all()

    total = len(sheets)
    complete = sum(1 for s in sheets if s.analysis_complete)
    total_latency = sum(s.latency_ms or 0 for s in sheets)
    total_cost = sum(s.cost_usd or 0 for s in sheets)

    agent_dist = {}
    complexity_dist = {"simple": 0, "moyenne": 0, "complexe": 0}
    for s in sheets:
        if s.analysis_complete and s.sheet_content:
            agent = s.sheet_content.get("agent_suggere", "unknown")
            agent_dist[agent] = agent_dist.get(agent, 0) + 1
            comp = s.sheet_content.get("complexite", "moyenne")
            if comp in complexity_dist:
                complexity_dist[comp] += 1

    return {
        "execution_id": execution_id,
        "stats": {
            "total": total,
            "analyzed": complete,
            "pending": total - complete,
            "total_latency_ms": total_latency,
            "avg_latency_ms": round(total_latency / max(1, complete)),
            "total_cost_usd": round(total_cost, 4),
            "agent_distribution": agent_dist,
            "complexity_distribution": complexity_dist,
        },
        "sheets": [s.to_dict() for s in sheets],
    }


@router.post("/execute/{execution_id}/synthesize")
async def synthesize_sds_v3(
    execution_id: int,
    project_context: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SDS v3 - Synthesize requirement sheets into professional SDS document."""
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from app.services.sds_synthesis_service import get_sds_synthesis_service

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    if not sheets:
        raise HTTPException(status_code=400, detail="No requirement sheets found. Run /microanalyze first.")

    fiches = []
    for sheet in sheets:
        if sheet.sheet_content:
            fiche = sheet.sheet_content.copy()
            fiche["uc_id"] = sheet.uc_id
            fiches.append(fiche)

    logger.info(f"[SDS v3] Starting synthesis for execution {execution_id}: {len(fiches)} fiches")

    synthesis_service = get_sds_synthesis_service()
    try:
        result = await synthesis_service.synthesize_sds(
            fiches=fiches,
            project_name=project.name,
            project_context=project_context or project.description or "",
        )

        sections_data = [
            {
                "domain": section.domain,
                "content": section.content,
                "uc_count": section.uc_count,
                "objects": section.objects,
                "tokens_used": section.tokens_used,
                "cost_usd": round(section.cost_usd, 4),
                "generation_time_ms": section.generation_time_ms,
            }
            for section in result.sections
        ]

        return {
            "execution_id": execution_id,
            "project_name": result.project_name,
            "total_ucs": result.total_ucs,
            "domains_count": len(sections_data),
            "sections": sections_data,
            "erd_mermaid": result.erd_mermaid,
            "permissions_matrix": result.permissions_matrix,
            "stats": {
                "total_tokens": result.total_tokens,
                "total_cost_usd": round(result.total_cost_usd, 4),
                "generation_time_ms": result.generation_time_ms,
            },
            "generated_at": result.generated_at,
        }

    except Exception as e:
        logger.error(f"[SDS v3] Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.get("/execute/{execution_id}/sds-preview")
def preview_sds_v3(
    execution_id: int,
    format: str = Query("markdown", enum=["markdown", "html"]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview the SDS v3 in Markdown or HTML."""
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from app.services.sds_synthesis_service import get_sds_synthesis_service

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    if not sheets:
        raise HTTPException(status_code=400, detail="No requirement sheets found")

    fiches = [s.sheet_content for s in sheets if s.sheet_content]

    synthesis_service = get_sds_synthesis_service()
    domains = synthesis_service.aggregate_by_domain(fiches)

    md_lines = [
        f"# SDS - {project.name}",
        "",
        f"**Date de generation**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Use Cases analyses**: {len(fiches)}",
        f"**Domaines identifies**: {len(domains)}",
        "",
        "---",
        "",
        "## Table des matieres",
        "",
    ]

    for i, (name, group) in enumerate(domains.items(), 1):
        md_lines.append(f"{i}. [{name}](#{name.lower().replace(' ', '-')}) ({group.uc_count} UCs)")

    md_lines.extend(["", "---", "", "## Resume par domaine", ""])

    for name, group in domains.items():
        summary = group.to_summary()
        md_lines.extend([
            f"### {name}",
            "",
            f"- **Use Cases**: {summary['uc_count']}",
            f"- **Objets SF**: {', '.join(summary['objects'][:5])}{'...' if len(summary['objects']) > 5 else ''}",
            f"- **Agents assignes**: {', '.join(summary['agents'])}",
            f"- **Complexite**: Simple={summary['complexity_distribution']['simple']}, "
            f"Moyenne={summary['complexity_distribution']['moyenne']}, "
            f"Complexe={summary['complexity_distribution']['complexe']}",
            "",
        ])

    markdown_content = "\n".join(md_lines)

    if format == "html":
        import re

        html = markdown_content
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)
        html = html.replace("\n\n", "</p><p>").replace("\n", "<br>")
        html = f"<html><body style='font-family: Arial; max-width: 800px; margin: auto; padding: 20px;'><p>{html}</p></body></html>"
        return Response(content=html, media_type="text/html")

    return {
        "execution_id": execution_id,
        "format": format,
        "content": markdown_content,
        "domains_summary": [g.to_summary() for g in domains.values()],
    }


@router.get("/execute/{execution_id}/domains-summary")
def get_domains_summary(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get domain aggregation summary for pre-synthesis preview."""
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from app.services.sds_synthesis_service import get_sds_synthesis_service

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    if not sheets:
        return {
            "execution_id": execution_id,
            "total_fiches": 0,
            "domains": [],
            "message": "No requirement sheets found. Run /microanalyze first.",
        }

    fiches = [s.sheet_content for s in sheets if s.sheet_content]

    synthesis_service = get_sds_synthesis_service()
    domains = synthesis_service.aggregate_by_domain(fiches)

    return {
        "execution_id": execution_id,
        "total_fiches": len(fiches),
        "domains_count": len(domains),
        "domains": [g.to_summary() for g in domains.values()],
        "estimated_cost_usd": round(len(domains) * 0.10, 2),
        "estimated_time_sec": len(domains) * 30,
    }


@router.post("/execute/{execution_id}/generate-docx")
async def generate_sds_docx(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SDS v3 - Generate professional DOCX document from synthesis."""
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from app.services.sds_synthesis_service import get_sds_synthesis_service
    from app.services.sds_docx_generator_v3 import generate_sds_docx_v3
    from app.models.agent_deliverable import AgentDeliverable
    import tempfile
    import os

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    if not sheets:
        raise HTTPException(status_code=400, detail="No requirement sheets found. Run /microanalyze and /synthesize first.")

    fiches = []
    for sheet in sheets:
        if sheet.sheet_content:
            fiche = sheet.sheet_content.copy()
            fiche["uc_id"] = sheet.uc_id
            fiches.append(fiche)

    logger.info(f"[DOCX Gen] Starting for execution {execution_id}: {len(fiches)} fiches")

    synthesis_service = get_sds_synthesis_service()
    try:
        synthesis_result = await synthesis_service.synthesize_sds(
            fiches=fiches,
            project_name=project.name,
            project_context=project.description or "",
        )

        synthesis_dict = {
            "project_name": synthesis_result.project_name,
            "total_ucs": synthesis_result.total_ucs,
            "domains_count": len(synthesis_result.sections),
            "sections": [
                {
                    "domain": s.domain,
                    "content": s.content,
                    "uc_count": s.uc_count,
                    "objects": s.objects,
                    "tokens_used": s.tokens_used,
                    "cost_usd": s.cost_usd,
                    "generation_time_ms": s.generation_time_ms,
                }
                for s in synthesis_result.sections
            ],
            "erd_mermaid": synthesis_result.erd_mermaid,
            "permissions_matrix": synthesis_result.permissions_matrix,
            "stats": {
                "total_tokens": synthesis_result.total_tokens,
                "total_cost_usd": synthesis_result.total_cost_usd,
                "generation_time_ms": synthesis_result.generation_time_ms,
            },
            "generated_at": synthesis_result.generated_at,
        }

        wbs_data = None
        wbs_deliverable = db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == execution_id,
            AgentDeliverable.agent_name == "architect",
            AgentDeliverable.artifact_type == "wbs",
        ).first()
        if wbs_deliverable and wbs_deliverable.content:
            wbs_data = wbs_deliverable.content

        project_info = {
            "salesforce_product": project.salesforce_product,
            "organization_type": project.organization_type,
        }

        output_dir = tempfile.mkdtemp(prefix="sds_docx_")
        safe_name = "".join(c if c.isalnum() or c in "- _" else "_" for c in project.name)
        output_path = os.path.join(output_dir, f"SDS_{safe_name}_{execution_id}.docx")

        generate_sds_docx_v3(
            project_name=project.name,
            synthesis_result=synthesis_dict,
            wbs_data=wbs_data,
            project_info=project_info,
            output_path=output_path,
        )

        logger.info(f"[DOCX Gen] Generated: {output_path}")

        return FileResponse(
            path=output_path,
            filename=f"SDS_{safe_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="SDS_{safe_name}.docx"'},
        )

    except Exception as e:
        logger.error(f"[DOCX Gen] Failed: {e}")
        raise HTTPException(status_code=500, detail=f"DOCX generation failed: {str(e)}")


@router.get("/execute/{execution_id}/download-sds-v3")
async def download_sds_v3(
    execution_id: int,
    format: str = Query("docx", enum=["docx", "pdf"]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the generated SDS v3 document."""
    import os
    import glob

    if format == "pdf":
        raise HTTPException(status_code=501, detail="PDF format not yet implemented. Use 'docx' format.")

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    output_dir = str(settings.OUTPUT_DIR / "sds_v3")
    pattern = f"{output_dir}/SDS_*_{execution_id}.docx"
    existing_files = glob.glob(pattern)

    if existing_files:
        output_path = existing_files[0]
        safe_name = "".join(c if c.isalnum() or c in "- _" else "_" for c in project.name)
        return FileResponse(
            path=output_path,
            filename=f"SDS_{safe_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="SDS_{safe_name}.docx"'},
        )

    return await generate_sds_docx(execution_id, db, current_user)


@router.post("/execute/{execution_id}/generate-sds-v3")
async def generate_sds_v3_full_pipeline(
    execution_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SDS v3 - Full pipeline in a single request."""
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from app.models.deliverable_item import DeliverableItem
    from app.services.sds_synthesis_service import get_sds_synthesis_service
    from app.services.sds_docx_generator_v3 import generate_sds_docx_v3
    from app.services.uc_analyzer_service import get_uc_analyzer
    import tempfile
    import os
    import time

    start_time = time.time()

    execution, project = verify_execution_project_access(execution_id, current_user.id, db)

    logger.info(f"[SDS v3] Starting full pipeline for execution {execution_id}")

    # Step 1: Check Use Cases
    use_cases = db.query(DeliverableItem).filter(
        DeliverableItem.execution_id == execution_id,
        DeliverableItem.item_type == "use_case",
    ).all()

    if not use_cases:
        raise HTTPException(status_code=400, detail="No Use Cases found. Please run the BA phase first (Olivia).")

    logger.info(f"[SDS v3] Found {len(use_cases)} Use Cases")

    # Step 2: Micro-analysis
    existing_sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).count()

    if existing_sheets < len(use_cases):
        logger.info(f"[SDS v3] Running micro-analysis ({existing_sheets}/{len(use_cases)} done)")
        try:
            analyzer = get_uc_analyzer()
            uc_dicts = []
            for uc in use_cases:
                existing = db.query(UCRequirementSheet).filter(
                    UCRequirementSheet.execution_id == execution_id,
                    UCRequirementSheet.uc_id == uc.item_id,
                    UCRequirementSheet.analysis_complete == True,
                ).first()
                if existing:
                    continue

                parsed = uc.content_parsed or {}
                uc_dict = {
                    "id": uc.item_id,
                    "uc_id": uc.item_id,
                    "title": parsed.get("title", uc.title or ""),
                    "parent_br_id": uc.parent_ref,
                }
                if isinstance(parsed, dict):
                    uc_dict.update(parsed)
                uc_dicts.append(uc_dict)

            if uc_dicts:
                logger.info(f"[SDS v3] Analyzing {len(uc_dicts)} UCs")
                results = await analyzer.analyze_batch(uc_dicts)

                # P7: Single transaction for all sheet saves
                try:
                    for (fiche, llm_response), uc_dict in zip(results, uc_dicts):
                        sheet = UCRequirementSheet(
                            execution_id=execution_id,
                            uc_id=fiche.uc_id,
                            uc_title=fiche.titre or uc_dict.get("title", ""),
                            parent_br_id=uc_dict.get("parent_br_id"),
                            sheet_content=fiche.to_dict(),
                            analysis_complete=not bool(fiche.error),
                            analysis_error=fiche.error,
                            llm_provider=llm_response.provider if llm_response else "local",
                            llm_model=llm_response.model_id if llm_response else "mistral:7b",
                            tokens_in=llm_response.tokens_in if llm_response else 0,
                            tokens_out=llm_response.tokens_out if llm_response else 0,
                            cost_usd=llm_response.cost_usd if llm_response else 0.0,
                            latency_ms=llm_response.latency_ms if llm_response else 0,
                        )
                        db.add(sheet)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

        except Exception as e:
            logger.error(f"[SDS v3] Micro-analysis failed: {e}")
            raise HTTPException(status_code=500, detail=f"Micro-analysis failed: {str(e)}")

    # Step 3: Load all sheets
    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True,
    ).all()

    fiches = []
    for sheet in sheets:
        if sheet.sheet_content:
            fiche = sheet.sheet_content.copy()
            fiche["uc_id"] = sheet.uc_id
            fiches.append(fiche)

    logger.info(f"[SDS v3] Loaded {len(fiches)} requirement sheets")

    # Step 4: Claude synthesis
    try:
        synthesis_service = get_sds_synthesis_service()
        synthesis_result = await synthesis_service.synthesize_sds(
            fiches=fiches,
            project_name=project.name,
            project_context=project.description or "",
        )
        logger.info(f"[SDS v3] Synthesis complete: {len(synthesis_result.sections)} sections, ${synthesis_result.total_cost_usd:.4f}")
    except Exception as e:
        logger.error(f"[SDS v3] Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")

    # Step 5: DOCX generation
    try:
        synthesis_dict = {
            "project_name": synthesis_result.project_name,
            "total_ucs": synthesis_result.total_ucs,
            "domains_count": len(synthesis_result.sections),
            "sections": [
                {"domain": s.domain, "content": s.content, "uc_count": s.uc_count, "objects": s.objects}
                for s in synthesis_result.sections
            ],
            "erd_mermaid": synthesis_result.erd_mermaid,
            "permissions_matrix": synthesis_result.permissions_matrix,
            "stats": {
                "total_tokens": synthesis_result.total_tokens,
                "total_cost_usd": synthesis_result.total_cost_usd,
                "generation_time_ms": synthesis_result.generation_time_ms,
            },
            "generated_at": synthesis_result.generated_at,
        }

        output_dir = str(settings.OUTPUT_DIR / "sds_v3")
        os.makedirs(output_dir, exist_ok=True)

        safe_name = "".join(c if c.isalnum() or c in "- _" else "_" for c in project.name)
        output_path = os.path.join(output_dir, f"SDS_{safe_name}_{execution_id}.docx")

        generate_sds_docx_v3(
            project_name=project.name,
            synthesis_result=synthesis_dict,
            project_info={
                "salesforce_product": project.salesforce_product or "Salesforce",
                "organization_type": project.organization_type or "Enterprise",
            },
            output_path=output_path,
        )

        # P7: Execution update in try/except
        try:
            execution.sds_document_path = output_path
            db.commit()
        except Exception:
            db.rollback()
            raise

        total_time = time.time() - start_time
        logger.info(f"[SDS v3] DOCX generated: {output_path}")

        return {
            "status": "success",
            "execution_id": execution_id,
            "project_name": project.name,
            "pipeline_summary": {
                "use_cases_processed": len(use_cases),
                "requirement_sheets": len(fiches),
                "domains_generated": len(synthesis_result.sections),
                "domains": [s.domain for s in synthesis_result.sections],
            },
            "costs": {
                "synthesis_cost_usd": synthesis_result.total_cost_usd,
                "total_tokens": synthesis_result.total_tokens,
            },
            "timing": {
                "total_time_seconds": round(total_time, 1),
                "synthesis_time_ms": synthesis_result.generation_time_ms,
            },
            "output": {
                "docx_path": output_path,
                "download_url": f"/api/pm/execute/{execution_id}/download-sds-v3",
            },
        }

    except Exception as e:
        logger.error(f"[SDS v3] DOCX generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"DOCX generation failed: {str(e)}")
