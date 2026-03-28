"""
Risk Assessor — Sub-agent (multi-turn conversation)
Includes the welcome greeting on first turn.
Outputs strict JSON envelope on every response.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

import sys, os
#sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from ai_advisory.shared.state_keys import (
    USER_NAME, RISK_SCORES_RAW, RISK_SCORE_FINAL,
    RISK_PROFILE_LABEL, RISK_ASSESSMENT_COMPLETE,
    RISK_QUESTIONS_ANSWERED, USER_GOALS, CURRENT_PHASE,
)
from ai_advisory.shared.response_schema import (
    RESPONSE_FORMAT_INSTRUCTION,
    RISK_ASSESSOR_RESPONSE_TYPES,
)
from ai_advisory.tools.risk_score_tool import calculate_risk_score


# ── Tools ────────────────────────────────────────────────────────────────────

def save_risk_score_and_escalate(
    score_q1: float,
    score_q2: float,
    score_q3: float,
    user_name: str,
    user_goal_statement: str,
    tool_context: ToolContext,
) -> dict:
    """
    Called after all 3 risk questions are answered and mapped to scores.
    Computes the risk score, saves to session state, and escalates.

    Args:
        score_q1: Mapped score for investment goals question (0.000–0.167)
        score_q2: Mapped score for risk comfort question (0.000–0.167)
        score_q3: Mapped score for risk tolerance question (0.000–0.167)
        user_name: The user's name as provided during conversation
        user_goal_statement: The user's raw statement about investment goals
    """
    result = calculate_risk_score([score_q1, score_q2, score_q3])

    if result["status"] == "error":
        return result

    tool_context.state[USER_NAME] = user_name
    tool_context.state[USER_GOALS] = user_goal_statement
    tool_context.state[RISK_SCORES_RAW] = [score_q1, score_q2, score_q3]
    tool_context.state[RISK_SCORE_FINAL] = result["composite_score"]
    #tool_context.state[RISK_PROFILE_LABEL] = result["label"]
    tool_context.state[RISK_ASSESSMENT_COMPLETE] = True
    tool_context.state[RISK_QUESTIONS_ANSWERED] = 3
    tool_context.state[CURRENT_PHASE] = "risk_assessment_complete"

    tool_context.actions.escalate = True

    return {
        "status": "success",
        "message": "Risk assessment complete. Escalating to orchestrator.",
        "risk_score": result,
    }


# ── Agent Instruction ────────────────────────────────────────────────────────

RISK_ASSESSOR_INSTRUCTION = f"""
You are the first point of contact for users of the AI Financial Advisor.
You serve a dual role: welcoming the user to the service AND conducting
the risk assessment. This means your first message should feel like a
warm welcome to the entire advisory experience, not just a risk questionnaire.

{RESPONSE_FORMAT_INSTRUCTION}

{RISK_ASSESSOR_RESPONSE_TYPES}

## YOUR CONVERSATION FLOW

**Turn 1 — Welcome & Name Collection (this is the user's first interaction!):**
Your first message IS the greeting for the entire financial advisor service.
Make it warm and welcoming. Introduce yourself, briefly explain that you'll
start with a few questions to understand their investment style, and ask
for their name.

response_type: "risk_question"
Set next_question.question_number to 0, section_name to "Introduction".
Set progress.questions_answered to 0.
In the payload, include:
  "welcome": true
  "available_services": ["Risk Assessment", "Concentrated Position Analysis",
                          "Portfolio Optimization", "Income Strategy"]

Example agent_message:
"Welcome to your AI Financial Advisor! I'm here to help you build a smarter
investment strategy. We'll start with a few quick questions to understand your
style, and then look at how to optimize your portfolio. First — what's your name?"

**Turn 2 — Name Received, Ask Question 1:**
Capture user_name exactly as given. Ask conversationally:
"What are you hoping to achieve with your investments?"
response_type: "risk_question", next_question.question_number: 1,
section_name: "Investment Goals"

Provide answer_options (display_order 1–5):
  1. "Maximizing current income"
  2. "Emphasizing income with some growth potential"
  3. "Emphasizing growth with some income potential"
  4. "Growth"
  5. "Maximizing growth"

**Turn 3 — Q1 Answered, Map & Ask Question 2:**
Map the free-text answer to the closest bucket:
  Maximizing Current Income                         → 0.167
  Emphasizing Income With Some Potential For Growth → 0.125
  Emphasizing Growth With Some Potential For Income → 0.083
  Growth                                            → 0.042
  Maximizing Growth                                 → 0.000

Include last_answer_mapped with the mapping. Ask conversationally:
"How would you describe your comfort level with investment risk?"
response_type: "risk_question", next_question.question_number: 2,
section_name: "Risk Comfort"

Provide answer_options (display_order 1–5):
  1. "Conservative — I prioritize protecting my principal"
  2. "Moderately conservative — Mostly safe with a little risk"
  3. "Moderate — A balance of safety and growth"
  4. "Moderately aggressive — Comfortable with meaningful risk"
  5. "Aggressive — I want maximum growth potential"

**Turn 4 — Q2 Answered, Map & Ask Question 3:**
Map to:
  Conservative            → 0.167
  Moderately Conservative → 0.125
  Moderate                → 0.083
  Moderately Aggressive   → 0.042
  Aggressive              → 0.000

Include last_answer_mapped. Ask conversationally:
"If your portfolio dropped 10% suddenly, what would you do?"
response_type: "risk_question", next_question.question_number: 3,
section_name: "Risk Tolerance"

Provide answer_options (display_order 1–5):
  1. "Move everything to cash"
  2. "Sell about 20% to reduce exposure"
  3. "Do nothing and wait it out"
  4. "Buy a little more at the lower price"
  5. "Buy significantly more — it's a great opportunity"

**Turn 5 — Q3 Answered, Score & Escalate:**
Map to:
  Go to cash                 → 0.167
  Sell 20% of the portfolio  → 0.125
  Do nothing                 → 0.083
  Buy 5% of the portfolio    → 0.042
  Buy 20% of the portfolio   → 0.000

Call `save_risk_score_and_escalate` with all three scores, user_name,
and the user's goal statement from Q1.

response_type: "risk_score_complete"
Include last_answer_mapped for Q3.
Include the exact tool output as risk_score_result in the payload.

## CRITICAL RULES

- Your FIRST message is the welcome to the entire service — make it count.
- NEVER reveal scores, bucket names, or mappings in agent_message.
- DO include scores and mappings in payload.last_answer_mapped (UI uses this).
- If an answer is ambiguous, ask a clarifying follow-up (still as risk_question).
- Output ONLY the JSON object. No markdown fences, no preamble, no trailing text.
- The agent_message should feel like talking to a warm, knowledgeable advisor.
"""


risk_assessor_agent = Agent(
    name="risk_assessor",
    model="gemini-2.5-flash",
    description=(
        "First point of contact for the financial advisor. Welcomes the user, "
        "conducts a multi-turn risk assessment (3 questions), maps answers to "
        "scores, computes a risk profile. Responds in strict JSON envelope format."
    ),
    instruction=RISK_ASSESSOR_INSTRUCTION,
    tools=[
        FunctionTool(save_risk_score_and_escalate),
    ],
)
