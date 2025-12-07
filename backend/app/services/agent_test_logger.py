"""
Agent Test Logger - Persistent logging for debugging agent behavior

Logs all data at each step:
- RAG query sent
- RAG context received
- Prompt constructed
- LLM response received

Files are stored in /logs/agent_tests/ as JSON for post-execution analysis.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

# Log directory
LOGS_DIR = Path(__file__).parent.parent.parent / "logs" / "agent_tests"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LogStep:
    """A single step in the agent execution"""
    step_number: int
    name: str
    timestamp: str
    data: Dict[str, Any]
    
    def to_dict(self):
        return asdict(self)


@dataclass
class AgentTestLog:
    """Complete log of an agent test execution"""
    test_id: str
    agent_id: str
    agent_name: str
    task_description: str
    started_at: str
    use_rag: bool = True
    steps: List[LogStep] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    completed_at: Optional[str] = None
    
    def add_step(self, name: str, data: Dict[str, Any]) -> LogStep:
        """Add a step to the log"""
        step = LogStep(
            step_number=len(self.steps) + 1,
            name=name,
            timestamp=datetime.now().isoformat(),
            data=data
        )
        self.steps.append(step)
        self._save()
        return step
    
    def complete(self, status: str, output: Any = None, error: str = None):
        """Mark the test as complete"""
        self.completed_at = datetime.now().isoformat()
        self.result = {
            "status": status,
            "output_length": len(str(output)) if output else 0,
            "output_preview": str(output)[:500] if output else None,
            "error_message": error
        }
        self._save()
    
    def _save(self):
        """Save log to JSON file"""
        filename = f"{self.started_at[:19].replace(':', '-')}_{self.agent_id}_{self.test_id[:8]}.json"
        filepath = LOGS_DIR / filename
        
        data = {
            "test_id": self.test_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "use_rag": self.use_rag,
            "steps": [s.to_dict() for s in self.steps],
            "result": self.result
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def to_dict(self):
        return {
            "test_id": self.test_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "use_rag": self.use_rag,
            "steps": [s.to_dict() for s in self.steps],
            "result": self.result
        }


class AgentTestLogger:
    """Manager for agent test logging"""
    
    _current_log: Optional[AgentTestLog] = None
    
    @classmethod
    def start_test(cls, agent_id: str, agent_name: str, task: str, use_rag: bool = True) -> AgentTestLog:
        """Start a new test log"""
        log = AgentTestLog(
            test_id=str(uuid.uuid4()),
            agent_id=agent_id,
            agent_name=agent_name,
            task_description=task,
            started_at=datetime.now().isoformat(),
            use_rag=use_rag
        )
        cls._current_log = log
        log._save()
        return log
    
    @classmethod
    def get_current(cls) -> Optional[AgentTestLog]:
        """Get current test log"""
        return cls._current_log
    
    @classmethod
    def log_rag_query(cls, query: str, categories: List[str] = None, metadata: Dict = None):
        """Log RAG query being sent"""
        if cls._current_log:
            cls._current_log.add_step("rag_query", {
                "query": query,
                "query_length": len(query),
                "categories": categories,
                "metadata": metadata
            })
    
    @classmethod
    def log_rag_response(cls, chunks: List[Dict], total_context_length: int = 0):
        """Log RAG response received"""
        if cls._current_log:
            # Limit chunk content for readability but keep full data
            chunks_summary = []
            for i, chunk in enumerate(chunks[:10]):  # Log first 10 chunks
                chunks_summary.append({
                    "index": i,
                    "source": chunk.get("source", "unknown"),
                    "score": chunk.get("score", 0),
                    "content_length": len(chunk.get("content", "")),
                    "content_preview": chunk.get("content", "")[:300],
                    "content_full": chunk.get("content", "")  # Full content for analysis
                })
            
            cls._current_log.add_step("rag_response", {
                "chunks_count": len(chunks),
                "total_context_length": total_context_length,
                "chunks": chunks_summary
            })
    
    @classmethod
    def log_prompt_construction(cls, system_prompt: str = None, user_prompt: str = None, 
                                 rag_context: str = None, full_prompt: str = None):
        """Log the prompt being sent to LLM"""
        if cls._current_log:
            cls._current_log.add_step("prompt_construction", {
                "system_prompt_length": len(system_prompt) if system_prompt else 0,
                "system_prompt_preview": system_prompt[:500] if system_prompt else None,
                "user_prompt_length": len(user_prompt) if user_prompt else 0,
                "user_prompt": user_prompt,  # Full user prompt (usually shorter)
                "rag_context_length": len(rag_context) if rag_context else 0,
                "rag_context_preview": rag_context[:1000] if rag_context else None,
                "full_prompt_length": len(full_prompt) if full_prompt else 0
            })
    
    @classmethod
    def log_llm_request(cls, model: str, messages: List[Dict], temperature: float = 0.7):
        """Log LLM API request"""
        if cls._current_log:
            # Sanitize messages for logging
            messages_log = []
            for msg in messages:
                messages_log.append({
                    "role": msg.get("role"),
                    "content_length": len(msg.get("content", "")),
                    "content_preview": msg.get("content", "")[:500]
                })
            
            cls._current_log.add_step("llm_request", {
                "model": model,
                "temperature": temperature,
                "messages_count": len(messages),
                "messages": messages_log
            })
    
    @classmethod
    def log_llm_response(cls, model: str, response_content: str, 
                         tokens_prompt: int = 0, tokens_completion: int = 0):
        """Log LLM response received"""
        if cls._current_log:
            cls._current_log.add_step("llm_response", {
                "model": model,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "tokens_total": tokens_prompt + tokens_completion,
                "response_length": len(response_content),
                "response_preview": response_content[:1000],
                "response_full": response_content  # Full response for analysis
            })
    
    @classmethod
    def log_custom(cls, step_name: str, data: Dict[str, Any]):
        """Log a custom step"""
        if cls._current_log:
            cls._current_log.add_step(step_name, data)
    
    @classmethod
    def complete_test(cls, status: str, output: Any = None, error: str = None):
        """Complete the current test"""
        if cls._current_log:
            cls._current_log.complete(status, output, error)
            log = cls._current_log
            cls._current_log = None
            return log
        return None
    
    @classmethod
    def list_logs(cls, limit: int = 20) -> List[Dict]:
        """List recent test logs"""
        log_files = sorted(LOGS_DIR.glob("*.json"), reverse=True)[:limit]
        logs = []
        for f in log_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    # Add summary info
                    logs.append({
                        "filename": f.name,
                        "test_id": data.get("test_id"),
                        "agent_id": data.get("agent_id"),
                        "agent_name": data.get("agent_name"),
                        "task_preview": data.get("task_description", "")[:100],
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "steps_count": len(data.get("steps", [])),
                        "status": data.get("result", {}).get("status") if data.get("result") else "running"
                    })
            except Exception as e:
                logs.append({"filename": f.name, "error": str(e)})
        return logs
    
    @classmethod
    def get_log(cls, test_id: str) -> Optional[Dict]:
        """Get a specific test log by ID"""
        for f in LOGS_DIR.glob("*.json"):
            if test_id in f.name:
                with open(f, 'r', encoding='utf-8') as file:
                    return json.load(file)
        return None
    
    @classmethod
    def get_log_by_filename(cls, filename: str) -> Optional[Dict]:
        """Get a specific test log by filename"""
        filepath = LOGS_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as file:
                return json.load(file)
        return None


# Singleton-like access
def get_logger() -> type[AgentTestLogger]:
    return AgentTestLogger
