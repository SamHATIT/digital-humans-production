"""
Blog API Routes - Generate articles from approved topics
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import os
import asyncio
from datetime import datetime

router = APIRouter(prefix="/blog", tags=["blog"])

# Database connection
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://digital_humans:DH_SecurePass2025!@localhost:5432/digital_humans_db")

class TopicRequest(BaseModel):
    id: int
    title: str
    agent: str

class BatchGenerateRequest(BaseModel):
    topics: List[TopicRequest]

class GenerationResult(BaseModel):
    id: int
    title: str
    success: bool
    ghost_post_id: Optional[str] = None
    error: Optional[str] = None

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def generate_single_article(topic: TopicRequest) -> GenerationResult:
    """Generate a single article using blog_generator.py"""
    script_path = "/root/workspace/digital-humans-production/scripts/blog_generator.py"
    
    try:
        # Run the generator script
        process = await asyncio.create_subprocess_exec(
            "python3", script_path,
            topic.title,
            "--agent", topic.agent,
            cwd="/root/workspace/digital-humans-production/scripts",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ}
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300  # 5 minutes max per article
        )
        
        output = stdout.decode()
        
        # Check if successful (look for ghost post URL in output)
        if "✅" in output and "ghost/#/editor/post/" in output:
            # Extract post ID from output
            import re
            match = re.search(r'ghost/#/editor/post/([a-f0-9]+)', output)
            post_id = match.group(1) if match else None
            
            return GenerationResult(
                id=topic.id,
                title=topic.title,
                success=True,
                ghost_post_id=post_id
            )
        else:
            return GenerationResult(
                id=topic.id,
                title=topic.title,
                success=False,
                error=stderr.decode()[:500] if stderr else "Unknown error"
            )
            
    except asyncio.TimeoutError:
        return GenerationResult(
            id=topic.id,
            title=topic.title,
            success=False,
            error="Timeout after 5 minutes"
        )
    except Exception as e:
        return GenerationResult(
            id=topic.id,
            title=topic.title,
            success=False,
            error=str(e)
        )

async def update_topic_status(topic_id: int, ghost_post_id: Optional[str], success: bool):
    """Update topic status in database after generation"""
    conn = await get_db_connection()
    try:
        if success:
            await conn.execute(
                """UPDATE blog_topics 
                   SET status = 'generated', ghost_post_id = $1, generated_at = NOW() 
                   WHERE id = $2""",
                ghost_post_id, topic_id
            )
        else:
            await conn.execute(
                """UPDATE blog_topics 
                   SET notes = COALESCE(notes, '') || ' | Generation failed at ' || NOW()::text
                   WHERE id = $1""",
                topic_id
            )
    finally:
        await conn.close()

@router.post("/generate-batch")
async def generate_batch(request: BatchGenerateRequest, background_tasks: BackgroundTasks):
    """Generate articles for approved topics"""
    
    if not request.topics:
        raise HTTPException(status_code=400, detail="No topics provided")
    
    results = []
    
    for topic in request.topics:
        # Generate article
        result = await generate_single_article(topic)
        results.append(result)
        
        # Update database
        await update_topic_status(topic.id, result.ghost_post_id, result.success)
    
    success_count = sum(1 for r in results if r.success)
    
    return {
        "success": True,
        "message": f"{success_count}/{len(results)} articles générés",
        "results": [r.dict() for r in results]
    }

@router.get("/pending-topics")
async def get_pending_topics():
    """Get topics awaiting validation"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT * FROM blog_topics 
               WHERE status = 'pending' 
               ORDER BY created_at DESC"""
        )
        return {"topics": [dict(r) for r in rows]}
    finally:
        await conn.close()

@router.get("/approved-topics")
async def get_approved_topics():
    """Get approved topics ready for generation"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT id, title, COALESCE(approved_agent, suggested_agent) as agent 
               FROM blog_topics 
               WHERE status = 'approved' 
               ORDER BY approved_at"""
        )
        return {"topics": [dict(r) for r in rows]}
    finally:
        await conn.close()
