"""
Re-run Phase 5 (Emma write_sds) après fix template + Elena spec recovery.
1. Appeler build_sds(148) directement
2. Si OK : insérer le deliverable Emma + marquer execution COMPLETED
"""
import sys, json, time
sys.path.insert(0, "/root/workspace/digital-humans-production/backend")
sys.path.insert(0, "/root/workspace/digital-humans-production/tools")

from datetime import datetime, timezone

# Désactiver SQLAlchemy logs (trop verbeux)
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.database import SessionLocal
from app.models.execution import Execution
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

print("=" * 60)
print("RETRY PHASE 5 — Execution 148 (Essais Cliniques E2E #144)")
print("=" * 60)

# 1. Appeler build_sds(148)
try:
    from build_sds import build_sds
    print("\n[1/3] Calling build_sds(148)...")
    start = time.time()
    sds_html = build_sds(148)
    elapsed = time.time() - start
    print(f"      OK! {len(sds_html):,} chars in {elapsed:.2f}s")
except Exception as e:
    print(f"      FAILED: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# 2. Insérer le deliverable Emma write_sds
db = SessionLocal()

deliverable_content = {
    "success": True,
    "agent_id": "research_analyst",
    "agent_name": "Emma (Research Analyst)",
    "mode": "write_sds",
    "execution_id": 148,
    "project_id": 100,
    "deliverable_type": "sds_document",
    "artifact_id": "SDS-001",
    "content": {
        "raw_markdown": sds_html,
        "raw_html": sds_html,
        "word_count": len(sds_html.split()),
        "sections_count": 12,
    },
    "metadata": {
        "tokens_used": 0,
        "execution_time_seconds": elapsed,
        "model_used": "build_sds (no LLM, DB-driven)",
        "manually_recovered": True,
        "recovery_reason": "Initial Phase 5 failed at 13:12:49 due to template bug 'list object has no attribute items' in cicd_deployment.html.j2:135. Template was patched to handle both dict and list for monitoring.alerting. Elena spec was also recovered manually from llm_interaction 1290 (deliverable 704).",
        "recovered_at": datetime.now(timezone.utc).isoformat(),
    }
}

content_json = json.dumps(deliverable_content, ensure_ascii=False)

print(f"\n[2/3] Inserting Emma SDS deliverable ({len(content_json):,} chars)...")
db.execute(text("""
    INSERT INTO agent_deliverables 
    (execution_id, deliverable_type, content, content_metadata, created_at, updated_at)
    VALUES (:exec_id, :type, :content, :metadata, :now, :now)
"""), {
    "exec_id": 148,
    "type": "research_analyst_sds_document",
    "content": content_json,
    "metadata": json.dumps({
        "manually_recovered": True,
        "sds_html_chars": len(sds_html),
        "word_count": len(sds_html.split()),
    }),
    "now": datetime.now(timezone.utc)
})
db.commit()

new_id = db.execute(text("""
    SELECT id FROM agent_deliverables 
    WHERE execution_id = 148 AND deliverable_type = 'research_analyst_sds_document'
""")).scalar()
print(f"      INSERTED deliverable id={new_id}")

# 3. Marquer execution COMPLETED + Emma status
exe = db.query(Execution).filter_by(id=148).first()

status = exe.agent_execution_status or {}
if "research_analyst" in status:
    status["research_analyst"]["state"] = "completed"
    status["research_analyst"]["progress"] = 100
    status["research_analyst"]["message"] = f"SDS Document generated ({len(sds_html):,} chars HTML) [recovered manually]"
    status["research_analyst"]["completed_at"] = datetime.now(timezone.utc).isoformat()
    flag_modified(exe, "agent_execution_status")

exe.status = "COMPLETED"
exe.execution_state = "sds_complete"
exe.progress = 100
exe.completed_at = datetime.now(timezone.utc)
exe.last_completed_phase = "phase5_consolidation"

print(f"\n[3/3] Marking execution 148 as COMPLETED...")
db.commit()
db.close()

# 4. Sauver aussi le HTML sur disk pour debug/preview
out_path = f"/tmp/sds_148_recovered.html"
with open(out_path, "w") as f:
    f.write(sds_html)
print(f"      HTML saved to {out_path}")
print(f"      View with: cat {out_path} | head -50")

print("\n" + "=" * 60)
print("DONE — execution 148 marked COMPLETED")
print("=" * 60)
