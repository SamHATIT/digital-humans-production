"""Sophie Chat Service for contextual project conversations using Claude."""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.execution import Execution
from app.models.business_requirement import BusinessRequirement
from app.models.agent_deliverable import AgentDeliverable
from app.models.project_conversation import ProjectConversation
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class SophieChatService:
    """Service for handling chat with Sophie (PM agent) using Claude."""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()  # Uses Claude by default
        self.max_context_chars = 30000  # Limit context to avoid token overflow
    
    def get_project_context(self, project_id: int, execution_id: Optional[int] = None) -> Dict[str, Any]:
        """Build context from project artifacts for Sophie."""
        logger.info(f"[Sophie Chat] Building context for project {project_id}")
        context = {}
        
        # Get project
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.warning(f"[Sophie Chat] Project {project_id} not found")
            return context
        
        context["project"] = {
            "name": project.name,
            "description": project.description,
            "salesforce_product": project.salesforce_product,
            "organization_type": project.organization_type,
            "business_requirements_raw": (project.business_requirements or "")[:2000]  # Limit
        }
        logger.info(f"[Sophie Chat] Project context loaded: {project.name}")
        
        # Get execution if not specified
        if not execution_id:
            execution = self.db.query(Execution).filter(
                Execution.project_id == project_id
            ).order_by(Execution.created_at.desc()).first()
            if execution:
                execution_id = execution.id
                logger.info(f"[Sophie Chat] Using latest execution: {execution_id}")
        
        if execution_id:
            # Get Business Requirements
            brs = self.db.query(BusinessRequirement).filter(
                BusinessRequirement.project_id == project_id
            ).all()
            
            context["business_requirements"] = [
                {
                    "id": br.br_id,
                    "category": br.category,
                    "requirement": br.requirement[:200],  # Truncate
                    "priority": br.priority.value if br.priority else "should",
                    "status": br.status.value if br.status else "pending"
                }
                for br in brs[:30]  # Limit to 30 BRs
            ]
            logger.info(f"[Sophie Chat] Loaded {len(context['business_requirements'])} BRs")
            
            # Get key deliverables (summaries only)
            deliverables = self.db.query(AgentDeliverable).filter(
                AgentDeliverable.execution_id == execution_id
            ).all()
            
            context["deliverables"] = []
            for d in deliverables:
                summary = self._extract_deliverable_summary(d)
                if summary:
                    context["deliverables"].append(summary)
            logger.info(f"[Sophie Chat] Loaded {len(context['deliverables'])} deliverable summaries")
        
        return context
    
    def _extract_deliverable_summary(self, deliverable: AgentDeliverable) -> Optional[Dict]:
        """Extract a summary from a deliverable for context."""
        try:
            if not deliverable.content:
                return None
            
            content = deliverable.content if isinstance(deliverable.content, dict) else json.loads(deliverable.content)
            
            summary = {
                "type": deliverable.deliverable_type,
                "agent": deliverable.agent_id or "unknown"
            }
            
            # Extract relevant summary based on type
            if "use_cases" in deliverable.deliverable_type.lower():
                uc_content = content.get("content", {})
                ucs = uc_content.get("use_cases", [])
                summary["count"] = len(ucs)
                summary["items"] = [uc.get("title", uc.get("uc_id", "UC"))[:50] for uc in ucs[:10]]
            
            elif "architecture" in deliverable.deliverable_type.lower() or "design" in deliverable.deliverable_type.lower():
                arch_content = content.get("content", {})
                summary["sections"] = list(arch_content.keys())[:10]
            
            elif "gap" in deliverable.deliverable_type.lower():
                gap_content = content.get("content", {})
                gaps = gap_content.get("gaps", [])
                summary["count"] = len(gaps)
            
            elif "wbs" in deliverable.deliverable_type.lower():
                wbs_content = content.get("content", {})
                phases = wbs_content.get("phases", [])
                summary["count"] = len(phases)
                summary["items"] = [p.get("name", "Phase")[:30] for p in phases[:5]]
            
            return summary
            
        except Exception as e:
            logger.warning(f"[Sophie Chat] Could not extract summary: {e}")
            return None
    
    def get_conversation_history(self, project_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation history."""
        messages = self.db.query(ProjectConversation).filter(
            ProjectConversation.project_id == project_id
        ).order_by(ProjectConversation.created_at.desc()).limit(limit).all()
        
        history = [
            {"role": m.role, "content": m.message}
            for m in reversed(messages)
        ]
        logger.info(f"[Sophie Chat] Loaded {len(history)} messages from history")
        return history
    
    async def chat(
        self,
        project_id: int,
        user_message: str,
        execution_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a chat message and get Sophie's response using Claude."""
        logger.info(f"[Sophie Chat] ========== NEW CHAT MESSAGE ==========")
        logger.info(f"[Sophie Chat] Project: {project_id}, Message length: {len(user_message)}")
        
        # Get context
        context = self.get_project_context(project_id, execution_id)
        history = self.get_conversation_history(project_id, limit=6)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(context)
        logger.info(f"[Sophie Chat] System prompt length: {len(system_prompt)} chars")
        
        # Build conversation as single prompt (Claude format)
        conversation_text = ""
        for msg in history:
            role_label = "Client" if msg["role"] == "user" else "Sophie"
            conversation_text += f"\n{role_label}: {msg['content']}\n"
        
        conversation_text += f"\nClient: {user_message}\n\nSophie:"
        
        full_prompt = conversation_text
        logger.info(f"[Sophie Chat] Full prompt length: {len(full_prompt)} chars")
        
        try:
            # Call Claude via LLMService
            logger.info(f"[Sophie Chat] Calling Claude (agent_type=sophie)...")
            
            response = self.llm_service.generate(
                prompt=full_prompt,
                agent_type="sophie",  # Uses ORCHESTRATOR tier = Claude Opus
                system_prompt=system_prompt,
                max_tokens=1500,
                temperature=0.7
            )
            
            assistant_message = response["content"]
            tokens_used = response.get("tokens_used", 0)
            model_used = response.get("model", "unknown")
            
            logger.info(f"[Sophie Chat] Response received: {len(assistant_message)} chars, {tokens_used} tokens")
            logger.info(f"[Sophie Chat] Model used: {model_used}")
            
            # Save conversation
            self._save_message(project_id, execution_id, "user", user_message, 0, model_used)
            self._save_message(project_id, execution_id, "assistant", assistant_message, tokens_used, model_used)
            
            logger.info(f"[Sophie Chat] ========== CHAT COMPLETE ==========")
            
            return {
                "success": True,
                "message": assistant_message,
                "tokens_used": tokens_used,
                "model_used": model_used,
                "context_used": list(context.keys())
            }
            
        except Exception as e:
            logger.error(f"[Sophie Chat] ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "message": "Je suis désolée, une erreur s'est produite. Veuillez réessayer."
            }
    
    def _build_system_prompt(self, context: Dict) -> str:
        """Build Sophie's system prompt with project context."""
        project_info = context.get("project", {})
        brs = context.get("business_requirements", [])
        deliverables = context.get("deliverables", [])
        
        prompt = f"""Tu es Sophie, Project Manager senior chez Digital Humans, spécialisée en implémentation Salesforce.

Tu es en charge du projet "{project_info.get('name', 'ce projet')}" qui est une implémentation {project_info.get('salesforce_product', 'Salesforce')}.

**Contexte du projet:**
- Type d'organisation: {project_info.get('organization_type', 'Non spécifié')}
- Description: {project_info.get('description', 'Non disponible')[:500]}

**Business Requirements validés ({len(brs)} BRs):**
"""
        
        for br in brs[:15]:
            prompt += f"- {br.get('id')}: [{br.get('priority', 'N/A')}] {br.get('requirement', '')[:80]}...\n"
        
        if len(brs) > 15:
            prompt += f"... et {len(brs) - 15} autres BRs\n"
        
        prompt += f"""
**Livrables générés ({len(deliverables)}):**
"""
        for d in deliverables[:8]:
            if d.get('count'):
                prompt += f"- {d.get('type')}: {d.get('count')} éléments\n"
            elif d.get('sections'):
                prompt += f"- {d.get('type')}: sections {', '.join(d.get('sections', [])[:3])}\n"
            else:
                prompt += f"- {d.get('type')}\n"
        
        prompt += """
**Ton rôle:**
- Répondre aux questions du client sur le projet et le SDS (System Design Specification)
- Expliquer les choix techniques et fonctionnels
- Clarifier les Use Cases et l'architecture proposée
- Aider le client à comprendre les impacts de modifications potentielles
- Suggérer des améliorations si pertinent
- Être professionnelle, claire et pédagogue

**Style de communication:**
- Réponds en français
- Sois concise mais complète (2-4 paragraphes max)
- Utilise des exemples concrets quand c'est utile
- Si tu ne sais pas quelque chose, dis-le honnêtement
- Propose des Change Requests si le client suggère des modifications importantes
"""
        
        return prompt
    
    def _save_message(
        self,
        project_id: int,
        execution_id: Optional[int],
        role: str,
        message: str,
        tokens_used: int = 0,
        model_used: str = None
    ):
        """Save a conversation message to the database."""
        conversation = ProjectConversation(
            project_id=project_id,
            execution_id=execution_id,
            role=role,
            message=message,
            tokens_used=tokens_used,
            model_used=model_used
        )
        self.db.add(conversation)
        self.db.commit()
        logger.info(f"[Sophie Chat] Saved {role} message to DB")
