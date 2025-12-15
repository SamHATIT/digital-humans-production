import asyncio
import json
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.models.agent_deliverable import AgentDeliverable
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

async def generate_wbs():
    db = SessionLocal()
    try:
        gap = db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == 119,
            AgentDeliverable.deliverable_type == "architect_gap_analysis"
        ).first()
        
        design = db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == 119,
            AgentDeliverable.deliverable_type == "architect_solution_design"
        ).first()
        
        if not gap or not design:
            print(f"Missing deliverables: gap={bool(gap)}, design={bool(design)}", flush=True)
            return
        
        gap_content = json.loads(gap.content) if isinstance(gap.content, str) else gap.content
        design_content = json.loads(design.content) if isinstance(design.content, str) else design.content
        
        print("Found gap analysis and solution design", flush=True)
        print("Generating WBS (this may take a few minutes)...", flush=True)
        
        service = PMOrchestratorServiceV2(db)
        
        wbs_result = await service._run_agent(
            agent_id="architect",
            mode="wbs",
            input_data={
                "gaps": gap_content.get("content", {}),
                "architecture": design_content.get("content", {}),
                "constraints": ""
            },
            execution_id=119,
            project_id=76
        )
        
        if wbs_result.get("success"):
            service._save_deliverable(119, "architect", "wbs", wbs_result["output"])
            tokens = wbs_result["output"].get("metadata", {}).get("tokens_used", 0)
            print(f"WBS generated successfully! Tokens: {tokens}", flush=True)
        else:
            print(f"WBS failed: {wbs_result.get('error')}", flush=True)
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(generate_wbs())
