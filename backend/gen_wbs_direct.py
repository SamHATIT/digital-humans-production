import subprocess
import json
import os
import tempfile

# Prepare input data from DB
import sys
os.chdir('/app')
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.models.agent_deliverable import AgentDeliverable

db = SessionLocal()

gap = db.query(AgentDeliverable).filter(
    AgentDeliverable.execution_id == 119,
    AgentDeliverable.deliverable_type == "architect_gap_analysis"
).first()

design = db.query(AgentDeliverable).filter(
    AgentDeliverable.execution_id == 119,
    AgentDeliverable.deliverable_type == "architect_solution_design"
).first()

gap_content = json.loads(gap.content) if isinstance(gap.content, str) else gap.content
design_content = json.loads(design.content) if isinstance(design.content, str) else design.content

db.close()

# Create input file
input_data = {
    "gaps": gap_content.get("content", {}),
    "architecture": design_content.get("content", {}),
    "constraints": ""
}

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(input_data, f)
    input_file = f.name

output_file = '/tmp/wbs_output.json'

print(f"Input: {input_file}")
print(f"Output: {output_file}")
print("Running agent...")
sys.stdout.flush()

# Run agent directly
result = subprocess.run(
    [
        'python3', '/app/agents/roles/salesforce_solution_architect.py',
        '--input', input_file,
        '--output', output_file,
        '--execution-id', '119',
        '--project-id', '76',
        '--mode', 'wbs'
    ],
    capture_output=True,
    text=True,
    timeout=300
)

print(f"Return code: {result.returncode}")
print(f"STDOUT: {result.stdout[:2000] if result.stdout else 'None'}")
print(f"STDERR: {result.stderr[:2000] if result.stderr else 'None'}")
