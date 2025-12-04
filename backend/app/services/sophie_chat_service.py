"""Sophie Chat Service for contextual project conversations."""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from openai import OpenAI

from app.models.project import Project
from app.models.execution import Execution
from app.models.business_requirement import BusinessRequirement
from app.models.agent_deliverable import AgentDeliverable
from app.models.project_conversation import ProjectConversation

logger = logging.getLogger(__name__)


class SophieChatService:
    """Service for handling chat with Sophie (PM agent)."""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI()
        self.model = "gpt-4o-mini"  # Use mini for chat (cost-effective)
        self.max_context_tokens = 8000
    
    def get_project_context(self, project_id: int, execution_id: Optional[int] = None) -> Dict[str, Any]:
        """Build context from project artifacts for Sophie."""
        context = {}
        
        # Get project
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return context
        
        context["project"] = {
            "name": project.name,
            "description": project.description,
            "salesforce_product": project.salesforce_product,
            "organization_type": project.organization_type,
            "business_requirements_raw": project.business_requirements
        }
        
        # Get execution if not specified
        if not execution_id:
            execution = self.db.query(Execution).filter(
                Execution.project_id == project_id
            ).order_by(Execution.created_at.desc()).first()
            if execution:
                execution_id = execution.id
        
        if execution_id:
            # Get Business Requirements
            brs = self.db.query(BusinessRequirement).filter(
                BusinessRequirement.project_id == project_id
            ).all()
            
            context["business_requirements"] = [
                {
                    "id": br.br_id,
                    "category": br.category,
                    "requirement": br.requirement,
                    "priority": br.priority,
                    "status": br.status
                }
                for br in brs[:20]  # Limit to 20 for context size
            ]
            
            # Get key deliverables (summaries only)
            deliverables = self.db.query(AgentDeliverable).filter(
                AgentDeliverable.execution_id == execution_id
            ).all()
            
            context["deliverables"] = []
            for d in deliverables:
                # Extract key info without full content
                summary = self._extract_deliverable_summary(d)
                if summary:
                    context["deliverables"].append(summary)
        
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
            if "use_cases" in deliverable.deliverable_type:
                uc_content = content.get("content", {})
                ucs = uc_content.get("use_cases", [])
                summary["count"] = len(ucs)
                summary["items"] = [uc.get("title", uc.get("uc_id", "UC")) for uc in ucs[:10]]
            
            elif "architecture" in deliverable.deliverable_type or "design" in deliverable.deliverable_type:
                arch_content = content.get("content", {})
                summary["sections"] = list(arch_content.keys())[:10]
            
            elif "gap" in deliverable.deliverable_type:
                gap_content = content.get("content", {})
                gaps = gap_content.get("gaps", [])
                summary["count"] = len(gaps)
            
            return summary
            
        except Exception as e:
            logger.warning(f"Could not extract summary: {e}")
            return None
    
    def get_conversation_history(self, project_id: int, limit: int = 20) -> List[Dict]:
        """Get recent conversation history."""
        messages = self.db.query(ProjectConversation).filter(
            ProjectConversation.project_id == project_id
        ).order_by(ProjectConversation.created_at.desc()).limit(limit).all()
        
        return [
            {"role": m.role, "content": m.message}
            for m in reversed(messages)
        ]
    
    async def chat(
        self,
        project_id: int,
        user_message: str,
        execution_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a chat message and get Sophie's response."""
        
        # Get context
        context = self.get_project_context(project_id, execution_id)
        history = self.get_conversation_history(project_id, limit=10)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(context)
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        
        try:
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            assistant_message = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Save conversation
            self._save_message(project_id, execution_id, "user", user_message)
            self._save_message(project_id, execution_id, "assistant", assistant_message, tokens_used)
            
            return {
                "success": True,
                "message": assistant_message,
                "tokens_used": tokens_used,
                "context_used": list(context.keys())
            }
            
        except Exception as e:
            logger.error(f"Sophie chat error: {e}")
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
- Description: {project_info.get('description', 'Non disponible')}

**Business Requirements extraits ({len(brs)} BRs):**
"""
        
        for br in brs[:10]:
            prompt += f"- {br.get('id')}: {br.get('requirement', '')[:100]}...\n"
        
        if len(brs) > 10:
            prompt += f"... et {len(brs) - 10} autres BRs\n"
        
        prompt += f"""
**Livrables générés:**
"""
        for d in deliverables:
            prompt += f"- {d.get('type')}: {d.get('count', 'N/A')} éléments\n"
        
        prompt += """
**Ton rôle:**
- Répondre aux questions du client sur le projet et le SDS
- Expliquer les choix techniques et fonctionnels
- Clarifier les Use Cases et l'architecture proposée
- Aider le client à comprendre les impacts de modifications potentielles
- Être professionnelle, claire et pédagogue

**Style de communication:**
- Réponds en français
- Sois concise mais complète
- Utilise des exemples concrets quand c'est utile
- Si tu ne sais pas quelque chose, dis-le honnêtement
- Propose des alternatives quand c'est pertinent
"""
        
        return prompt
    
    def _save_message(
        self,
        project_id: int,
        execution_id: Optional[int],
        role: str,
        message: str,
        tokens_used: int = 0
    ):
        """Save a conversation message to the database."""
        conversation = ProjectConversation(
            project_id=project_id,
            execution_id=execution_id,
            role=role,
            message=message,
            tokens_used=tokens_used,
            model_used=self.model
        )
        self.db.add(conversation)
        self.db.commit()
