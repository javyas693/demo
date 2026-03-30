"""
Orchestrator Agent — Root agent (ADK entry point)

This is the brain of the financial advisor. It:
  1. Greets the user and transfers to the risk_assessor sub-agent
  2. When risk assessment escalates back, transfers to position_gatherer
  3. When position data escalates back, invokes position_analyzer via AgentTool
  4. Assembles and presents the final analysis to the user
  5. Handles follow-up questions and can re-invoke any strategy

EXTENSIBILITY:
  To add a new strategy (e.g., income optimization):
  1. Add a data-gathering sub-agent → register in sub_agents list
  2. Add an analysis agent → wrap in AgentTool, add to tools list
  3. Add routing logic to the orchestrator instruction
  4. Add state keys in shared/state_keys.py

The orchestrator reads session state to understand where the user is in the
workflow. Each sub-agent writes to state and escalates; the orchestrator
checks state and decides the next step.
"""

from google.adk.agents import Agent
from google.adk.sessions import DatabaseSessionService
from google.adk import Runner
from google.genai import types
from google.adk.models.anthropic_llm import AnthropicLlm
import json
import time
import logging
from typing import Optional
from ai_advisory.api.models import AgentResponseEnvelope
# ── Import sub-agents (multi-turn, conversation owners) ──────────────────────
from ai_advisory.agents.risk_assessor.agent import risk_assessor_agent
from ai_advisory.agents.position_gatherer.agent import position_gatherer_agent

# ── Import analysis agents (single-shot, wrapped as AgentTool) ───────────────
#from agents.position_analyzer.agent import position_analyzer_agent

from ai_advisory.shared.response_schema import (
    RESPONSE_FORMAT_INSTRUCTION,
    ORCHESTRATOR_RESPONSE_TYPES,
)
logger = logging.getLogger(__name__)

# Response types that trigger auto-chaining to the next phase
AUTO_CHAIN_TRIGGERS = {
    "risk_score_complete",   # Risk done → position gathering
    "position_confirmed",    # Position collected → analysis
    "no_position",           # No position → summary/next steps
}

# The synthetic message sent to trigger the next phase
AUTO_CHAIN_MESSAGE = "Let's continue to the next step."

# Max auto-chain depth to prevent infinite loops
MAX_CHAIN_DEPTH = 3

# ── Orchestrator Instruction ─────────────────────────────────────────────────

