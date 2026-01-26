"""
UC Analyzer Service - Micro-analyse des Use Cases avec LLM local
SDS v3: Chaque UC → Fiche Besoin JSON (Nemo local) → Synthèse (Claude)
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.services.llm_router_service import (
    LLMRouterService, LLMRequest, LLMResponse, TaskComplexity, get_llm_router
)

logger = logging.getLogger(__name__)

FICHE_BESOIN_PROMPT = """Tu es un analyste Salesforce. Analyse ce Use Case et génère une Fiche Besoin JSON.

USE CASE:
{uc_json}

RÈGLES DE ROUTING AGENT:
- raj (Admin): Configuration standard, Flows, Validation Rules, Permission Sets, Dashboards, Reports, objets custom simples
- diego (Apex Dev): Triggers, Classes Apex, Batch, Queueable, logique métier complexe, intégrations API
- zara (LWC Dev): Composants Lightning (LWC), interfaces utilisateur custom, pages Lightning
- aisha (Data): Migration de données, Data Cloud, ETL, intégrations externes, import/export

IMPORTANT: Si sf_automation.type = "None" ou "Flow" → raj (pas diego)

Génère UNIQUEMENT un JSON valide (pas de markdown, pas d'explication) avec cette structure:
{{
  "uc_id": "{uc_id}",
  "titre": "Titre court du besoin",
  "acteur": "Qui effectue l'action",
  "objectif": "Ce que l'utilisateur veut accomplir",
  "objets_salesforce": ["Liste des objets SF impliqués"],
  "champs_cles": ["Champs importants à créer/modifier"],
  "automatisations": ["Flow", "Trigger", "Apex", "LWC si UI custom"],
  "regles_metier": ["Contraintes et validations"],
  "complexite": "simple|moyenne|complexe",
  "agent_suggere": "diego|zara|raj|aisha",
  "justification_agent": "Pourquoi cet agent"
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


class UCAnalyzerService:
    """Service pour analyser les UCs et générer des Fiches Besoin"""
    
    def __init__(self):
        self.router = get_llm_router()
        self.stats = {"total": 0, "success": 0, "failed": 0, "total_latency_ms": 0}
    
    async def analyze_uc(self, uc: Dict[str, Any]) -> FicheBesoin:
        """Analyse un UC et génère sa Fiche Besoin"""
        uc_id = uc.get("id", uc.get("uc_id", "UC-???"))
        
        prompt = FICHE_BESOIN_PROMPT.format(
            uc_json=json.dumps(uc, ensure_ascii=False, indent=2),
            uc_id=uc_id
        )
        
        try:
            response: LLMResponse = await self.router.complete(LLMRequest(
                prompt=prompt,
                task_type=TaskComplexity.SIMPLE,
                max_tokens=600,
                temperature=0.2
            ))
            
            self.stats["total"] += 1
            self.stats["total_latency_ms"] += response.latency_ms
            
            if not response.success:
                self.stats["failed"] += 1
                return FicheBesoin(
                    uc_id=uc_id, titre="", acteur="", objectif="",
                    objets_salesforce=[], champs_cles=[], automatisations=[],
                    regles_metier=[], complexite="", agent_suggere="",
                    error=response.error
                )
            
            # Parse JSON response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
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
            )
            
        except json.JSONDecodeError as e:
            self.stats["failed"] += 1
            logger.warning(f"[UCAnalyzer] JSON parse error for {uc_id}: {e}")
            return FicheBesoin(
                uc_id=uc_id, titre="", acteur="", objectif="",
                objets_salesforce=[], champs_cles=[], automatisations=[],
                regles_metier=[], complexite="", agent_suggere="",
                raw_response=response.content if response else None,
                error=f"JSON parse error: {e}"
            )
        except Exception as e:
            self.stats["failed"] += 1
            logger.error(f"[UCAnalyzer] Error analyzing {uc_id}: {e}")
            return FicheBesoin(
                uc_id=uc_id, titre="", acteur="", objectif="",
                objets_salesforce=[], champs_cles=[], automatisations=[],
                regles_metier=[], complexite="", agent_suggere="",
                error=str(e)
            )
    
    async def analyze_batch(self, use_cases: List[Dict[str, Any]], concurrency: int = 1) -> List[FicheBesoin]:
        """Analyse un batch de UCs"""
        results = []
        for i, uc in enumerate(use_cases):
            logger.info(f"[UCAnalyzer] Analyzing UC {i+1}/{len(use_cases)}")
            fiche = await self.analyze_uc(uc)
            results.append(fiche)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les stats d'analyse"""
        avg_latency = self.stats["total_latency_ms"] / self.stats["total"] if self.stats["total"] > 0 else 0
        return {
            **self.stats,
            "avg_latency_ms": round(avg_latency),
            "success_rate": round(self.stats["success"] / max(1, self.stats["total"]) * 100, 1)
        }
