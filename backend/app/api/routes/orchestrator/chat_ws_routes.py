"""
Chat and WebSocket routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — Real-time communication endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio
import logging

from app.database import get_db, SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.utils.dependencies import get_current_user
from app.config import settings
from app.api.routes.orchestrator._helpers import verify_execution_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])

# kim:PROD-02 — interval between two reads of the execution row.
WS_POLL_INTERVAL_SECONDS = 5


def _load_execution_snapshot(execution_id: int, user_id: int):
    """Read one execution in a short-lived session, return a plain dict.

    kim:PROD-02: the session is opened, read and closed inside this call so
    that no DB connection is held across an ``await``. Previously the handler
    kept one session open for the whole socket lifetime (``next(get_db())``,
    never closed), so N monitoring tabs pinned N PostgreSQL connections.

    Returns None when the execution does not exist or does not belong to
    ``user_id``.
    """
    db = SessionLocal()
    try:
        execution = (
            db.query(Execution)
            .join(Project)
            .filter(Execution.id == execution_id, Project.user_id == user_id)
            .first()
        )
        if not execution:
            return None
        status = execution.status
        return {
            "status": status,
            "status_value": status.value if hasattr(status, "value") else str(status),
            "progress": execution.progress or 0,
            "current_agent": execution.current_agent,
            "agent_execution_status": execution.agent_execution_status,
            "sds_document_path": execution.sds_document_path,
        }
    finally:
        db.close()


async def _wait_or_disconnect(websocket: WebSocket, timeout: float) -> bool:
    """Wait ``timeout`` seconds, returning True as soon as the client leaves.

    A blind ``asyncio.sleep`` never reads the socket, so a closed browser tab
    went unnoticed and the server task polled forever. Reading with a timeout
    turns a disconnect into an immediate, clean exit.
    """
    try:
        message = await asyncio.wait_for(websocket.receive(), timeout=timeout)
    except asyncio.TimeoutError:
        return False
    except (WebSocketDisconnect, RuntimeError):
        return True
    return message.get("type") == "websocket.disconnect"


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

    user_id_int = int(user_id)

    try:
        # kim:PROD-02 — every DB read goes through a short-lived session run in
        # a worker thread: no connection is held across an await, and the sync
        # SQLAlchemy call no longer blocks the event loop for every client.
        snapshot = await asyncio.to_thread(
            _load_execution_snapshot, execution_id, user_id_int
        )

        if snapshot is None:
            await websocket.send_json({"type": "error", "data": {"error": "Execution not found"}})
            await websocket.close()
            return

        await websocket.send_json({
            "type": "connected",
            "data": {"execution_id": execution_id, "status": snapshot["status_value"]},
        })

        last_status = snapshot["status"]
        last_agent = snapshot["current_agent"]

        while True:
            try:
                if snapshot is None:
                    await websocket.send_json(
                        {"type": "error", "data": {"error": "Execution not found"}}
                    )
                    break

                if snapshot["status"] != last_status or snapshot["current_agent"] != last_agent:
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "execution_id": execution_id,
                            "status": snapshot["status_value"],
                            "progress": snapshot["progress"],
                            "current_agent": snapshot["current_agent"],
                            "agent_execution_status": snapshot["agent_execution_status"],
                            "message": f"Agent {snapshot['current_agent']} is running..." if snapshot["current_agent"] else None,
                        },
                    })
                    last_status = snapshot["status"]
                    last_agent = snapshot["current_agent"]

                if snapshot["status"] in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                    await websocket.send_json({
                        "type": "completed" if snapshot["status"] == ExecutionStatus.COMPLETED else "error",
                        "data": {
                            "execution_id": execution_id,
                            "status": snapshot["status_value"],
                            "progress": 100 if snapshot["status"] == ExecutionStatus.COMPLETED else snapshot["progress"],
                            "sds_document_path": snapshot["sds_document_path"],
                        },
                    })
                    break

                if await _wait_or_disconnect(websocket, WS_POLL_INTERVAL_SECONDS):
                    logger.info(f"WebSocket client left execution {execution_id}")
                    break

                snapshot = await asyncio.to_thread(
                    _load_execution_snapshot, execution_id, user_id_int
                )

            except WebSocketDisconnect:
                raise
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
