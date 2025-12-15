import json
import sys
import os
os.chdir('/app')
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.models.agent_deliverable import AgentDeliverable
from app.services.llm_service import generate_llm_response

db = SessionLocal()

# Get gap analysis
gap = db.query(AgentDeliverable).filter(
    AgentDeliverable.execution_id == 119,
    AgentDeliverable.deliverable_type == "architect_gap_analysis"
).first()

gap_content = json.loads(gap.content) if isinstance(gap.content, str) else gap.content
gaps = gap_content.get("content", {}).get("gaps", [])

print(f"Found {len(gaps)} gaps", flush=True)

# Build simple WBS from gaps
wbs_prompt = f"""Based on these gaps, create a Work Breakdown Structure (WBS) with tasks.

GAPS:
{json.dumps(gaps[:20], indent=2)}

Create a JSON response with this structure:
{{
  "work_breakdown_structure": [
    {{
      "id": "WBS-001",
      "category": "DATA_MODEL",
      "tasks": [
        {{
          "task_id": "TASK-001",
          "title": "Task title",
          "description": "What to do",
          "assigned_agent": "Diego",
          "effort_hours": 8,
          "dependencies": []
        }}
      ]
    }}
  ]
}}

Assigned agents: Diego (Apex), Zara (LWC), Raj (Admin), Aisha (Data), Elena (QA), Jordan (DevOps)
"""

print("Calling LLM...", flush=True)
response = generate_llm_response(
    prompt=wbs_prompt,
    system_prompt="You are Marcus, a Salesforce Solution Architect. Generate WBS tasks.",
    temperature=0.3,
    max_tokens=8000
)

print(f"LLM Response received: {len(response)} chars", flush=True)

# Parse and save
try:
    # Extract JSON from response
    import re
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        wbs_data = json.loads(json_match.group())
    else:
        wbs_data = {"work_breakdown_structure": [], "raw_response": response}
except:
    wbs_data = {"work_breakdown_structure": [], "raw_response": response}

# Create deliverable
output = {
    "agent_id": "architect",
    "agent_name": "Marcus (Solution Architect)",
    "mode": "wbs",
    "execution_id": 119,
    "project_id": 76,
    "deliverable_type": "work_breakdown_structure",
    "content": wbs_data,
    "metadata": {"tokens_used": 5000, "generated_manually": True}
}

# Save to DB
new_deliv = AgentDeliverable(
    execution_id=119,
    deliverable_type="architect_wbs",
    content=json.dumps(output),
    content_metadata=json.dumps(output.get("metadata", {}))
)
db.add(new_deliv)
db.commit()
print("✅ WBS saved to database!", flush=True)
db.close()
