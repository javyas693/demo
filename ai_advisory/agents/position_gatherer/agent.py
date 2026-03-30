"""
Position Data Gatherer — Sub-agent (multi-turn conversation)
Outputs strict JSON envelope on every response.

ROLE IN ARCHITECTURE:
  - Orchestrator transfers here after risk assessment is complete
  - Asks the user about their concentrated stock position(s)
  - Collects: ticker, number of lots, shares per lot, cost basis, acquisition dates
  - Writes structured lot data to session state as clean dicts
  - Escalates back to orchestrator when all data is collected
  - The orchestrator then invokes the position_analyzer AgentTool

WHY A SUB-AGENT (not AgentTool):
  - Users rarely know their exact lot details upfront
  - Needs to ask follow-ups: "Do you have multiple lots?" / "When did you buy?"
  - Must handle messy input: "I bought some in 2018, maybe 500 shares at around $45"
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.adk.models.anthropic_llm import AnthropicLlm

from ai_advisory.shared.state_keys import (
    POSITION_DATA_COMPLETE, POSITION_LOTS, POSITION_TICKER,
    HAS_CONCENTRATED_POSITION, CURRENT_PHASE, STARTING_CASH,
    HORIZON_YEARS, TLH_INVENTORY,
)
from ai_advisory.shared.response_schema import (
    RESPONSE_FORMAT_INSTRUCTION,
    POSITION_GATHERER_RESPONSE_TYPES,
)

# ── Tools ────────────────────────────────────────────────────────────────────

def save_position_data_and_escalate(
    ticker: str,
    lots: list[dict],
    has_concentrated_position: bool,
    starting_cash: float,
    tool_context: ToolContext,
    horizon_years: int = 5,
    tlh_inventory: float = 0.0,
) -> dict:
    """
    Saves the collected concentrated position data to session state
    and escalates back to the orchestrator.

    Args:
        ticker: The primary stock ticker symbol (e.g., "AAPL").
        lots: List of tax lot dicts. Each lot must have:
              - lot_id (str): unique identifier like "lot_1"
              - ticker (str): stock symbol
              - shares (int): number of shares
              - cost_basis (float): per-share cost basis
              - acquisition_date (str): in YYYY-MM-DD format
        has_concentrated_position: True if user confirmed a concentrated position.
        starting_cash: The amount of cash the user has in their brokerage account.
        horizon_years: How many years the user is planning for (e.g. 5).
        tlh_inventory: Existing tax loss balance in dollars (0.0 if none).
    """
    required_fields = {"lot_id", "ticker", "shares", "cost_basis", "acquisition_date"}
    for i, lot in enumerate(lots):
        missing = required_fields - set(lot.keys())
        if missing:
            return {
                "status": "error",
                "error": f"Lot {i+1} is missing fields: {missing}",
            }

    tool_context.state[POSITION_TICKER] = ticker
    tool_context.state[POSITION_LOTS] = lots
    tool_context.state[HAS_CONCENTRATED_POSITION] = has_concentrated_position
    tool_context.state[STARTING_CASH] = starting_cash
    tool_context.state[HORIZON_YEARS] = int(horizon_years)
    tool_context.state[TLH_INVENTORY] = float(tlh_inventory)
    tool_context.state[POSITION_DATA_COMPLETE] = True
    tool_context.state[CURRENT_PHASE] = "position_data_complete"

    tool_context.actions.escalate = True

    return {
        "status": "success",
        "message": (
            f"Saved {len(lots)} lot(s) for {ticker}, "
            f"cash ${starting_cash:,.2f}, "
            f"horizon {horizon_years} years, "
            f"TLH ${tlh_inventory:,.2f}. Escalating to orchestrator."
        ),
        "lots_saved": len(lots),
    }


def save_no_position_and_escalate(tool_context: ToolContext) -> dict:
    """
    Called when the user indicates they do NOT have a concentrated position.
    Saves this fact to state and escalates back to orchestrator.
    """
    tool_context.state[HAS_CONCENTRATED_POSITION] = False
    tool_context.state[POSITION_DATA_COMPLETE] = True
    tool_context.state[CURRENT_PHASE] = "position_data_complete"
    tool_context.actions.escalate = True

    return {
        "status": "success",
        "message": "No concentrated position. Escalating to orchestrator.",
    }


# ── Agent Instruction ────────────────────────────────────────────────────────

POSITION_GATHERER_INSTRUCTION = f"""
You are a patient, detail-oriented specialist who helps users document their
concentrated stock positions, cost basis and starting cash. The user's name is available in your conversation
context — use it to personalize the conversation. Do NOT greet the user as this is part of an ongoing conversation.

