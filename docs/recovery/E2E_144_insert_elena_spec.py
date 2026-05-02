"""
Insère Elena spec dans agent_deliverables depuis llm_interactions id 1290.
Marque elena = completed dans agent_execution_status.
"""
import sys, json
sys.path.insert(0, "/root/workspace/digital-humans-production/backend")

from app.database import SessionLocal
from app.models.agent_deliverable import AgentDeliverable
from app.models.execution import Execution
from sqlalchemy import text
from datetime import datetime, timezone

db = SessionLocal()

# 1. Récupérer la response Elena
result = db.execute(text("""
    SELECT response, tokens_input, tokens_output, execution_time_seconds, model
    FROM llm_interactions WHERE id = 1290
""")).fetchone()

if not result:
    print("ERREUR: llm_interaction 1290 introuvable")
    sys.exit(1)

response_text, tok_in, tok_out, exec_time, model = result
print(f"Elena response: {len(response_text):,} chars, {tok_out:,} tokens output, model={model}")

# 2. Construire le wrapper deliverable (format identique à Aisha/Lucas/Jordan)
deliverable_content = {
    "success": True,
    "agent_id": "elena",
    "agent_name": "Elena (QA Tester)",
    "mode": "spec",
    "execution_id": "148",
    "deliverable_type": "qa_specifications",
    "content": {
        "raw_markdown": response_text
    },
    "metadata": {
        "tokens_used": tok_out,
        "tokens_input": tok_in,
        "execution_time_seconds": exec_time,
        "model_used": model,
        "manually_recovered": True,
        "recovered_from_llm_interaction_id": 1290,
        "recovery_reason": "Elena failed with 'Skipped: Timeout (10 min)' but LLM call succeeded post-timeout. Spec recovered to allow Phase 5 SDS generation.",
        "recovered_at": datetime.now(timezone.utc).isoformat()
    }
}

content_json = json.dumps(deliverable_content, ensure_ascii=False)
print(f"Wrapper deliverable: {len(content_json):,} chars")

# 3. INSERT dans agent_deliverables
db.execute(text("""
    INSERT INTO agent_deliverables 
    (execution_id, deliverable_type, content, content_metadata, created_at, updated_at)
    VALUES (:exec_id, :type, :content, :metadata, :now, :now)
"""), {
    "exec_id": 148,
    "type": "qa_qa_specifications",  # même pattern que data_data_specifications, etc.
    "content": content_json,
    "metadata": json.dumps({"manually_recovered": True, "from_llm_interaction": 1290}),
    "now": datetime.now(timezone.utc)
})
db.commit()

# 4. Vérifier
new_id = db.execute(text("""
    SELECT id, deliverable_type, length(content) AS chars
    FROM agent_deliverables 
    WHERE execution_id = 148 AND deliverable_type = 'qa_qa_specifications'
""")).fetchone()
print(f"INSERTED: id={new_id[0]}, type={new_id[1]}, chars={new_id[2]:,}")

# 5. Mettre à jour agent_execution_status pour Elena (qa) = completed
exe = db.query(Execution).filter_by(id=148).first()
status = exe.agent_execution_status or {}
if "qa" in status:
    status["qa"]["state"] = "completed"
    status["qa"]["progress"] = 88
    status["qa"]["message"] = "Elena (QA) done [recovered manually post-timeout]"
    status["qa"]["completed_at"] = datetime.now(timezone.utc).isoformat()
    status["qa"]["tokens_used"] = tok_out
    
    # SQLAlchemy ORM ne détecte pas les changements dans JSONB par défaut, force update
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(exe, "agent_execution_status")
    db.commit()
    print(f"Elena (qa) status: failed -> completed (tokens={tok_out:,})")
else:
    print(f"WARNING: 'qa' key not in agent_execution_status. Keys: {list(status.keys())}")

db.close()
print("DONE")
