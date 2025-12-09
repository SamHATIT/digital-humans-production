"""
LLM Logger Service - Logs all LLM interactions to database
"""
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime

# Database imports
try:
    from app.database import SessionLocal
    from app.models.llm_interaction import LLMInteraction
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


def log_llm_interaction(
    agent_id: str,
    prompt: str,
    response: Optional[str] = None,
    execution_id: Optional[int] = None,
    task_id: Optional[str] = None,
    agent_mode: Optional[str] = None,
    rag_context: Optional[str] = None,
    previous_feedback: Optional[str] = None,
    parsed_files: Optional[Dict] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    execution_time_seconds: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None
) -> Optional[int]:
    """
    Log an LLM interaction to the database.
    
    Returns:
        The ID of the created record, or None if logging failed.
    """
    if not DB_AVAILABLE:
        print(f"⚠️ [LLM Logger] Database not available, skipping log")
        return None
    
    try:
        db = SessionLocal()
        
        interaction = LLMInteraction(
            execution_id=int(execution_id) if execution_id else None,
            task_id=task_id,
            agent_id=agent_id,
            agent_mode=agent_mode,
            prompt=prompt[:100000] if prompt else None,  # Limit size
            rag_context=rag_context[:50000] if rag_context else None,
            previous_feedback=previous_feedback[:10000] if previous_feedback else None,
            response=response[:500000] if response else None,  # LLM responses can be large
            parsed_files=parsed_files,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            model=model,
            provider=provider,
            execution_time_seconds=execution_time_seconds,
            success=success,
            error_message=error_message[:5000] if error_message else None
        )
        
        db.add(interaction)
        db.commit()
        interaction_id = interaction.id
        db.close()
        
        print(f"📝 [LLM Logger] Logged interaction #{interaction_id} for {agent_id}", flush=True)
        return interaction_id
        
    except Exception as e:
        print(f"❌ [LLM Logger] Failed to log: {e}", flush=True)
        try:
            db.close()
        except:
            pass
        return None


class LLMInteractionContext:
    """
    Context manager for tracking LLM interactions.
    Automatically logs timing and handles errors.
    """
    
    def __init__(
        self,
        agent_id: str,
        prompt: str,
        execution_id: Optional[int] = None,
        task_id: Optional[str] = None,
        agent_mode: Optional[str] = None,
        rag_context: Optional[str] = None,
        previous_feedback: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.agent_id = agent_id
        self.prompt = prompt
        self.execution_id = execution_id
        self.task_id = task_id
        self.agent_mode = agent_mode
        self.rag_context = rag_context
        self.previous_feedback = previous_feedback
        self.model = model
        self.provider = provider
        self.start_time = None
        self.response = None
        self.parsed_files = None
        self.tokens_input = None
        self.tokens_output = None
        self.success = True
        self.error_message = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def set_response(self, response: str, tokens_input: int = None, tokens_output: int = None):
        """Set the LLM response and token counts."""
        self.response = response
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
    
    def set_parsed_files(self, files: Dict):
        """Set the files parsed from the response."""
        self.parsed_files = files
    
    def set_error(self, error: str):
        """Mark the interaction as failed."""
        self.success = False
        self.error_message = error
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time if self.start_time else None
        
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)
        
        log_llm_interaction(
            agent_id=self.agent_id,
            prompt=self.prompt,
            response=self.response,
            execution_id=self.execution_id,
            task_id=self.task_id,
            agent_mode=self.agent_mode,
            rag_context=self.rag_context,
            previous_feedback=self.previous_feedback,
            parsed_files=self.parsed_files,
            tokens_input=self.tokens_input,
            tokens_output=self.tokens_output,
            model=self.model,
            provider=self.provider,
            execution_time_seconds=execution_time,
            success=self.success,
            error_message=self.error_message
        )
        
        return False  # Don't suppress exceptions