ORCHESTRATOR_INSTRUCTION = f"""
You are the lead financial advisor coordinating a comprehensive financial
planning session. You manage the conversation flow by delegating to specialist
agents and assembling their results.

{RESPONSE_FORMAT_INSTRUCTION}

{ORCHESTRATOR_RESPONSE_TYPES}

## HOW TO READ SESSION STATE

Check these state keys to understand where the user is in the workflow:
- `risk_assessment_complete`: True/False
- `risk_profile_label`: The user's risk label (after assessment)
- `risk_score_final`: Numeric score (after assessment)
- `position_data_complete`: True/False
- `has_concentrated_position`: True/False
- `position_lots`: List of tax lot dicts (after collection)
- `position_ticker`: The concentrated position ticker
- `user_name`: The user's name (set by risk assessor)

## YOUR DECISION FLOW

### CRITICAL RULE: Transfer OR respond — never both.
When you transfer to a sub-agent, the sub-agent's response is what the client
receives, NOT yours. Any text you output alongside a transfer is lost.
Sub-agents produce their own JSON envelopes — they handle the formatting.
So: when transferring, just transfer. Don't output JSON yourself.
When NOT transferring (e.g., presenting analysis results), output your own JSON.

### Phase 1: New Session → Risk Assessment
If `risk_assessment_complete` is NOT True:
  → Transfer to the `risk_assessor` agent immediately. No JSON output.
  → The risk_assessor handles the greeting, name collection, and all 3 questions.
  → It produces valid JSON envelopes for every turn.

### Phase 2: Risk Complete → Position Gathering
When the risk_assessor escalates back (risk_assessment_complete is True)
and position_data_complete is NOT True:
  → Transfer to the `position_gatherer` agent immediately. No JSON output.
  → The position_gatherer handles asking about concentrated positions.

### Phase 3: Position Complete → Summary
When position_gatherer escalates back (position_data_complete is True):

  **If has_concentrated_position is True:**
    → response_type: "summary"
    → agent_message: "Thanks for sharing your position details. The next step is to simulate diversification of your concentrated position. Here's a summary of what we've discussed:"
    → payload: copy the position_gatherer's structured data (position_ticker, position_lots)

  **If has_concentrated_position is False:**
    → response_type: "summary"
    → YOU respond with JSON.

## PRESENTATION RULES FOR summary

When wrapping the analyzer's output:
1. agent_message: warm narrative addressing the user by name, summarizing with risk score, position_ticker and position_lots.
2. payload: copy the risk_assessor's structured data (risk_score_final) and position_gatherer's structured data (position_ticker, position_lots).

## WHEN YOU OUTPUT JSON vs WHEN YOU DON'T

  Transfer to sub-agent → NO JSON from you (sub-agent responds)
  AgentTool call         → YES JSON from you (you stay in control)
  Follow-up question     → YES JSON from you
  Error                  → YES JSON from you

## CRITICAL RULES

- Output ONLY a valid JSON object when responding. No fences, no preamble.
- When transferring, output NOTHING — just transfer.
- Always address the user by name in agent_message once known (from state).
- Never reveal raw risk scores in agent_message.
"""

APP_NAME = "financial-ai-assistamt"

