"""
UC Analyzer Service - Micro-analyse des Use Cases avec LLM local (SDS v3)
Chaque UC → Fiche Besoin JSON (Mistral local) → Synthèse (Claude)
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.llm_router_service import (
    LLMRouterService, LLMRequest, LLMResponse, TaskComplexity, get_llm_router
)
from app.models.uc_requirement_sheet import UCRequirementSheet

logger = logging.getLogger(__name__)

FICHE_BESOIN_PROMPT = """Tu es un analyste Salesforce. Analyse ce Use Case et génère une Fiche Besoin JSON.

USE CASE:
{uc_json}

RÈGLES DE ROUTING AGENT (CRITIQUES):
- raj (Admin): Configuration standard, Flows, Validation Rules, Permission Sets, Dashboards, Reports, objets custom simples, TOUT ce qui est "No Code"
- diego (Apex Dev): Triggers, Classes Apex, Batch, Queueable, logique métier COMPLEXE, intégrations API codées
- zara (LWC Dev): Composants Lightning (LWC), interfaces utilisateur CUSTOM, pages Lightning personnalisées
- aisha (Data): Migration de données, Data Cloud, ETL, intégrations externes massives
- elena (QA): Tests unitaires, tests d'intégration, plans de test
- jordan (DevOps): Déploiement, CI/CD, packaging, environnements
- lucas (Training): Formation, documentation utilisateur, guides

IMPORTANT: 
- Si sf_automation.type = "None" ou "Flow" → raj (PAS diego)
- Si c'est de la config standard (objets, champs, page layouts) → raj
- Diego UNIQUEMENT si code Apex explicitement requis

