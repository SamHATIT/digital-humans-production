"""Change Request Service for impact analysis and targeted re-generation using Claude."""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus
from app.models.execution import Execution, ExecutionStatus
from app.models.change_request import ChangeRequest
from app.models.business_requirement import BusinessRequirement
from app.models.agent_deliverable import AgentDeliverable
from app.models.sds_version import SDSVersion
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Cost estimates per agent (in USD) - based on typical token usage
AGENT_COSTS = {
    "pm": 0.10,
    "ba": 0.80,
    "architect": 1.20,
    "apex": 0.60,
    "lwc": 0.50,
    "admin": 0.40,
    "qa": 0.50,
    "devops": 0.30,
    "data": 0.40,
    "trainer": 0.30,
}

# Category to likely impacted agents mapping
CATEGORY_AGENT_MAP = {
    "business_rule": ["ba", "architect", "apex", "admin", "qa"],
    "data_model": ["architect", "apex", "data", "qa"],
    "process": ["ba", "architect", "admin", "qa"],
    "ui_ux": ["lwc", "qa"],
    "integration": ["architect", "apex", "devops"],
    "security": ["architect", "admin", "qa"],
    "other": ["ba", "architect"],
}


class ChangeRequestService:
    """Service for handling Change Request analysis and targeted re-generation."""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
    
    def analyze_impact(self, cr_id: int) -> Dict[str, Any]:
        """
        Analyze the impact of a change request using Claude.
        Returns structured impact analysis with affected items and cost estimate.
        """
        logger.info(f"[CR Service] ========== IMPACT ANALYSIS START ==========")
        logger.info(f"[CR Service] Analyzing CR ID: {cr_id}")
        
        # Load CR
        cr = self.db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
        if not cr:
            logger.error(f"[CR Service] CR {cr_id} not found")
            return {"success": False, "error": "CR not found"}
        
        logger.info(f"[CR Service] CR: {cr.cr_number} - {cr.title}")
        logger.info(f"[CR Service] Category: {cr.category}, Priority: {cr.priority}")
        
        # Load project context
        project = self.db.query(Project).filter(Project.id == cr.project_id).first()
        if not project:
            logger.error(f"[CR Service] Project {cr.project_id} not found")
            return {"success": False, "error": "Project not found"}
        
        logger.info(f"[CR Service] Project: {project.name}")
        
        # Load related BR if specified
        related_br_text = ""
        if cr.related_br_id:
            br = self.db.query(BusinessRequirement).filter(
                BusinessRequirement.id == cr.related_br_id
            ).first()
            if br:
                related_br_text = f"{br.br_id}: {br.requirement}"
                logger.info(f"[CR Service] Related BR: {br.br_id}")
        
        # Load all BRs for context
        brs = self.db.query(BusinessRequirement).filter(
            BusinessRequirement.project_id == cr.project_id
        ).all()
        logger.info(f"[CR Service] Total BRs in project: {len(brs)}")
        
        # Load deliverables for context
        execution = self.db.query(Execution).filter(
            Execution.project_id == cr.project_id
        ).order_by(Execution.created_at.desc()).first()
        
        deliverables_context = ""
        if execution:
            deliverables = self.db.query(AgentDeliverable).filter(
                AgentDeliverable.execution_id == execution.id
            ).all()
            logger.info(f"[CR Service] Found {len(deliverables)} deliverables from execution {execution.id}")
            
            for d in deliverables:
                deliverables_context += f"- {d.deliverable_type}\n"
        
        # Build analysis prompt
        prompt = self._build_impact_analysis_prompt(cr, project, brs, related_br_text, deliverables_context)
        logger.info(f"[CR Service] Analysis prompt length: {len(prompt)} chars")
        
        system_prompt = """Tu es Sophie, Project Manager experte en implémentation Salesforce.
Tu dois analyser l'impact d'une demande de modification (Change Request) sur un projet existant.

Tu dois retourner UNIQUEMENT un JSON valide avec cette structure exacte:
{
    "summary": "Résumé de l'impact en 2-3 phrases",
    "affected_brs": ["BR-001", "BR-002"],
    "affected_use_cases": ["UC-001-01", "UC-002-01"],
    "affected_architecture_sections": ["data_model", "security", "integrations"],
    "agents_to_rerun": ["ba", "architect", "apex"],
    "risk_level": "low|medium|high",
    "estimated_effort": "Estimation de l'effort en jours-homme",
    "recommendations": ["Recommandation 1", "Recommandation 2"],
    "dependencies": "Description des dépendances entre éléments impactés"
}

Sois précis et factuel. Base ton analyse sur les éléments fournis."""
        
        try:
            logger.info(f"[CR Service] Calling Claude for impact analysis...")
            
            response = self.llm_service.generate(
                prompt=prompt,
                agent_type="sophie",  # ORCHESTRATOR tier
                system_prompt=system_prompt,
                max_tokens=2000,
                temperature=0.3  # Low temperature for structured output
            )
            
            response_text = response["content"]
            tokens_used = response.get("tokens_used", 0)
            
            logger.info(f"[CR Service] Claude response: {len(response_text)} chars, {tokens_used} tokens")
            
            # Parse JSON from response
            impact_data = self._parse_impact_json(response_text)
            
            if not impact_data:
                logger.warning(f"[CR Service] Could not parse JSON, using category-based fallback")
                impact_data = self._fallback_impact_analysis(cr)
            
            logger.info(f"[CR Service] Impact analysis result:")
            logger.info(f"[CR Service]   - Risk level: {impact_data.get('risk_level')}")
            logger.info(f"[CR Service]   - Agents to rerun: {impact_data.get('agents_to_rerun')}")
            logger.info(f"[CR Service]   - Affected BRs: {impact_data.get('affected_brs')}")
            
            # Calculate cost estimate
            agents_to_rerun = impact_data.get("agents_to_rerun", [])
            estimated_cost = sum(AGENT_COSTS.get(a, 0.5) for a in agents_to_rerun)
            estimated_cost += 0.50  # SDS regeneration cost
            
            logger.info(f"[CR Service] Estimated cost: ${estimated_cost:.2f}")
            
            # Update CR in database
            cr.status = "analyzed"
            cr.analyzed_at = datetime.now(timezone.utc)
            cr.impact_analysis = impact_data
            cr.estimated_cost = Decimal(str(round(estimated_cost, 2)))
            cr.agents_to_rerun = agents_to_rerun
            self.db.commit()
            
            logger.info(f"[CR Service] CR {cr.cr_number} updated with analysis")
            logger.info(f"[CR Service] ========== IMPACT ANALYSIS COMPLETE ==========")
            
            return {
                "success": True,
                "cr_number": cr.cr_number,
                "impact_analysis": impact_data,
                "estimated_cost": float(estimated_cost),
                "agents_to_rerun": agents_to_rerun,
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            logger.error(f"[CR Service] Impact analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Use fallback
            impact_data = self._fallback_impact_analysis(cr)
            agents_to_rerun = impact_data.get("agents_to_rerun", [])
            estimated_cost = sum(AGENT_COSTS.get(a, 0.5) for a in agents_to_rerun) + 0.50
            
            cr.status = "analyzed"
            cr.analyzed_at = datetime.now(timezone.utc)
            cr.impact_analysis = impact_data
            cr.estimated_cost = Decimal(str(round(estimated_cost, 2)))
            cr.agents_to_rerun = agents_to_rerun
            self.db.commit()
            
            return {
                "success": True,
                "cr_number": cr.cr_number,
                "impact_analysis": impact_data,
                "estimated_cost": float(estimated_cost),
                "agents_to_rerun": agents_to_rerun,
                "fallback_used": True
            }
    
    def _build_impact_analysis_prompt(
        self,
        cr: ChangeRequest,
        project: Project,
        brs: List[BusinessRequirement],
        related_br_text: str,
        deliverables_context: str
    ) -> str:
        """Build the prompt for impact analysis."""
        
        brs_text = "\n".join([
            f"- {br.br_id}: [{br.category}] {br.requirement[:100]}..."
            for br in brs[:20]
        ])
        
        prompt = f"""Analyse l'impact de cette Change Request sur le projet Salesforce.

## Projet
- Nom: {project.name}
- Produit: {project.salesforce_product}
- Type: {project.organization_type}

## Change Request
- Numéro: {cr.cr_number}
- Catégorie: {cr.category}
- Priorité: {cr.priority}
- Titre: {cr.title}
- Description: {cr.description}
- BR concerné: {related_br_text or "Non spécifié"}

## Business Requirements existants
{brs_text}

## Livrables actuels
{deliverables_context}

## Ta tâche
Analyse les impacts de cette modification et retourne un JSON structuré avec:
1. Les BRs potentiellement affectés (ceux qui ont des dépendances avec la modification)
2. Les Use Cases qui devront être mis à jour
3. Les sections d'architecture impactées (data_model, security, flows, integrations, reports, etc.)
4. Les agents qui devront re-générer leur partie
5. Le niveau de risque
6. Les recommandations

Retourne UNIQUEMENT le JSON, sans texte avant ou après."""
        
        return prompt
    
    def _parse_impact_json(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from Claude's response."""
        try:
            # Try to find JSON in response
            text = response_text.strip()
            
            # Remove markdown code blocks if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text.strip())
            
        except Exception as e:
            logger.warning(f"[CR Service] JSON parse error: {e}")
            return None
    
    def _fallback_impact_analysis(self, cr: ChangeRequest) -> Dict:
        """Fallback impact analysis based on category."""
        agents = CATEGORY_AGENT_MAP.get(cr.category, ["ba", "architect"])
        
        risk_level = "medium"
        if cr.priority in ["high", "critical"]:
            risk_level = "high"
        elif cr.priority == "low":
            risk_level = "low"
        
        return {
            "summary": f"Modification de type {cr.category} nécessitant une mise à jour des éléments concernés.",
            "affected_brs": [],
            "affected_use_cases": [],
            "affected_architecture_sections": [cr.category],
            "agents_to_rerun": agents,
            "risk_level": risk_level,
            "estimated_effort": "1-2 jours",
            "recommendations": [
                "Valider les impacts avec l'équipe technique",
                "Effectuer des tests de non-régression après modification"
            ],
            "dependencies": "Analyse automatique basée sur la catégorie"
        }
    
    async def process_change_request(self, cr_id: int) -> Dict[str, Any]:
        """
        Process an approved CR by triggering targeted re-generation.
        """
        logger.info(f"[CR Service] ========== PROCESSING CR START ==========")
        logger.info(f"[CR Service] Processing CR ID: {cr_id}")
        
        # Load CR
        cr = self.db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
        if not cr:
            logger.error(f"[CR Service] CR {cr_id} not found")
            return {"success": False, "error": "CR not found"}
        
        if cr.status != "approved":
            logger.error(f"[CR Service] CR {cr_id} not in approved status: {cr.status}")
            return {"success": False, "error": "CR must be approved before processing"}
        
        logger.info(f"[CR Service] CR: {cr.cr_number} - {cr.title}")
        logger.info(f"[CR Service] Agents to rerun: {cr.agents_to_rerun}")
        
        # Update status to processing
        cr.status = "processing"
        self.db.commit()
        
        try:
            # Get project and latest execution
            project = self.db.query(Project).filter(Project.id == cr.project_id).first()
            execution = self.db.query(Execution).filter(
                Execution.project_id == cr.project_id
            ).order_by(Execution.created_at.desc()).first()
            
            if not execution:
                logger.error(f"[CR Service] No execution found for project {cr.project_id}")
                return {"success": False, "error": "No execution found"}
            
            logger.info(f"[CR Service] Using execution {execution.id} as base")
            
            # Import orchestrator service
            from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2
            
            # Create orchestrator and run targeted re-generation
            orchestrator = PMOrchestratorServiceV2(self.db)
            
            result = await orchestrator.execute_targeted_regeneration(
                execution_id=execution.id,
                project_id=cr.project_id,
                agents_to_run=cr.agents_to_rerun or [],
                change_request=cr
            )
            
            if result.get("success"):
                # Update CR
                cr.status = "completed"
                cr.completed_at = datetime.now(timezone.utc)
                cr.resulting_sds_version_id = result.get("new_sds_version")
                cr.resolution_notes = f"Re-génération terminée. Nouveau SDS v{result.get('new_sds_version')}"
                
                logger.info(f"[CR Service] CR {cr.cr_number} completed successfully")
                logger.info(f"[CR Service] New SDS version: {result.get('new_sds_version')}")
            else:
                cr.status = "analyzed"  # Revert to analyzed so it can be retried
                cr.resolution_notes = f"Échec: {result.get('error')}"
                logger.error(f"[CR Service] CR processing failed: {result.get('error')}")
            
            self.db.commit()
            
            logger.info(f"[CR Service] ========== PROCESSING CR COMPLETE ==========")
            
            return result
            
        except Exception as e:
            logger.error(f"[CR Service] Processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            cr.status = "analyzed"
            cr.resolution_notes = f"Erreur: {str(e)}"
            self.db.commit()
            
            return {"success": False, "error": str(e)}
