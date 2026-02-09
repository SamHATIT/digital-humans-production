"""
SDS Synthesis Service - Génération de SDS de qualité professionnelle (v3)

Architecture:
1. PASS 1 (Done): Mistral local → Fiches Besoin JSON par UC
2. PASS 2: Agrégation Python → Groupement par domaine fonctionnel
3. PASS 3: Claude Sonnet → Sections SDS par domaine
4. PASS 4: Assembly → Document DOCX final

Inspiré des SDS LVMH (86p) et Shiseido (73p)
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.llm_router_service import (
    LLMRouterService, LLMRequest, LLMResponse, TaskComplexity, get_llm_router
)
from app.models.uc_requirement_sheet import UCRequirementSheet
from app.services.sds_section_writer import DIGITAL_HUMANS_AGENTS

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION DES DOMAINES FONCTIONNELS
# ============================================================================

DOMAIN_KEYWORDS = {
    "Customer Management": ["customer", "client", "account", "contact", "person", "user", "profil"],
    "Case Management": ["case", "ticket", "request", "claim", "réclamation", "demande", "support"],
    "Order Management": ["order", "commande", "purchase", "achat", "panier", "cart"],
    "Product Management": ["product", "article", "catalog", "inventory", "stock"],
    "Return & Refund": ["return", "retour", "refund", "remboursement", "exchange", "échange"],
    "Quality & Claims": ["quality", "qualité", "cosmetovigilance", "claim", "defect"],
    "Communication": ["email", "notification", "sms", "alert", "message", "template"],
    "Reporting & Analytics": ["report", "dashboard", "analytics", "kpi", "metric", "statistique"],
    "Integration": ["integration", "api", "sync", "import", "export", "talend", "middleware"],
    "Security & Access": ["security", "permission", "role", "profile", "access", "sharing"],
    "Workflow & Automation": ["workflow", "flow", "automation", "trigger", "process", "approval"],
}

# Template de section SDS (inspiré LVMH/Shiseido)
SDS_SECTION_PROMPT = """Tu es un consultant Salesforce senior rédigeant un SDS (Solution Design Specification) professionnel.

""" + DIGITAL_HUMANS_AGENTS + """

CONTEXTE PROJET:
{project_context}

DOMAINE FONCTIONNEL: {domain_name}
NOMBRE DE USE CASES: {uc_count}

FICHES BESOIN DU DOMAINE:
{fiches_json}

---

GÉNÈRE la section SDS pour ce domaine en suivant EXACTEMENT cette structure (format Markdown):

## {domain_name}

### Vue d'ensemble
[2-3 paragraphes décrivant le périmètre fonctionnel, les acteurs concernés, et les objectifs métier]

### Modèle de données

#### Objets Salesforce
[Table des objets avec colonnes: Objet | Type (Standard/Custom) | Description | Relation principale]

#### Champs clés
[Table avec colonnes: Objet | Champ | Type | Description | Obligatoire]

