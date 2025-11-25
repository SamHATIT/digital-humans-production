from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any

from app.database import get_db
from app.models import User, Project, Execution, AgentDeliverable, QualityGate, ExecutionStatus, GateStatus
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def count_lines_of_code(content: str) -> int:
    if not content:
        return 0
    lines = content.split('\n')
    code_lines = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('//', '#', '/*', '*', '*/', '<!--', '-->')):
            continue
        code_lines += 1
    return code_lines

@router.get("")
async def get_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    completed_projects = db.query(Project).join(Execution).filter(
        Execution.status == ExecutionStatus.COMPLETED,
        Project.user_id == current_user.id
    ).distinct().count()
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_completed = db.query(Project).join(Execution).filter(
        Execution.status == ExecutionStatus.COMPLETED,
        Execution.completed_at >= week_ago,
        Project.user_id == current_user.id
    ).distinct().count()
    
    deliverables = db.query(AgentDeliverable.content).join(Execution).join(Project).filter(
        Project.user_id == current_user.id
    ).all()
    total_lines = sum(count_lines_of_code(d.content) for d in deliverables)
    
    completed_executions = db.query(Execution).join(Project).filter(
        Execution.status == ExecutionStatus.COMPLETED,
        Execution.duration_seconds.isnot(None),
        Project.user_id == current_user.id
    ).all()
    
    ai_time_hours = sum(e.duration_seconds for e in completed_executions) / 3600
    manual_time_estimate = ai_time_hours * 20
    time_saved_hours = manual_time_estimate - ai_time_hours
    
    bugs_caught = db.query(QualityGate).join(Execution).join(Project).filter(
        QualityGate.status == GateStatus.FAILED,
        Project.user_id == current_user.id
    ).count()
    
    recent_projects = db.query(Project).join(Execution).filter(
        Project.user_id == current_user.id
    ).order_by(Project.updated_at.desc()).limit(10).all()
    
    projects_list = []
    for project in recent_projects:
        latest_execution = db.query(Execution).filter(
            Execution.project_id == project.id
        ).order_by(Execution.created_at.desc()).first()
        
        if latest_execution:
            status_map = {
                ExecutionStatus.COMPLETED: "Completed",
                ExecutionStatus.FAILED: "Failed",
                ExecutionStatus.IN_PROGRESS: "In Progress",
                ExecutionStatus.PENDING: "Pending"
            }
            
            projects_list.append({
                "id": f"PROJ-{project.id:03d}",
                "name": project.name,
                "date": latest_execution.created_at.strftime("%Y-%m-%d"),
                "status": status_map.get(latest_execution.status, "Unknown"),
                "impact": "High" if completed_projects > 5 else "Medium"
            })
    
    velocity_data = []
    for week_offset in range(6, -1, -1):
        week_start = datetime.utcnow() - timedelta(weeks=week_offset+1)
        week_end = datetime.utcnow() - timedelta(weeks=week_offset)
        
        week_projects = db.query(Execution).join(Project).filter(
            Execution.status == ExecutionStatus.COMPLETED,
            Execution.completed_at >= week_start,
            Execution.completed_at < week_end,
            Project.user_id == current_user.id
        ).count()
        
        velocity_data.append(week_projects)
    
    return {
        "stats": {
            "total_projects": completed_projects,
            "projects_change": f"+{recent_completed} this week" if recent_completed > 0 else "No change",
            "lines_of_code": total_lines,
            "time_saved_hours": round(time_saved_hours, 1),
            "bugs_caught": bugs_caught
        },
        "projects": projects_list,
        "velocity": velocity_data
    }