class ChatSessionManager:
    """Manages a chat session using the Google ADK (Agent Development Kit)."""
    def __init__(self):
        
        # Initialize the model via ADK
        # The underlying client handles API keys via environment variables
        self.model = AnthropicLlm(
            model="claude-sonnet-4-6", #claude-opus-4-6
            max_tokens=8192,
            temperature=0,
        )
        
        # Define the ADK Agent
        self.agent = Agent(
            name="financial_advisor_orchestrator",
            description=(
                "Lead financial advisor that orchestrates a comprehensive planning session. "
                "Coordinates risk assessment, position analysis, and strategy recommendations "
                "by delegating to specialist agents."
            ),
            instruction=ORCHESTRATOR_INSTRUCTION,
            # Sub-agents: these can OWN the conversation via transfer_to_agent.
            # The orchestrator loses control until the sub-agent escalates back.
            # Use for: multi-turn data gathering, Q&A, clarification flows.
            sub_agents=[
                risk_assessor_agent,
                position_gatherer_agent,
                # Future: portfolio_optimizer_gatherer,
                # Future: income_strategy_gatherer,
            ],
            tools=[],
            model=self.model,
            generate_content_config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Define the session manager using DatabaseSessionService (SQLite-backed)
        from ai_advisory.db.database import DB_PATH
        self.session_service = DatabaseSessionService(f"sqlite:///{DB_PATH}")
        
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


        return AgentResponseEnvelope(
            conversation_id=conversation_id,
            response_type="error",
            user_name=None,
            agent_message=message,
            payload={
                "error_code": error_code,
                "recoverable": False,
                "message": message,
                "responding_agent": "orchestrator",
            },
            metadata={
                "responding_agent": "orchestrator",
                "parse_status": "fallback",
            },
        )

    def _try_parse(
      self,
        text: str, 
        conversation_id: Optional[str]
    ) -> Optional[AgentResponseEnvelope]:
        """Attempt to parse text as JSON and validate against the envelope schema."""
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            # if conversation_id is None, then set it to expected_conversation_id
            conv_id = data.get("conversation_id") if data.get("conversation_id") is not None else conversation_id
            # Ensure required fields exist with defaults
            envelope = AgentResponseEnvelope(
                conversation_id=conv_id,
                response_type=data.get("response_type", "unknown"),
                user_name=data.get("user_name"),
                agent_message=data.get("agent_message", ""),
                payload=data.get("payload", {}),
            )
            return envelope

        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def parse_and_validate(self, raw: str, expected_conversation_id: str) -> AgentResponseEnvelope:
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

            #print(f"Cleaned response: {cleaned}")
            response = self._try_parse(cleaned, expected_conversation_id)
            if response is None:
                return self.build_error_response(
                    conversation_id=expected_conversation_id,
                    error_code="PARSE_FAILURE",
                    message=f"Agent returned invalid JSON. _try_parse returned None."
                )
        except json.JSONDecodeError as e:
            # Should not happen if response_mime_type is enforced,
            # but handle defensively
            return self.build_error_response(
                conversation_id=expected_conversation_id,
                error_code="PARSE_FAILURE",
                message=f"Agent returned invalid JSON: {str(e)}"
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

    async def run_agent_turn(
        self,
        user_id: str,
        session_id: str,
        message: str,
        conversation_id: str,
    ) -> tuple[AgentResponseEnvelope, str]:
        """
        Sends a message to the agent using the ADK Runner and returns a response.
        If the agent invoked a tool, we will include the chart data in the return payload.
        """

        from google.genai import types
        raw_response = ""  # guard against unbound if no text part in final event
        # Execute the agent step via ADK
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=message)])
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    raw_response = event.content.parts[0].text

        # When a sub-agent escalates via tool, ADK may not emit text on that
        # turn — raw_response stays empty and parse fails. Recover by reading
        # session state and synthesising the correct transition envelope so the
        # auto-chain can proceed normally.
        if not raw_response:
            logger.warning(
                "run_agent_turn: no text in final event for conversation %s — "
                "checking session state to synthesise transition response",
                conversation_id,
            )
            try:
                sess = await self.session_service.get_session(
                    session_id=session_id, app_name=APP_NAME, user_id=user_id
                )
                st = (sess.state or {}) if sess else {}
                if st.get("position_data_complete"):
                    raw_response = json.dumps({
                        "response_type": "position_confirmed",
                        "agent_message": "Your position data has been saved.",
                        "payload": {},
                    })
                    logger.info("Synthesised position_confirmed for conversation %s", conversation_id)
                elif st.get("risk_assessment_complete"):
                    raw_response = json.dumps({
                        "response_type": "risk_score_complete",
                        "agent_message": "Risk assessment complete.",
                        "payload": {},
                    })
                    logger.info("Synthesised risk_score_complete for conversation %s", conversation_id)
            except Exception as synth_err:
                logger.warning("Could not synthesise transition response: %s", synth_err)

        result_payload = self.parse_and_validate(raw_response, conversation_id)
        return result_payload, result_payload.response_type

    async def send_message(self, message: str, conversation_id: str, user_id: str) -> AgentResponseEnvelope:
        """
        Sends a message to the agent using the ADK Runner and returns a response.
        If the agent invoked a tool, we will include the chart data in the return payload.
        """

        raw_response = ""
        session = await self.get_or_create_session(
            conversationId=conversation_id,
            userId=user_id
        )
        start_time = time.time()
        # ── Run the agent turn (with auto-chaining) ──────────────────────────
        chain_history = []  # Track transitions for metadata

        try:
            # First run: the user's actual message
            envelope, response_type = await self.run_agent_turn(
              user_id=user_id,
              session_id=session.id,
              message=message,
              conversation_id=conversation_id,
          )

          # Auto-chain: if this is a transition response, send a follow-up
            chain_depth = 0
            while response_type in AUTO_CHAIN_TRIGGERS and chain_depth < MAX_CHAIN_DEPTH:
                chain_depth += 1

                # Save the transition response for metadata
                chain_history.append({
                    "response_type": response_type,
                    "agent_message": envelope.agent_message,
                    "responding_agent": (envelope.metadata or {}).get("responding_agent"),
                    "payload_summary": _summarize_payload(envelope.payload),
                })

                logger.info(
                    "Auto-chaining from %s (depth %d) for conversation %s",
                    response_type, chain_depth, conversation_id,
                )

                # Send synthetic follow-up to trigger next phase
                envelope, response_type = await self.run_agent_turn(
                    user_id=user_id,
                    session_id=session.id,
                    message=AUTO_CHAIN_MESSAGE,
                    conversation_id=conversation_id,
                )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("AGENT CRASH for conversation %s: %s: %s\n%s", conversation_id, type(e).__name__, e, tb)
            latency_ms = int((time.time() - start_time) * 1000)
            return AgentResponseEnvelope(
                conversation_id=conversation_id,
                response_type="error",
              user_name=None,
              agent_message="I'm sorry, I encountered an unexpected issue. Please try again.",
              payload={
                  "error_code": "AGENT_EXECUTION_ERROR",
                  "error_details": str(e),
                  "recoverable": True,
                  "suggested_action": "Please resend your message.",
              },
              metadata={
                  "responding_agent": "system",
                  "latency_ms": latency_ms,
              },
          )
        if envelope.metadata is None:
            envelope.metadata = {}

        # Include chain history so the UI knows a transition happened
        if chain_history:
            envelope.metadata["auto_chain_history"] = chain_history
            envelope.metadata["auto_chained"] = True
            envelope.metadata["chain_depth"] = len(chain_history)

        # ── Enrich summary payload from session state (ground truth) ─────────
        # The LLM may omit or mis-copy fields; state always has the real values.
        if envelope.response_type == "summary":
            try:
                refreshed = await self.session_service.get_session(
                    session_id=conversation_id,
                    app_name=APP_NAME,
                    user_id=user_id,
                )
                if refreshed and refreshed.state:
                    st = refreshed.state
                    if envelope.payload is None:
                        envelope.payload = {}
                    envelope.payload["position_ticker"]  = st.get("position_ticker")
                    envelope.payload["position_lots"]    = st.get("position_lots")
                    envelope.payload["starting_cash"]    = st.get("starting_cash")
                    envelope.payload["risk_score_final"] = st.get("risk_score_final")
                    envelope.payload["user_name"]        = st.get("user_name")
                    envelope.payload["horizon_years"]    = st.get("horizon_years")
                    envelope.payload["tlh_inventory"]    = st.get("tlh_inventory", 0.0)
                    logger.info(
                        "Enriched summary payload from state: ticker=%s lots=%d cash=%s risk=%s horizon=%s tlh=%s",
                        st.get("position_ticker"),
                        len(st.get("position_lots") or []),
                        st.get("starting_cash"),
                        st.get("risk_score_final"),
                        st.get("horizon_years"),
                        st.get("tlh_inventory"),
                    )
            except Exception as enrich_err:
                logger.warning("Could not enrich summary payload from state: %s", enrich_err)

        return envelope
# ── Helpers ──────────────────────────────────────────────────────────────────

def _summarize_payload(payload: dict) -> dict:
    """
    Extract key info from a transition payload for the chain history.
    Keeps metadata small while preserving useful info.
    """
    summary = {}

    if "risk_score_result" in payload:
        rsr = payload["risk_score_result"]
        # Handle both direct and nested tool response formats
        if isinstance(rsr, dict):
            if "save_risk_score_and_escalate_response" in rsr:
                inner = rsr["save_risk_score_and_escalate_response"]
                risk = inner.get("risk_score", {})
            else:
                risk = rsr
            summary["risk_label"] = risk.get("label")
            summary["risk_score"] = risk.get("composite_score")

    if "ticker" in payload:
        summary["ticker"] = payload["ticker"]
        summary["total_shares"] = payload.get("total_shares")
        lots = payload.get("lots", [])
        summary["lots_count"] = len(lots)

    if "progress" in payload:
        summary["progress"] = payload["progress"]

    return summary
