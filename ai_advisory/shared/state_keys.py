"""
Centralized session state keys.

Every agent reads/writes state through these constants.
Adding a new strategy? Add its keys here first — this is the contract
between data-gathering sub-agents and analysis AgentTools.
"""


# ── Risk Assessment ──────────────────────────────────────────────────────────
RISK_ASSESSMENT_COMPLETE = "risk_assessment_complete"        # bool
RISK_SCORES_RAW = "risk_scores_raw"                          # list[float] — per-question scores
RISK_SCORE_FINAL = "risk_score_final"                        # float — composite 0.0–1.0
RISK_PROFILE_LABEL = "risk_profile_label"                    # str — e.g. "Moderate"
RISK_QUESTIONS_ANSWERED = "risk_questions_answered"           # int — progress tracker

# ── User Profile ─────────────────────────────────────────────────────────────
USER_NAME = "user_name"                                      # str
USER_GOALS = "user_goals"                                    # str — raw user statement

# ── Concentrated Position ────────────────────────────────────────────────────
POSITION_DATA_COMPLETE = "position_data_complete"            # bool
POSITION_LOTS = "position_lots"                              # list[dict] — structured lot data
# Each lot: {"ticker": str, "shares": int, "cost_basis": float,
#             "acquisition_date": str, "lot_id": str}
POSITION_TICKER = "position_ticker"                          # str — primary ticker symbol
POSITION_CURRENT_PRICE = "position_current_price"            # float — fetched market price
HAS_CONCENTRATED_POSITION = "has_concentrated_position"      # bool
STARTING_CASH = "starting_cash"                              # float — user's starting cash

# ── Position Analysis Results ────────────────────────────────────────────────
UNWIND_ANALYSIS_COMPLETE = "unwind_analysis_complete"        # bool
UNWIND_STRATEGY = "unwind_strategy"                          # dict — full analysis output

# ── Orchestrator Control ─────────────────────────────────────────────────────
CURRENT_PHASE = "current_phase"                              # str — tracks workflow stage
# Phase values: "greeting", "risk_assessment", "position_gathering",
#               "position_analysis", "complete"

# ── Future Strategy Slots (add new strategies here) ──────────────────────────
# INCOME_STRATEGY_DATA = "income_strategy_data"
# INCOME_STRATEGY_RESULT = "income_strategy_result"
# GROWTH_STRATEGY_DATA = "growth_strategy_data"
# GROWTH_STRATEGY_RESULT = "growth_strategy_result"
