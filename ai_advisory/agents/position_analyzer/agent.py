"""
Position Unwind Analyzer — AgentTool (single-shot analysis)

ROLE IN ARCHITECTURE:
  - Wrapped in AgentTool by the orchestrator
  - Called AFTER position_gatherer has collected all lot data into session state
  - Reads position data and risk profile from session state
  - Uses FunctionTools (capital gains calculator, staged selldown modeler)
    to run quantitative scenarios
  - Returns a complete analysis with multiple unwind strategies
  - The orchestrator stays in control and presents results to the user

WHY AN AGENTTOOL (not sub-agent):
  - Does NOT need to talk to the user — it has all data from state
  - The orchestrator needs to retain control to potentially invoke
    other strategy agents (portfolio optimizer, income planner) and
    merge all results before responding
  - Runs deterministic analysis with LLM reasoning for interpretation
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tools.capital_gains_tool import calculate_capital_gains, model_staged_selldown


# ── Agent Definition ─────────────────────────────────────────────────────────

POSITION_ANALYZER_INSTRUCTION = """
You are a quantitative tax-efficient portfolio transition analyst. You analyze
concentrated stock positions and recommend unwind strategies.

## INPUT (from session state — injected into your context)

You will receive:
- `position_ticker`: The stock ticker symbol
- `position_lots`: List of tax lots with shares, cost_basis, acquisition_date
- `risk_profile_label`: The user's risk profile (Conservative → Aggressive)
- `risk_score_final`: Numeric risk score (0.0 = aggressive, 0.5 = conservative)
- `user_name`: The user's name
- `user_goals`: Their stated investment goals

## YOUR ANALYSIS PROCESS

1. **Calculate current tax exposure**: Call `calculate_capital_gains` with the
   lots and an assumed current price. Use the lot data to understand the
   gain/loss position of each lot.

   NOTE: Since you may not have a live market data feed, use a reasonable
   current price or note that the price should be updated. For the analysis,
   you can assume a price or the orchestrator will provide one.

2. **Model unwind scenarios**: Call `model_staged_selldown` with different
   parameters based on the user's risk profile:

   - **Conservative profile** → Slow unwind: 10% per year over 7-10 years
   - **Moderate profile** → Balanced: 15-20% per year over 5-7 years
   - **Aggressive profile** → Fast unwind: 25-33% per year over 3-4 years

   Run at least 2-3 scenarios to give the user options.

3. **Consider alternative strategies** (describe qualitatively):
   - **Exchange Fund**: If total position > $1M, mention pooled diversification
     vehicles that defer capital gains (requires accredited investor status)
   - **Charitable Giving**: If they have philanthropic goals, donating appreciated
     shares avoids capital gains entirely
   - **Hedging**: Protective puts or collars to limit downside while holding

4. **Produce your recommendation**: Based on the risk profile and tax analysis,
   recommend one primary strategy. Explain the trade-offs clearly.

## OUTPUT FORMAT

Structure your response as a clear analysis with:
- Executive summary (2-3 sentences)
- Current tax exposure summary
- Scenario comparison table
- Recommended strategy with rationale
- Alternative strategies worth considering
- Key assumptions and caveats

## IMPORTANT RULES

- Never recommend a strategy without showing the tax impact
- Always caveat that this is educational, not personalized tax advice
- If lots have mixed holding periods, highlight the tax efficiency of
  selling short-term lots last (let them convert to long-term)
- Be specific with numbers — users want to see dollar amounts
"""

position_analyzer_agent = Agent(
    name="position_unwind_analyzer",
    model="gemini-2.5-flash",
    description=(
        "Analyzes concentrated stock positions and produces tax-efficient "
        "unwind strategies. Reads position data and risk profile from session "
        "state. Runs capital gains calculations and staged selldown models. "
        "Returns a complete analysis with multiple scenarios and a recommendation. "
        "Call this agent with a request like: 'Analyze the concentrated position "
        "in state. Ticker: {position_ticker}, Lots: {position_lots}, "
        "Risk profile: {risk_profile_label}, Current price: {price}'"
    ),
    instruction=POSITION_ANALYZER_INSTRUCTION,
    tools=[
        FunctionTool(calculate_capital_gains),
        FunctionTool(model_staged_selldown),
    ],
)
