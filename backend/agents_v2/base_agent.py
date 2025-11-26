"""
Base Agent V2 - Foundation for artifact-based agents
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from openai import OpenAI

logger = logging.getLogger(__name__)


class BaseAgentV2(ABC):
    """
    Base class for V2 agents that produce structured artifacts.
    
    All agents inherit from this class and implement:
    - get_system_prompt(): Returns the agent's system prompt
    - get_artifact_types(): Returns list of artifact types this agent produces
    - process_response(): Parses LLM response into artifacts
    """
    
    def __init__(self, execution_id: int, db_session=None):
        self.execution_id = execution_id
        self.db = db_session
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        self.agent_id = self.get_agent_id()
        self.artifacts_produced = []
        self.questions_asked = []
    
    @abstractmethod
    def get_agent_id(self) -> str:
        """Return agent identifier (ba, architect, apex, etc.)"""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass
    
    @abstractmethod
    def get_artifact_types(self) -> List[str]:
        """Return list of artifact types this agent produces"""
        pass
    
    @abstractmethod
    def process_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into artifact dictionaries"""
        pass
    
    def build_context(self, artifacts: List[Dict], questions: List[Dict]) -> str:
        """Build context string from existing artifacts and questions"""
        context_parts = []
        
        # Add artifacts context
        if artifacts:
            context_parts.append("## EXISTING ARTIFACTS\n")
            for artifact in artifacts:
                context_parts.append(f"### {artifact['artifact_code']}: {artifact['title']}")
                context_parts.append(f"Type: {artifact['artifact_type']}")
                context_parts.append(f"Status: {artifact['status']}")
                context_parts.append(f"Content:\n```json\n{json.dumps(artifact['content'], indent=2, ensure_ascii=False)}\n```\n")
        
        # Add answered questions context
        answered = [q for q in questions if q.get('status') == 'answered']
        if answered:
            context_parts.append("## ANSWERED QUESTIONS\n")
            for q in answered:
                context_parts.append(f"### {q['question_code']}")
                context_parts.append(f"From: {q['from_agent']} → To: {q['to_agent']}")
                context_parts.append(f"Question: {q['question']}")
                context_parts.append(f"Answer: {q['answer']}")
                if q.get('recommendation'):
                    context_parts.append(f"Recommendation: {q['recommendation']}")
                context_parts.append("")
        
        return "\n".join(context_parts)
    
    def call_llm(self, user_prompt: str, context: str = "") -> str:
        """Call OpenAI API with system prompt and user content"""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
        ]
        
        if context:
            messages.append({"role": "user", "content": f"CONTEXT:\n{context}"})
            messages.append({"role": "assistant", "content": "I've reviewed the context. Please provide the project requirements."})
        
        messages.append({"role": "user", "content": user_prompt})
        
        logger.info(f"[{self.agent_id}] Calling LLM with {len(messages)} messages")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=16000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[{self.agent_id}] LLM call failed: {e}")
            raise
    
    def execute(self, project_requirements: str, context_artifacts: List[Dict] = None, context_questions: List[Dict] = None) -> Dict[str, Any]:
        """
        Execute the agent to produce artifacts.
        
        Args:
            project_requirements: The raw project requirements text
            context_artifacts: List of existing artifacts for context
            context_questions: List of questions (pending and answered)
        
        Returns:
            Dict with artifacts, questions, and execution metadata
        """
        start_time = datetime.utcnow()
        
        # Build context
        context = self.build_context(
            context_artifacts or [],
            context_questions or []
        )
        
        # Call LLM
        try:
            raw_response = self.call_llm(project_requirements, context)
            
            # Process response into artifacts
            artifacts = self.process_response(raw_response)
            
            return {
                "success": True,
                "agent_id": self.agent_id,
                "execution_id": self.execution_id,
                "artifacts": artifacts,
                "questions": self.questions_asked,
                "raw_response": raw_response,
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
            }
        except Exception as e:
            logger.error(f"[{self.agent_id}] Execution failed: {e}")
            return {
                "success": False,
                "agent_id": self.agent_id,
                "execution_id": self.execution_id,
                "error": str(e),
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
            }
    
    def create_question(self, to_agent: str, context: str, question: str, related_artifacts: List[str] = None) -> Dict:
        """Create a question to another agent"""
        q = {
            "to_agent": to_agent,
            "context": context,
            "question": question,
            "related_artifacts": related_artifacts or []
        }
        self.questions_asked.append(q)
        return q
    
    @staticmethod
    def extract_json_from_response(response: str, start_marker: str = "```json", end_marker: str = "```") -> List[Dict]:
        """Extract JSON blocks from LLM response"""
        artifacts = []
        
        # Find all JSON blocks
        parts = response.split(start_marker)
        for part in parts[1:]:  # Skip first part (before any JSON)
            if end_marker in part:
                json_str = part.split(end_marker)[0].strip()
                try:
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        artifacts.extend(data)
                    else:
                        artifacts.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON block: {e}")
                    continue
        
        return artifacts
