"""
Notification service using PostgreSQL LISTEN/NOTIFY for real-time updates.
Replaces polling with event-driven architecture.
"""
import asyncio
import json
import logging
from typing import Dict, Optional, Callable, Any, Set
from contextlib import asynccontextmanager
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    PostgreSQL LISTEN/NOTIFY based notification service.
    
    Channels:
    - execution_{id}: Updates for a specific execution
    - build_{id}: Updates for a specific build phase
    - global: System-wide notifications
    """
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._listeners: Dict[str, Set[asyncio.Queue]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def initialize(self):
        """Initialize the connection pool and start listening."""
        if self._pool is not None:
            return
            
        try:
            # Parse DATABASE_URL for asyncpg
            db_url = settings.DATABASE_URL
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgres://", 1)
            
            self._pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=5,
                command_timeout=60
            )
            logger.info("NotificationService: Connection pool created")
        except Exception as e:
            logger.error(f"NotificationService: Failed to create pool: {e}")
            raise
    
    async def close(self):
        """Close the connection pool."""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("NotificationService: Connection pool closed")
    
    async def notify(self, channel: str, payload: Dict[str, Any]):
        """
        Send a notification to a channel.
        
        Args:
            channel: Channel name (e.g., "execution_123")
            payload: JSON-serializable data to send
        """
        if not self._pool:
            logger.warning("NotificationService: Pool not initialized, skipping notify")
            return
            
        try:
            async with self._pool.acquire() as conn:
                # PostgreSQL NOTIFY with JSON payload
                await conn.execute(
                    f"SELECT pg_notify($1, $2)",
                    channel,
                    json.dumps(payload)
                )
                logger.debug(f"NotificationService: Sent to {channel}: {payload.get('event', 'unknown')}")
        except Exception as e:
            logger.error(f"NotificationService: Failed to notify {channel}: {e}")
    
    @asynccontextmanager
    async def subscribe(self, channel: str):
        """
        Subscribe to a channel and yield received messages.
        
        Usage:
            async with notification_service.subscribe("execution_123") as queue:
                while True:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
        """
        if not self._pool:
            await self.initialize()
        
        queue: asyncio.Queue = asyncio.Queue()
        
        # Register listener
        if channel not in self._listeners:
            self._listeners[channel] = set()
        self._listeners[channel].add(queue)
        
        # Start listening on this channel
        conn = await self._pool.acquire()
        try:
            def callback(conn, pid, channel, payload):
                try:
                    data = json.loads(payload)
                    # Put message in all queues for this channel
                    for q in self._listeners.get(channel, []):
                        try:
                            q.put_nowait(data)
                        except asyncio.QueueFull:
                            pass
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in notification: {payload[:100]}")
            
            await conn.add_listener(channel, callback)
            logger.debug(f"NotificationService: Subscribed to {channel}")
            
            yield queue
            
        finally:
            await conn.remove_listener(channel, callback)
            await self._pool.release(conn)
            
            # Unregister listener
            if channel in self._listeners:
                self._listeners[channel].discard(queue)
                if not self._listeners[channel]:
                    del self._listeners[channel]
            
            logger.debug(f"NotificationService: Unsubscribed from {channel}")
    
    # Convenience methods for common notifications
    
    async def notify_execution_progress(
        self, 
        execution_id: int, 
        status: str, 
        progress: int,
        agent: Optional[str] = None,
        message: Optional[str] = None
    ):
        """Notify about execution progress update."""
        await self.notify(f"execution_{execution_id}", {
            "event": "progress",
            "execution_id": execution_id,
            "status": status,
            "progress": progress,
            "agent": agent,
            "message": message
        })
    
    async def notify_execution_completed(
        self, 
        execution_id: int,
        status: str,
        sds_document_path: Optional[str] = None
    ):
        """Notify that execution has completed."""
        await self.notify(f"execution_{execution_id}", {
            "event": "completed",
            "execution_id": execution_id,
            "status": status,
            "sds_document_path": sds_document_path
        })
    
    async def notify_build_task_update(
        self,
        execution_id: int,
        task_id: str,
        status: str,
        message: Optional[str] = None
    ):
        """Notify about build task status change."""
        await self.notify(f"build_{execution_id}", {
            "event": "task_update",
            "execution_id": execution_id,
            "task_id": task_id,
            "status": status,
            "message": message
        })


# Global singleton instance
_notification_service: Optional[NotificationService] = None


async def get_notification_service() -> NotificationService:
    """Get or create the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
        await _notification_service.initialize()
    return _notification_service


async def shutdown_notification_service():
    """Shutdown the global notification service."""
    global _notification_service
    if _notification_service:
        await _notification_service.close()
        _notification_service = None
