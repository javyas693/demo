from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk import Runner
from google.genai import types
from google.adk.models.anthropic_llm import AnthropicLlm

from ai_advisory.agent.tools import AGENT_TOOLS

from pydantic import BaseModel
from typing import Optional, Dict, Any

import json
import os


def get_system_instruction() -> str:
    """Constructs the system instruction dynamically with the questions."""
    
    return """
You are a financial risk assessment agent. Your goal is to introduce yourself, get the users name and then ask them a series of questions to understand their risk profile. 
The user can answer the questions in a free text format. 
CRITICAL: Your entire response must be only a single JSON object.

## RESPONSE ENVELOPE
{
  "conversation_id": "<echo back exactly as received>",
  "response_type": "<see types below>",
  "sequence": <integer, increment by 1 each turn>,
  "user_name": <null until provided, then always echo back exactly as given>,
  "agent_message": <the only field the user sees — warm, conversational tone>,
  "payload": <object, shape depends on response_type>
}

## CONVERSATION FLOW
1. GREETING → First turn only. Ask for the user's name.
2. NAME RECEIVED → ask Question 1
3. QUESTION 1 (Investment Goals)
4. QUESTION 2 (Risk Comfort)
5. QUESTION 3 (Risk Tolerance)
6. After Q3 mapped → call calculate_risk_score_tool
7. Ask concentrated position question
8. Call analyze_concentrated_position_tool
"""

APP_NAME = "financial-ai-assistant"


class AgentResponse(BaseModel):
    conversation_id: str
    response_type: str
    sequence: int
    user_name: Optional[str]
    agent_message: str
    payload: Dict[str, Any]


class ChatSessionManager:
    """Manages a chat session using the Google ADK (Agent Development Kit)."""

    def __init__(self):

        # Initialize the model via ADK
        self.model = AnthropicLlm(
            model="claude-opus-4-6",
            max_tokens=8192,
            temperature=0,
            provider="anthropic",
            use_vertex=False
        )

        # Define the ADK Agent
        self.agent = Agent(
            name="financial_planner",
            description="A Financial Planning Assistant that scores risk and analyzes positions.",
            instruction=get_system_instruction(),
            tools=AGENT_TOOLS,
            model=self.model,
            output_schema=AgentResponse
        )

        # Session manager
        self.session_service = InMemorySessionService()

        # Runner orchestrates the agent
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service
        )

    def build_error_response(
        self,
        conversation_id: str,
        error_code: str,
        message: str
    ) -> dict:

        return {
            "conversation_id": conversation_id,
            "response_type": "error",
            "sequence": -1,
            "user_name": None,
            "agent_message": message,
            "payload": {
                "error_code": error_code,
                "recoverable": False,
                "message": message,
                "retry_context": {
                    "repeat_question_number": None,
                    "section_name": None
                }
            }
        }

    def parse_and_validate(self, raw: str, expected_conversation_id: str) -> dict:
        """
        Parses the agent JSON response.
        """

        try:
            cleaned = raw.strip()

            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            response = json.loads(cleaned)

        except json.JSONDecodeError as e:

            return self.build_error_response(
                conversation_id=expected_conversation_id,
                error_code="PARSE_FAILURE",
                message=f"Agent returned invalid JSON: {str(e)}"
            )

        if response.get("conversation_id") != expected_conversation_id:
            response["conversation_id"] = expected_conversation_id

        if "payload" not in response:
            return self.build_error_response(
                conversation_id=expected_conversation_id,
                error_code="MISSING_PAYLOAD",
                message="Agent response missing payload field"
            )

        return response

    async def get_or_create_session(self, conversationId: str, userId: str):

        session = await self.session_service.get_session(
            session_id=conversationId,
            app_name=APP_NAME,
            user_id=userId
        )

        if not session:

            session = await self.session_service.create_session(
                session_id=conversationId,
                app_name=APP_NAME,
                user_id=userId
            )

        return session

    async def send_message(
        self,
        message: str,
        conversation_id: str,
        user_id: str
    ) -> dict:

        raw_response = ""

        try:
            session = await self.get_or_create_session(
                conversationId=conversation_id,
                userId=user_id
            )

            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=message)]
                )
            ):

                if event.is_final_response():

                    if event.content and event.content.parts:

                        raw_response = event.content.parts[0].text

            print(f"Raw response: {raw_response}")

            result_payload = self.parse_and_validate(
                raw_response,
                conversation_id
            )

            # Deterministic workflow control
            payload_data = result_payload.get("payload", {})

            def find_score_recursively(d):
                if not isinstance(d, dict):
                    return None
                if "final_risk_score" in d:
                    return d["final_risk_score"]
                if "total_risk_score" in d:
                    return d["total_risk_score"]
                for v in d.values():
                    if isinstance(v, dict):
                        res = find_score_recursively(v)
                        if res is not None:
                            return res
                return None

            score_val = find_score_recursively(payload_data)
            
            if score_val is not None:
                if isinstance(score_val, (int, float)) and score_val <= 1.0:
                    score_val = round(100.0 - (100.0 * float(score_val)), 2)

                result_payload["response_type"] = "risk_score_complete"
                payload_data["final_risk_score"] = score_val
                payload_data["next_page"] = "your-capital-today"
                result_payload["payload"] = payload_data

            return result_payload

        except Exception as e:
            print(f"Agent failsafe triggered: {e}")
            return {
                "conversation_id": conversation_id,
                "response_type": "error",
                "sequence": -1,
                "user_name": None,
                "agent_message": "The AI assistant is temporarily unavailable.",
                "payload": {
                    "status": "fallback",
                    "error_code": "AGENT_UNAVAILABLE",
                    "message": str(e)
                }
            }