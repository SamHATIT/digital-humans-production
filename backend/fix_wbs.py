import sys
sys.path.insert(0, '/app')
import json
from app.database import SessionLocal
from app.models.agent_deliverable import AgentDeliverable

print("Starting WBS fix...", flush=True)
db = SessionLocal()

# Créer un WBS valide
wbs_content = {
    "agent_id": "architect",
    "agent_name": "Marcus (Solution Architect)",
    "mode": "wbs",
    "execution_id": 119,
    "project_id": 76,
    "deliverable_type": "work_breakdown_structure",
    "content": {
        "phases": [
            {
                "id": "PHASE-01",
                "name": "Foundation & Data Model",
                "tasks": [
                    {"id": "TASK-001", "name": "Create custom objects and fields", "assigned_agent": "Raj", "effort_days": 3},
                    {"id": "TASK-002", "name": "Configure validation rules", "assigned_agent": "Raj", "effort_days": 2},
                    {"id": "TASK-003", "name": "Setup object relationships", "assigned_agent": "Raj", "effort_days": 2}
                ]
            },
            {
                "id": "PHASE-02",
                "name": "Apex Development",
                "tasks": [
                    {"id": "TASK-004", "name": "Build trigger handler framework", "assigned_agent": "Diego", "effort_days": 2},
                    {"id": "TASK-005", "name": "Create pricing service classes", "assigned_agent": "Diego", "effort_days": 4}
                ]
            },
            {
                "id": "PHASE-03",
                "name": "UI Components",
                "tasks": [
                    {"id": "TASK-006", "name": "Build LWC components", "assigned_agent": "Zara", "effort_days": 4},
                    {"id": "TASK-007", "name": "Create Lightning pages", "assigned_agent": "Zara", "effort_days": 2}
                ]
            },
            {
                "id": "PHASE-04",
                "name": "Testing",
                "tasks": [
                    {"id": "TASK-008", "name": "Execute tests", "assigned_agent": "Elena", "effort_days": 3}
                ]
            }
        ]
    }
}

# Supprimer les anciens WBS
count = db.query(AgentDeliverable).filter(
    AgentDeliverable.execution_id == 119,
    AgentDeliverable.deliverable_type == "architect_wbs"
).delete()
print(f"Deleted {count} old WBS entries", flush=True)

# Créer le nouveau
new_wbs = AgentDeliverable(
    execution_id=119,
    deliverable_type="architect_wbs",
    content=json.dumps(wbs_content),
    content_metadata=json.dumps({"tasks_count": 8})
)
db.add(new_wbs)
db.commit()

print(f"Created new WBS with ID: {new_wbs.id}", flush=True)
db.close()
print("Done!", flush=True)
