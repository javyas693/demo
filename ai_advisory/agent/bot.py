from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk import Runner
from google.genai import types
# ADK currently supports GeminiModel but lets just pass model string directly to Agent if using default
from google.adk.models.anthropic_llm import AnthropicLlm

from ai_advisory.agent.tools import AGENT_TOOLS
import json

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
    1. GREETING → First turn only. Ask for the user's name. → response_type: greeting, payload: { "next_question": { "question_number": 0, "section_name": "Introduction", "question_text": "...", "answer_options": [], "free_text_only": true } }
    2. NAME RECEIVED → 
    After name is provided (last_answer_mapped is null), and after each risk answer is successfully mapped using semantic intent.
    Capture user_name exactly, set in every response from now on → ask Question 1 → response_type: question, last_answer_mapped: null
    payload: {
      "progress": { "questions_answered": <0-3>, "questions_total": 3, "percent_complete": <0-100> },
      "last_answer_mapped": { "question_name": "...", "user_raw_input": "...", "mapped_to": "...", "score_awarded": <float> } or null,
      "next_question": { "question_number": <1-3>, "section_name": "...", "question_text": "...", "free_text_only": true, "answer_options": [ { "text": "...", "display_order": <int> } ] }
    }
    3. QUESTION 1 (Investment Goals) → ask conversationally: "What are you hoping to achieve with this investment?"
    4. QUESTION 2 (Risk Comfort) → ask conversationally: "How would you describe your comfort level with investment risk?"
    5. QUESTION 3 (Risk Tolerance) → ask conversationally: "If your portfolio dropped 10% suddenly, what would you do?"
    6. After Q3 mapped → call calculate_risk_score_tool with [score1, score2, score3] 
     Include the next question about concentrated position.
     response_type: risk_score_complete
     payload: {
      "progress": { "questions_answered": 3, "questions_total": 3, "percent_complete": 100 },
      "risk_score_result": <exact unmodified output of calculate_risk_score_tool>,
      "next_question": { "section_name": "Concentrated Position", "question_text": "...", "free_text_only": true, "follow_up_fields": [
        { "field": "ticker_symbol", "label": "Stock Symbol", "type": "text", "required": true },
        { "field": "acquisition_date", "label": "Date of Acquisition", "type": "date", "required": true },
        { "field": "shares_held", "label": "Number of Shares", "type": "number", "required": true }
      ]}
    }
    7. Collect ticker_symbol, acquisition_date, shares_held conversationally
    8. Call analyze_concentrated_position_tool → response_type: analysis_result

    ## ANSWER BUCKETS
    Never reveal scores or bucket names to the user. Map free-text answers using semantic intent. 
    DO NOT SHOW THE REASONING OR THE MAPPING TO THE USER. JUST SHOW THE NEXT QUESTION.

    Question 1 — Investment Goals:
      Maximizing Current Income                         → 0.167
      Emphasizing Income With Some Potential For Growth → 0.125
      Emphasizing Growth With Some Potential For Income → 0.083
      Growth                                            → 0.042
      Maximizing Growth                                 → 0.000

    Question 2 — Risk Comfort:
      Conservative            → 0.167
      Moderately Conservative → 0.125
      Moderate                → 0.083
      Moderately Aggressive   → 0.042
      Aggressive              → 0.000

    Question 3 — Risk Tolerance:
      Go to cash                 → 0.167
      Sell 20% of the portfolio  → 0.125
      Do nothing                 → 0.083
      Buy 5% of the portfolio    → 0.042
      Buy 20% of the portfolio   → 0.000

    ## TOOL RULES
    - Never call a tool before all required inputs are collected
    - Never modify tool output — insert it into payload exactly as returned
    - Tool failure → response_type: error, error_code: TOOL_FAILURE, recoverable: false

"""
TEMP_INSTRUCTION = """
    ## MAPPING RULES
    - HIGH confidence → map immediately, proceed to next question
    - MEDIUM confidence → use response_type: clarification, ask one natural follow-up
    - LOW confidence → keep clarifying until resolved
    - After 3 failed clarification attempts → map to the more conservative bucket and proceed
    - Total mapping failure → response_type: error, error_code: ANSWER_MAPPING_FAILED, recoverable: true
"""

APP_NAME = "financial-ai-assistamt"

class ChatSessionManager:
    """Manages a chat session using the Google ADK (Agent Development Kit)."""
    def __init__(self):
        
        # Initialize the model via ADK
        # The underlying client handles API keys via environment variables
        self.model = AnthropicLlm(
            model="claude-opus-4-6",
            max_tokens=8192,
            temperature=0,
        )
        
        # Define the ADK Agent
        self.agent = Agent(
            name="financial_planner",
            description="A Financial Planning Assistant that scores risk and analyzes positions.",
            instruction=get_system_instruction(),
            tools=AGENT_TOOLS,
            model=self.model,
            generate_content_config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Define the session manager using InMemorySessionService
        self.session_service = InMemorySessionService()
        
        # Define the ADK Runner to orchestrate the Agent with the Session
        self.runner = Runner(
            agent=self.agent,
            app_name=APP_NAME,
            session_service=self.session_service,
            auto_create_session=True
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
        Parses the agent's JSON response and runs basic validation.
        """
        try:
            cleaned = raw.strip()
        
            # ✅ Strip markdown fences if present
            if cleaned.startswith("```"):
                # Remove opening fence (```json or ```)
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                # Remove closing fence
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            response = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Should not happen if response_mime_type is enforced,
            # but handle defensively
            return self.build_error_response(
                conversation_id=expected_conversation_id,
                error_code="PARSE_FAILURE",
                message=f"Agent returned invalid JSON: {str(e)}"
            )

        # Validate conversation_id integrity
        if response.get("conversation_id") != expected_conversation_id:
            response["conversation_id"] = expected_conversation_id

        # Validate payload exists
        if "payload" not in response:
            return build_error_response(
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
        
    async def send_message(self, message: str, conversation_id: str, user_id: str) -> dict:
        """
        Sends a message to the agent using the ADK Runner and returns a response.
        If the agent invoked a tool, we will include the chart data in the return payload.
        """

        raw_response = ""
        session = await self.get_or_create_session(
            conversationId=conversation_id,
            userId=user_id
        )

        from google.genai import types
        # Execute the agent step via ADK
        async for event in self.runner.run_async(
            user_id=user_id, 
            session_id=session.id, 
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=message)])
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    raw_response = event.content.parts[0].text
        # log the raw response
        print(f"Raw response: {raw_response}")
        result_payload = self.parse_and_validate(raw_response, conversation_id)
        return result_payload