### Règles métier
[Liste numérotée BR_[DOMAIN]_001, BR_[DOMAIN]_002... avec format:]
- **BR_[DOMAIN]_XXX**: [Description de la règle]
  - Déclencheur: [Quand s'applique]
  - Action: [Ce qui se passe]
  - Message d'erreur (si applicable): [Texte]

### Automatisations
[Table avec colonnes: Type (Flow/Trigger/Apex) | Nom | Déclencheur | Action | Agent assigné]

### Processus métier
[Flowchart Mermaid du processus principal:]
```mermaid
flowchart TD
    A[Début] --> B{{Condition}}
    B -->|Oui| C[Action 1]
    B -->|Non| D[Action 2]
    C --> E[Fin]
    D --> E
```

### Interfaces utilisateur
[Si LWC/pages personnalisées, décrire les écrans avec leurs champs]

### Validation et tests
[Critères d'acceptation clés à tester]

---

RÈGLES DE RÉDACTION:
1. Sois CONCIS mais COMPLET - chaque information doit être actionnable
2. Utilise les VRAIS noms d'objets Salesforce mentionnés dans les fiches
3. Numérote les Business Rules avec le préfixe du domaine (ex: BR_CASE_001)
4. Le flowchart Mermaid doit représenter le processus RÉEL du domaine
5. Ne JAMAIS inventer d'informations non présentes dans les fiches
6. Si une information manque, indique "[À définir avec le client]"

Génère la section complète:"""


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class DomainGroup:
    """Groupe de fiches besoin par domaine fonctionnel"""
    name: str
    fiches: List[Dict[str, Any]] = field(default_factory=list)
    objects: set = field(default_factory=set)
    agents: set = field(default_factory=set)
    
    @property
    def uc_count(self) -> int:
        return len(self.fiches)
    
    def to_summary(self) -> Dict[str, Any]:
        return {
            "domain": self.name,
            "uc_count": self.uc_count,
            "objects": list(self.objects),
            "agents": list(self.agents),
            "complexity_distribution": self._get_complexity_dist()
        }
    
    def _get_complexity_dist(self) -> Dict[str, int]:
        dist = {"simple": 0, "moyenne": 0, "complexe": 0}
        for f in self.fiches:
            c = f.get("complexite", "moyenne").lower()
            if c in dist:
                dist[c] += 1
        return dist


@dataclass
class SDSSection:
    """Section générée du SDS"""
    domain: str
    content: str
    uc_count: int
    objects: List[str]
    tokens_used: int = 0
    cost_usd: float = 0.0
    generation_time_ms: int = 0


@dataclass
class SDSSynthesisResult:
    """Résultat complet de la synthèse SDS"""
    project_name: str
    sections: List[SDSSection]
    erd_mermaid: str
    permissions_matrix: str
    total_ucs: int
    total_tokens: int
    total_cost_usd: float
    generation_time_ms: int
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ============================================================================
# SERVICE PRINCIPAL
# ============================================================================

class SDSSynthesisService:
    """Service de synthèse SDS v3 - Génération par domaine"""
    
    def __init__(self):
        self.router = get_llm_router()
        self.stats = {
            "sections_generated": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_time_ms": 0
        }
    
    # ========================================================================
    # PASS 2: Agrégation par domaine
    # ========================================================================
    
    def aggregate_by_domain(self, fiches: List[Dict[str, Any]]) -> Dict[str, DomainGroup]:
        """
        Agrège les fiches besoin par domaine fonctionnel.
        Utilise les objets SF et mots-clés pour classifier.
        """
        domains: Dict[str, DomainGroup] = {}
        unclassified = DomainGroup(name="Other")
        
        for fiche in fiches:
            domain = self._classify_fiche(fiche)
            
            if domain not in domains:
                domains[domain] = DomainGroup(name=domain)
            
            group = domains[domain]
            group.fiches.append(fiche)
            
            # Collecter objets et agents
            for obj in fiche.get("objets_salesforce", []):
                group.objects.add(obj)
            
            agent = fiche.get("agent_suggere")
            if agent:
                group.agents.add(agent)
        
        # Trier par nombre de UCs (plus gros domaines en premier)
        sorted_domains = dict(sorted(
            domains.items(),
            key=lambda x: x[1].uc_count,
            reverse=True
        ))
        
        logger.info(f"Agrégation: {len(fiches)} fiches → {len(sorted_domains)} domaines")
        for name, group in sorted_domains.items():
            logger.info(f"  - {name}: {group.uc_count} UCs, objets: {list(group.objects)[:5]}")
        
        return sorted_domains
    
    def _classify_fiche(self, fiche: Dict[str, Any]) -> str:
        """Classifie une fiche dans un domaine fonctionnel"""
        # Construire le texte à analyser
        text_parts = [
            fiche.get("titre", ""),
            fiche.get("objectif", ""),
            " ".join(fiche.get("objets_salesforce", [])),
            " ".join(fiche.get("automatisations", []))
        ]
        text = " ".join(text_parts).lower()
        
        # Score par domaine
        scores = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > 0:
                scores[domain] = score
        
        # Retourner le domaine avec le plus haut score
        if scores:
            return max(scores, key=scores.get)
        
        return "Other"
    
    # ========================================================================
    # PASS 3: Génération sections SDS via Claude
    # ========================================================================
    
    async def generate_section(
        self,
        domain_group: DomainGroup,
        project_context: str = ""
    ) -> SDSSection:
        """Génère une section SDS pour un domaine via Claude"""
        import time
        start_time = time.time()
        
        # Préparer le JSON des fiches (limité pour le contexte)
        fiches_json = json.dumps(domain_group.fiches, ensure_ascii=False, indent=2)
        
        # Si trop long, résumer
        if len(fiches_json) > 30000:
            fiches_json = self._summarize_fiches(domain_group.fiches)
        
        prompt = SDS_SECTION_PROMPT.format(
            project_context=project_context or "Projet Salesforce Service Cloud",
            domain_name=domain_group.name,
            uc_count=domain_group.uc_count,
            fiches_json=fiches_json
        )
        
        # Appel Claude via le router (force Claude pour la qualité)
        request = LLMRequest(
            
            prompt=prompt,
            task_type=TaskComplexity.COMPLEX,  # Force Claude
            max_tokens=4000,
            temperature=0.3,  # Déterministe pour la cohérence
            force_provider="anthropic/claude-sonnet"
        )
        
        response = await self.router.complete(request)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        section = SDSSection(
            domain=domain_group.name,
            content=response.content,
            uc_count=domain_group.uc_count,
            objects=list(domain_group.objects),
            tokens_used=response.tokens_in + response.tokens_out,
            cost_usd=response.cost_usd,
            generation_time_ms=elapsed_ms
        )
        
        # Mise à jour stats
        self.stats["sections_generated"] += 1
        self.stats["total_tokens"] += response.tokens_in + response.tokens_out
        self.stats["total_cost_usd"] += response.cost_usd
        self.stats["total_time_ms"] += elapsed_ms
        
        logger.info(f"Section '{domain_group.name}' générée: {response.tokens_in + response.tokens_out} tokens, ${response.cost_usd:.4f}, {elapsed_ms}ms")
        
        return section
    
    def _summarize_fiches(self, fiches: List[Dict[str, Any]]) -> str:
        """Résume les fiches si trop volumineuses"""
        summary = []
        for f in fiches:
            summary.append({
                "uc_id": f.get("uc_id"),
                "titre": f.get("titre"),
                "objets": f.get("objets_salesforce", [])[:3],
                "agent": f.get("agent_suggere"),
                "complexite": f.get("complexite")
            })
        return json.dumps(summary, ensure_ascii=False, indent=2)
    
    # ========================================================================
    # PASS 4: Génération ERD et Matrice Permissions
    # ========================================================================
    
    def generate_erd_mermaid(self, all_fiches: List[Dict[str, Any]]) -> str:
        """Génère un ERD Mermaid à partir de tous les objets"""
        import re as regex
        
        def clean_name(name: str) -> str:
            """Nettoie un nom pour Mermaid (alphanumeric + underscore seulement)"""
            # Enlever __c, remplacer caractères spéciaux
            cleaned = name.replace("__c", "").replace("__", "_")
            # Garder seulement alphanumeric et underscore
            cleaned = regex.sub(r'[^a-zA-Z0-9_]', '_', cleaned)
            # Enlever underscores multiples
            cleaned = regex.sub(r'_+', '_', cleaned)
            # Enlever underscores au début/fin
            cleaned = cleaned.strip('_')
            return cleaned[:30] if cleaned else "Unknown"
        
        objects = defaultdict(lambda: {"fields": set(), "relations": set()})
        
        for fiche in all_fiches:
            for obj in fiche.get("objets_salesforce", []):
                obj_clean = clean_name(obj)
                if obj_clean:
                    for field in fiche.get("champs_cles", []):
                        field_clean = clean_name(field)
                        if field_clean:
                            objects[obj_clean]["fields"].add(field_clean)
        
        # Détecter relations (simpliste: si un objet référence un autre)
        obj_names = list(objects.keys())
        for obj in obj_names:
            for field in objects[obj]["fields"]:
                for other_obj in obj_names:
                    if other_obj.lower() in field.lower() and other_obj != obj:
                        objects[obj]["relations"].add(other_obj)
        
        # Générer Mermaid
        lines = ["erDiagram"]
        
        for obj, data in objects.items():
            # Ajouter l'entité avec quelques champs
            fields = list(data["fields"])[:5]  # Max 5 champs par objet
            if fields:
                lines.append(f"    {obj} {{")
                for f in fields:
                    lines.append(f"        string {f}")
                lines.append("    }")
            
            # Ajouter les relations
            for rel in data["relations"]:
                lines.append(f"    {obj} ||--o{{ {rel} : has")
        
        return "\n".join(lines)
    
    def generate_permissions_matrix(self, all_fiches: List[Dict[str, Any]]) -> str:
        """Génère une matrice de permissions Markdown"""
        # Collecter profils/agents et objets
        agents = set()
        objects = set()
        
        for fiche in all_fiches:
            agent = fiche.get("agent_suggere")
            if agent:
                agents.add(agent)
            for obj in fiche.get("objets_salesforce", []):
                objects.add(obj)
        
        # Générer table Markdown
        agents_list = sorted(agents)
        objects_list = sorted(objects)[:15]  # Max 15 objets
        
        header = "| Objet | " + " | ".join(agents_list) + " |"
        separator = "|" + "---|" * (len(agents_list) + 1)
        
        rows = [header, separator]
        for obj in objects_list:
            row = f"| {obj} |"
            for agent in agents_list:
                # Simplifié: R+C+M pour l'agent assigné, R pour les autres
                row += " R+C+M |" if agent == "raj" else " R |"
            rows.append(row)
        
        return "\n".join(rows)
    
    # ========================================================================
    # MÉTHODE PRINCIPALE: Synthèse complète
    # ========================================================================
    
    async def synthesize_sds(
        self,
        fiches: List[Dict[str, Any]],
        project_name: str = "Projet Salesforce",
        project_context: str = ""
    ) -> SDSSynthesisResult:
        """
        Pipeline complet de synthèse SDS v3.
        
        Args:
            fiches: Liste des fiches besoin (issues de UCAnalyzerService)
            project_name: Nom du projet
            project_context: Contexte additionnel (client, objectifs, contraintes)
        
        Returns:
            SDSSynthesisResult avec toutes les sections générées
        """
        import time
        start_time = time.time()
        
        logger.info(f"=== Début synthèse SDS v3 pour '{project_name}' ===")
        logger.info(f"Input: {len(fiches)} fiches besoin")
        
        # PASS 2: Agrégation par domaine
        domains = self.aggregate_by_domain(fiches)
        
        # PASS 3: Génération sections (en parallèle, max 3 concurrent)
        sections = []
        semaphore = asyncio.Semaphore(3)
        
        async def generate_with_limit(domain_group):
            async with semaphore:
                return await self.generate_section(domain_group, project_context)
        
        tasks = [generate_with_limit(group) for group in domains.values()]
        sections = await asyncio.gather(*tasks)
        
        # PASS 4: Générer ERD et Matrice
        erd = self.generate_erd_mermaid(fiches)
        permissions = self.generate_permissions_matrix(fiches)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        result = SDSSynthesisResult(
            project_name=project_name,
            sections=sections,
            erd_mermaid=erd,
            permissions_matrix=permissions,
            total_ucs=len(fiches),
            total_tokens=self.stats["total_tokens"],
            total_cost_usd=self.stats["total_cost_usd"],
            generation_time_ms=elapsed_ms
        )
        
        logger.info(f"=== Synthèse SDS terminée ===")
        logger.info(f"  Sections: {len(sections)}")
        logger.info(f"  Tokens: {self.stats['total_tokens']}")
        logger.info(f"  Coût: ${self.stats['total_cost_usd']:.4f}")
        logger.info(f"  Temps: {elapsed_ms}ms")
        
        return result
    
    # ========================================================================
    # MÉTHODE: Charger fiches depuis DB
    # ========================================================================
    
    async def load_fiches_from_db(
        self,
        db: AsyncSession,
        execution_id: int
    ) -> List[Dict[str, Any]]:
        """Charge les fiches besoin depuis la table uc_requirement_sheets"""
        query = select(UCRequirementSheet).where(
            UCRequirementSheet.execution_id == execution_id
        )
        result = await db.execute(query)
        sheets = result.scalars().all()
        
        fiches = []
        for sheet in sheets:
            if sheet.requirement_sheet:
                fiche = sheet.requirement_sheet
                fiche["uc_id"] = sheet.uc_id
                fiches.append(fiche)
        
        logger.info(f"Chargé {len(fiches)} fiches depuis DB pour execution {execution_id}")
        return fiches


# ============================================================================
# SINGLETON
# ============================================================================

_sds_synthesis_service: Optional[SDSSynthesisService] = None

def get_sds_synthesis_service() -> SDSSynthesisService:
    global _sds_synthesis_service
    if _sds_synthesis_service is None:
        _sds_synthesis_service = SDSSynthesisService()
    return _sds_synthesis_service
