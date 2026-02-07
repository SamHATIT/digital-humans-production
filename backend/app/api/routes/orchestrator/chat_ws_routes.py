"""
Chat and WebSocket routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — Real-time communication endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio
import json
import logging

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.utils.dependencies import get_current_user
from app.config import settings
from app.api.routes.orchestrator._helpers import verify_execution_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/chat/{execution_id}")
async def chat_with_pm(
    execution_id: int,
    chat_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to Sophie (PM Orchestrator) for questions about the execution."""
    execution = verify_execution_access(execution_id, current_user.id, db)

    user_message = chat_data.get("message", "").strip()
    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required",
        )

    pm_response = (
        f"Hello! I'm Sophie, your PM Orchestrator. "
        f"Your execution (#{execution_id}) is currently in '{execution.status}' status. "
        f"How can I help you with your project?"
    )

    return {
        "execution_id": execution_id,
        "user_message": user_message,
        "pm_response": pm_response,
    }


@router.websocket("/ws/{execution_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    execution_id: int,
    token: str = Query(None),
):
    """WebSocket endpoint for real-time execution progress updates."""
    from jose import jwt, JWTError

    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()

    try:
        db = next(get_db())

        execution = (
            db.query(Execution)
            .join(Project)
            .filter(Execution.id == execution_id, Project.user_id == int(user_id))
            .first()
        )

        if not execution:
            await websocket.send_json({"type": "error", "data": {"error": "Execution not found"}})
            await websocket.close()
            return

        await websocket.send_json({
            "type": "connected",
            "data": {"execution_id": execution_id, "status": execution.status.value},
        })

        last_status = execution.status
        last_agent = execution.current_agent

        while True:
            try:
                db.refresh(execution)

                if execution.status != last_status or execution.current_agent != last_agent:
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "execution_id": execution_id,
                            "status": execution.status.value,
                            "progress": execution.progress or 0,
                            "current_agent": execution.current_agent,
                            "agent_execution_status": execution.agent_execution_status,
                            "message": f"Agent {execution.current_agent} is running..." if execution.current_agent else None,
                        },
                    })
                    last_status = execution.status
                    last_agent = execution.current_agent

                if execution.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                    await websocket.send_json({
                        "type": "completed" if execution.status == ExecutionStatus.COMPLETED else "error",
                        "data": {
                            "execution_id": execution_id,
                            "status": execution.status.value,
                            "progress": 100 if execution.status == ExecutionStatus.COMPLETED else execution.progress,
                            "sds_document_path": execution.sds_document_path,
                        },
                    })
                    break

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in WebSocket loop: {str(e)}")
                await websocket.send_json({"type": "error", "data": {"error": "Internal server error"}})
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"type": "error", "data": {"error": str(e)}})
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass
