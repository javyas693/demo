"""
Response Schema — The JSON contract between all agents and the UI.

Every agent response MUST conform to this envelope. The UI parses
`response_type` to determine which component to render, and `payload`
for the data that component needs.

RESPONSE TYPES BY AGENT:
  Orchestrator:
    - greeting              → Initial welcome, before risk assessment
    - handoff               → Transitioning to a specialist agent
    - summary               → Final plan / wrap-up
    - error                 → Something went wrong

  Risk Assessor:
    - risk_question         → Asking one of the 3 risk questions
    - risk_score_complete   → All questions answered, score computed

  Position Gatherer:
    - position_question     → Asking about holdings / lots
    - position_confirmed    → User confirmed data, ready for analysis
    - no_position           → User has no concentrated position
"""

# ── Response type constants ──────────────────────────────────────────────────
# Orchestrator
GREETING = "greeting"
HANDOFF = "handoff"
SUMMARY = "summary"
ERROR = "error"

# Risk Assessor
RISK_QUESTION = "risk_question"
RISK_SCORE_COMPLETE = "risk_score_complete"

# Position Gatherer
POSITION_QUESTION = "position_question"
POSITION_CONFIRMED = "position_confirmed"
NO_POSITION = "no_position"


# ── The JSON instruction block shared by ALL agents ──────────────────────────
# This gets injected into every agent's system prompt.

RESPONSE_FORMAT_INSTRUCTION = """
## MANDATORY RESPONSE FORMAT

CRITICAL: You MUST respond with ONLY a valid JSON object — no markdown, no backticks,
no extra text before or after. Every single response must follow this envelope:

```
{
  "conversation_id": "<echo back the conversation_id from the user's message, or null if not provided>",
  "response_type": "<one of the types listed below>",
  "user_name": <null until the user provides their name, then always echo it back>,
  "agent_message": "<the ONLY text the user sees — warm, conversational tone>",
  "payload": { <shape depends on response_type — see below> }
}
```

RULES:
- `agent_message` is what gets displayed to the user. It must be complete,
  friendly, and conversational. Never put JSON or technical details in it.
- `payload` carries structured data for the UI to render widgets, progress
  bars, charts, etc. The user does NOT see payload directly.
- NEVER include score values, bucket names, or internal mappings in `agent_message`.
- If a field is not applicable, use null — never omit required fields.
"""


# ── Per-agent response type definitions ──────────────────────────────────────

RISK_ASSESSOR_RESPONSE_TYPES = """
## YOUR RESPONSE TYPES

### response_type: "risk_question"
Use when asking one of the 3 risk assessment questions (or the initial name question).

payload: {
  "progress": {
    "questions_answered": <0-3>,
    "questions_total": 3,
    "percent_complete": <0-100 integer>
  },
  "last_answer_mapped": {
    "question_number": <1-3>,
    "question_name": "<e.g. Investment Goals>",
    "user_raw_input": "<what the user actually said>",
    "mapped_to": "<the bucket label, e.g. Moderate>",
    "score_awarded": <float, e.g. 0.083>
  } or null if this is the first question,
  "next_question": {
    "question_number": <0 for name, 1-3 for risk questions>,
    "section_name": "<e.g. Introduction, Investment Goals, Risk Comfort, Risk Tolerance>",
    "question_text": "<the conversational question — same as in agent_message>",
    "free_text_only": true,
    "answer_options": [
      { "text": "<option text>", "display_order": <int> }
    ]
  }
}

### response_type: "risk_score_complete"
Use after Q3 is mapped AND calculate_risk_score has been called.

payload: {
  "progress": {
    "questions_answered": 3,
    "questions_total": 3,
    "percent_complete": 100
  },
  "last_answer_mapped": {
    "question_number": 3,
    "question_name": "Risk Tolerance",
    "user_raw_input": "<what the user said>",
    "mapped_to": "<bucket label>",
    "score_awarded": <float>
  },
  "risk_score_result": <exact unmodified output from calculate_risk_score tool>
}
"""


