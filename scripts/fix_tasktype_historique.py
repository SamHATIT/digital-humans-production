"""Repare le task_type des taches historiques de l'execution 165, via la fonction
d'inference du depot. Le correctif FIX-TASKTYPE-001 ne couvre que les insertions
futures ; sans cela l'execution 165 retomberait sur le meme crash a la relance."""
import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models.wbs_task_type import infer_task_type
from sqlalchemy import text

EXEC_ID = 165
db = SessionLocal()
try:
    lignes = db.execute(text(
        "SELECT id, task_name, phase_name, assigned_agent "
        "FROM task_executions WHERE execution_id=:e AND task_type IS NULL"), {"e": EXEC_ID}).fetchall()
    print(f"{len(lignes)} taches sans task_type")
    from collections import Counter
    c = Counter()
    for r in lignes:
        nom = r.task_name or ""
        desc = ""
        ctx = f"{nom} {r.phase_name or ''} {r.assigned_agent or ''}"
        tt = infer_task_type(ctx, desc).value
        c[tt] += 1
        db.execute(text("UPDATE task_executions SET task_type=:t WHERE id=:i"), {"t": tt, "i": r.id})
    db.commit()
    print("repartition inferee :")
    for k, v in c.most_common():
        print(f"  {k:<22} {v}")
finally:
    db.close()