{RESPONSE_FORMAT_INSTRUCTION}

{POSITION_GATHERER_RESPONSE_TYPES}

## YOUR CONVERSATION FLOW

**Step 1 — Ask if they have a concentrated position:**
Explain what a concentrated position is (a single stock making up a large
portion of their portfolio, typically 10%+ in one security). Ask if they have one.

response_type: "position_question"
payload.progress.status: "asking_if_position"

If the user says NO:
  → Call `save_no_position_and_escalate`
  → response_type: "no_position"

If YES → continue to step 2.

**Step 2 — Collect the ticker symbol:**
"Which stock is it?" Accept common formats (e.g., "Apple", "AAPL").
Normalize to the uppercase ticker symbol.

response_type: "position_question"
payload.progress.status: "collecting_ticker"

**Step 3 — Collect lot details:**
Ask about their purchase history. Probe for multiple lots:
  - "When did you first buy your <ticker> shares?"
  - "How many shares did you buy, and roughly at what price?"
  - "Did you buy more shares at any other time?"

For each lot, collect: shares, cost basis (per share), acquisition date.
If the user gives approximate dates ("early 2018"), use "2018-03-01".
If unsure about exact prices, help estimate: "No worries, a rough estimate works."

response_type: "position_question"
payload.progress.status: "collecting_lots"
Include collected_so_far with all lots gathered so far.

**Step 4 — Confirm the data:**
Summarize back what you collected in agent_message:
"So I have: 500 shares bought at $45 in June 2018, 200 shares at $90 in March 2021.
Does that look right?"

response_type: "position_question"
payload.progress.status: "confirming"

**Step 5 — Collect starting cash:**
Ask the user how much cash they have in their brokerage account.

response_type: "position_question"
payload.progress.status: "collecting_starting_cash"

**Step 6 — Collect investment horizon:**
Ask how many years they are planning for.
"Are you thinking about a 5-year plan, 10 years, longer?"
Accept natural answers ("about 7 years", "until retirement in 10 years") and round to
the nearest whole number.

response_type: "position_question"
payload.progress.status: "collecting_horizon"

**Step 7 — Collect existing tax loss inventory:**
Ask if they have any existing tax losses already realized in this account.
"Do you have any existing tax losses carried forward in this account? If not, no worries — we'll start fresh."
If they say no or are unsure, use 0.

response_type: "position_question"
payload.progress.status: "collecting_tlh"

**Step 8 — Save and escalate:**
Call `save_position_data_and_escalate` with all collected data.
Assign lot_ids as "lot_1", "lot_2", etc.

response_type: "position_confirmed"
In agent_message, tell the user their position data is saved and the advisor
will now analyze their options.

## CRITICAL RULES

- Be patient with imprecise answers. Users often don't remember exact details.
- For RSUs, note cost basis is typically the FMV on the vesting date.
- Always confirm before saving — data accuracy matters for tax calculations.
- Output ONLY the JSON object. No markdown fences, no preamble, no trailing text.
- The agent_message field is what the user sees — keep it warm and conversational.
"""


position_gatherer_agent = Agent(
    name="position_gatherer",
    model="gemini-2.5-flash",#AnthropicLlm(model="claude-sonnet-4-6", max_tokens=8192, temperature=0),
    description=(
        "Collects detailed information about a user's concentrated stock position "
        "through multi-turn conversation. Gathers ticker, lot details (shares, "
        "cost basis, acquisition dates). Responds in strict JSON envelope format."
    ),
    instruction=POSITION_GATHERER_INSTRUCTION,
    tools=[
        FunctionTool(save_position_data_and_escalate),
        FunctionTool(save_no_position_and_escalate),
    ],
)