POSITION_GATHERER_RESPONSE_TYPES = """
## YOUR RESPONSE TYPES

### response_type: "position_question"
Use when asking about the user's concentrated position or collecting lot details.

payload: {
  "progress": {
    "phase": "position_gathering",
    "lots_collected": <int — how many lots collected so far>,
    "status": "<asking_if_position | collecting_ticker | collecting_lots | confirming>"
  },
  "collected_so_far": [
    {
      "lot_id": "<lot_1, lot_2, ...>",
      "ticker": "<AAPL>",
      "shares": <int>,
      "cost_basis": <float>,
      "acquisition_date": "<YYYY-MM-DD>"
    }
  ] or null if nothing collected yet,
  "next_field": {
    "field_name": "<e.g. ticker_symbol, lot_details, confirmation>",
    "question_text": "<the conversational question>",
    "field_type": "<text | number | date | confirmation>"
  }
}

### response_type: "position_confirmed"
Use after the user confirms their lot data and before escalating.

payload: {
  "ticker": "<AAPL>",
  "total_shares": <int>,
  "lots": [
    {
      "lot_id": "lot_1",
      "ticker": "<AAPL>",
      "shares": <int>,
      "cost_basis": <float>,
      "acquisition_date": "<YYYY-MM-DD>"
    }
  ]
}

### response_type: "no_position"
Use when the user indicates they do NOT have a concentrated position.

payload: {
  "has_concentrated_position": false,
  "next_steps": "<brief description of what happens next>"
}
"""


ORCHESTRATOR_RESPONSE_TYPES = """
## YOUR RESPONSE TYPES

### response_type: "greeting"
Use for the very first message of the session.

payload: {
  "phase": "welcome",
  "available_services": [
    "Risk Assessment",
    "Concentrated Position Analysis",
    "Portfolio Optimization",
    "Income Strategy"
  ]
}

### response_type: "handoff"
Use when transferring to a specialist agent.

payload: {
  "transferring_to": "<risk_assessor | position_gatherer>",
  "reason": "<brief explanation of why this specialist is next>",
  "phase": "<risk_assessment | position_gathering>"
}

<<<<<<< HEAD
=======
### response_type: "analysis_result"
Use when presenting the output from a strategy AgentTool.

payload: {
  "analysis_type": "<concentrated_position_unwind | portfolio_optimization | income_strategy>",
  "risk_profile": {
    "label": "<Conservative | Moderate | ...>",
    "target_equity_allocation": <float>
  },
  "position_summary": {
    "ticker": "<AAPL>",
    "total_shares": <int>,
    "total_market_value": <float>,
    "total_unrealized_gain": <float>,
    "total_estimated_tax": <float>
  },
  "scenarios": [
    {
      "strategy_name": "<e.g. 20% Annual Selldown>",
      "description": "<brief description>",
      "years_to_complete": <int>,
      "total_proceeds": <float>,
      "total_tax": <float>,
      "effective_tax_rate": <float>,
      "year_by_year": [ <yearly breakdown objects> ]
    }
  ],
  "recommended_scenario": "<name of recommended strategy>",
  "recommendation_rationale": "<why this strategy fits the user's profile>",
  "alternative_strategies": [
    {
      "name": "<Exchange Fund | Charitable Giving | Hedging>",
      "description": "<brief description>",
      "applicable": <true|false>,
      "eligibility_note": "<e.g. Requires accredited investor status>"
    }
  ],
  "disclaimers": ["<standard disclaimers>"]
}

>>>>>>> 9b21d26 (E2E working with subagents flow.)
### response_type: "summary"
Use for the final wrap-up after all strategies have been presented.

payload: {
  "phase": "complete",
  "strategies_analyzed": ["<list of strategies that were run>"],
  "key_recommendations": ["<top 2-3 action items>"],
  "next_steps": ["<suggested follow-up actions>"]
}

<<<<<<< HEAD
=======
### response_type: "follow_up"
Use when answering questions after the main analysis is complete.

payload: {
  "topic": "<what the follow-up is about>",
  "references_strategy": "<which strategy this relates to, or null>"
}

>>>>>>> 9b21d26 (E2E working with subagents flow.)
### response_type: "error"
Use when something goes wrong.

payload: {
  "error_code": "<TOOL_FAILURE | MISSING_DATA | INVALID_INPUT>",
  "error_details": "<technical details for logging>",
  "recoverable": <true|false>,
  "suggested_action": "<what the user should do>"
}
"""