Génère UNIQUEMENT un JSON valide (pas de markdown, pas d'explication) avec cette structure:
{{
  "uc_id": "{uc_id}",
  "titre": "Titre court du besoin (max 100 caractères)",
  "acteur": "Qui effectue l'action",
  "objectif": "Ce que l'utilisateur veut accomplir (1-2 phrases)",
  "objets_salesforce": ["Liste des objets SF impliqués"],
  "champs_cles": ["Champs importants à créer/modifier"],
  "automatisations": ["Type: Flow, Trigger, Apex, LWC, etc."],
  "regles_metier": ["Contraintes et validations métier"],
  "complexite": "simple|moyenne|complexe",
  "agent_suggere": "diego|zara|raj|aisha|elena|jordan|lucas",
  "justification_agent": "Explication courte du choix d'agent"
}}

JSON:"""


@dataclass
class FicheBesoin:
    uc_id: str
    titre: str
    acteur: str
    objectif: str
    objets_salesforce: List[str]
    champs_cles: List[str]
    automatisations: List[str]
    regles_metier: List[str]
    complexite: str
    agent_suggere: str
    justification_agent: str = ""
    raw_response: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uc_id": self.uc_id,
            "titre": self.titre,
            "acteur": self.acteur,
            "objectif": self.objectif,
            "objets_salesforce": self.objets_salesforce,
            "champs_cles": self.champs_cles,
            "automatisations": self.automatisations,
            "regles_metier": self.regles_metier,
            "complexite": self.complexite,
            "agent_suggere": self.agent_suggere,
            "justification_agent": self.justification_agent
        }


class UCAnalyzerService:
    """Service pour analyser les UCs et générer des Fiches Besoin"""
    
    def __init__(self):
        self.router = get_llm_router()
        self.stats = {"total": 0, "success": 0, "failed": 0, "total_latency_ms": 0, "total_cost_usd": 0.0}
    
    async def analyze_uc(self, uc: Dict[str, Any]) -> tuple[FicheBesoin, Optional[LLMResponse]]:
        """Analyse un UC et génère sa Fiche Besoin. Retourne aussi la réponse LLM pour les métadonnées."""
        uc_id = uc.get("id", uc.get("uc_id", "UC-???"))
        
        prompt = FICHE_BESOIN_PROMPT.format(
            uc_json=json.dumps(uc, ensure_ascii=False, indent=2),
            uc_id=uc_id
        )
        
        response: Optional[LLMResponse] = None
        try:
            response = await self.router.complete(LLMRequest(
                prompt=prompt,
                task_type=TaskComplexity.SIMPLE,
                max_tokens=600,
                temperature=0.2
            ))
            
            self.stats["total"] += 1
            self.stats["total_latency_ms"] += response.latency_ms
            self.stats["total_cost_usd"] += response.cost_usd
            
            if not response.success:
                self.stats["failed"] += 1
                return FicheBesoin(
                    uc_id=uc_id, titre="", acteur="", objectif="",
                    objets_salesforce=[], champs_cles=[], automatisations=[],
                    regles_metier=[], complexite="", agent_suggere="",
                    error=response.error
                ), response
            
            # Parse JSON response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            # Nettoyage supplémentaire
            content = content.strip()
            if content.endswith("```"):
                content = content[:-3].strip()
            
            data = json.loads(content)
            self.stats["success"] += 1
            
            return FicheBesoin(
                uc_id=data.get("uc_id", uc_id),
                titre=data.get("titre", ""),
                acteur=data.get("acteur", ""),
                objectif=data.get("objectif", ""),
                objets_salesforce=data.get("objets_salesforce", []),
                champs_cles=data.get("champs_cles", []),
                automatisations=data.get("automatisations", []),
                regles_metier=data.get("regles_metier", []),
                complexite=data.get("complexite", "moyenne"),
                agent_suggere=data.get("agent_suggere", "raj"),
                justification_agent=data.get("justification_agent", ""),
                raw_response=response.content
            ), response
            
        except json.JSONDecodeError as e:
            self.stats["failed"] += 1
            logger.warning(f"[UCAnalyzer] JSON parse error for {uc_id}: {e}")
            return FicheBesoin(
                uc_id=uc_id, titre="", acteur="", objectif="",
                objets_salesforce=[], champs_cles=[], automatisations=[],
                regles_metier=[], complexite="", agent_suggere="",
                raw_response=response.content if response else None,
                error=f"JSON parse error: {e}"
            ), response
        except Exception as e:
            self.stats["failed"] += 1
            logger.error(f"[UCAnalyzer] Error analyzing {uc_id}: {e}")
            return FicheBesoin(
                uc_id=uc_id, titre="", acteur="", objectif="",
                objets_salesforce=[], champs_cles=[], automatisations=[],
                regles_metier=[], complexite="", agent_suggere="",
                error=str(e)
            ), response
    
    async def analyze_batch(
        self, 
        use_cases: List[Dict[str, Any]], 
        concurrency: int = 1
    ) -> List[tuple[FicheBesoin, Optional[LLMResponse]]]:
        """Analyse un batch de UCs (séquentiel pour LLM local)"""
        results = []
        for i, uc in enumerate(use_cases):
            uc_id = uc.get("id", uc.get("uc_id", f"UC-{i+1}"))
            logger.info(f"[UCAnalyzer] Analyzing UC {i+1}/{len(use_cases)}: {uc_id}")
            result = await self.analyze_uc(uc)
            results.append(result)
        return results
    
    async def analyze_and_save(
        self,
        db: AsyncSession,
        execution_id: int,
        use_cases: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[UCRequirementSheet]:
        """Analyse les UCs et sauvegarde en base"""
        saved_sheets = []
        total = len(use_cases)
        
        for i, uc in enumerate(use_cases):
            uc_id = uc.get("id", uc.get("uc_id", f"UC-{i+1}"))
            uc_title = uc.get("title", uc.get("name", ""))
            parent_br = uc.get("parent_br_id", uc.get("br_id", ""))
            
            logger.info(f"[UCAnalyzer] Analyzing {i+1}/{total}: {uc_id}")
            
            # Vérifier si déjà analysé (pour reprise)
            existing = await db.execute(
                select(UCRequirementSheet).where(
                    UCRequirementSheet.execution_id == execution_id,
                    UCRequirementSheet.uc_id == uc_id
                )
            )
            existing_sheet = existing.scalar_one_or_none()
            if existing_sheet and existing_sheet.analysis_complete:
                logger.info(f"[UCAnalyzer] {uc_id} already analyzed, skipping")
                saved_sheets.append(existing_sheet)
                if progress_callback:
                    await progress_callback(i + 1, total, uc_id, "skipped")
                continue
            
            # Analyser
            fiche, llm_response = await self.analyze_uc(uc)
            
            # Créer ou mettre à jour
            if existing_sheet:
                sheet = existing_sheet
                sheet.uc_title = uc_title or fiche.titre
                sheet.sheet_content = fiche.to_dict()
                sheet.analysis_complete = not bool(fiche.error)
                sheet.analysis_error = fiche.error
                if llm_response:
                    sheet.llm_provider = llm_response.provider
                    sheet.llm_model = llm_response.model
                    sheet.tokens_in = llm_response.tokens_in
                    sheet.tokens_out = llm_response.tokens_out
                    sheet.cost_usd = llm_response.cost_usd
                    sheet.latency_ms = llm_response.latency_ms
            else:
                sheet = UCRequirementSheet(
                    execution_id=execution_id,
                    uc_id=uc_id,
                    uc_title=uc_title or fiche.titre,
                    parent_br_id=parent_br,
                    sheet_content=fiche.to_dict(),
                    analysis_complete=not bool(fiche.error),
                    analysis_error=fiche.error,
                    llm_provider=llm_response.provider if llm_response else None,
                    llm_model=llm_response.model if llm_response else None,
                    tokens_in=llm_response.tokens_in if llm_response else 0,
                    tokens_out=llm_response.tokens_out if llm_response else 0,
                    cost_usd=llm_response.cost_usd if llm_response else 0.0,
                    latency_ms=llm_response.latency_ms if llm_response else 0
                )
                db.add(sheet)
            
            await db.commit()
            await db.refresh(sheet)
            saved_sheets.append(sheet)
            
            if progress_callback:
                status = "success" if sheet.analysis_complete else "error"
                await progress_callback(i + 1, total, uc_id, status)
        
        return saved_sheets
    
    async def get_sheets_for_execution(
        self, 
        db: AsyncSession, 
        execution_id: int
    ) -> List[UCRequirementSheet]:
        """Récupère toutes les fiches pour une exécution"""
        result = await db.execute(
            select(UCRequirementSheet)
            .where(UCRequirementSheet.execution_id == execution_id)
            .order_by(UCRequirementSheet.uc_id)
        )
        return list(result.scalars().all())
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les stats d'analyse"""
        avg_latency = self.stats["total_latency_ms"] / self.stats["total"] if self.stats["total"] > 0 else 0
        return {
            **self.stats,
            "avg_latency_ms": round(avg_latency),
            "success_rate": round(self.stats["success"] / max(1, self.stats["total"]) * 100, 1)
        }
    
    def format_sheets_for_sds(self, sheets: List[UCRequirementSheet]) -> str:
        """Formate les fiches pour injection dans le prompt de synthèse SDS"""
        formatted = []
        for sheet in sheets:
            if sheet.analysis_complete:
                content = sheet.sheet_content or {}
                formatted.append(f"""
### {sheet.uc_id}: {content.get('titre', sheet.uc_title)}
- **Acteur**: {content.get('acteur', 'N/A')}
- **Objectif**: {content.get('objectif', 'N/A')}
- **Objets SF**: {', '.join(content.get('objets_salesforce', []))}
- **Automatisations**: {', '.join(content.get('automatisations', []))}
- **Complexité**: {content.get('complexite', 'N/A')}
- **Agent BUILD**: {content.get('agent_suggere', 'N/A')}
""")
        return "\n".join(formatted)
    
    def get_agent_distribution(self, sheets: List[UCRequirementSheet]) -> Dict[str, int]:
        """Calcule la distribution des agents suggérés"""
        distribution = {}
        for sheet in sheets:
            if sheet.analysis_complete and sheet.sheet_content:
                agent = sheet.sheet_content.get("agent_suggere", "unknown")
                distribution[agent] = distribution.get(agent, 0) + 1
        return distribution


# Singleton pour réutilisation
_uc_analyzer_instance: Optional[UCAnalyzerService] = None

def get_uc_analyzer() -> UCAnalyzerService:
    """Retourne l'instance singleton du UC Analyzer"""
    global _uc_analyzer_instance
    if _uc_analyzer_instance is None:
        _uc_analyzer_instance = UCAnalyzerService()
    return _uc_analyzer_instance
