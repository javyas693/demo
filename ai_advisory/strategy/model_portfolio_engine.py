"""
Model Portfolio Engine
ai_advisory/strategy/model_portfolio_engine.py

Self-contained engine for model portfolio (frontier-based) backtest simulation.
Mirrors the architecture of StrategyUnwindEngine and AnchorIncomeEngine:
  - __init__ takes all params
  - simulate() runs standalone, returns complete result dict

Can be used:
  - Standalone: ModelPortfolioEngine(...).simulate()
  - Via orchestrator: weights resolved externally, passed as target_weights
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai_advisory.services.portfolio_analytics import run_mp_backtest


class ModelPortfolioEngine:
    """
    Frontier model portfolio backtest engine.

    Owns:
      - Weight resolution (via frontier or direct)
      - Monthly rebalancing simulation
      - Full result dict (summary, time_series, audit_log)

    Does NOT own:
      - Capital allocation decisions (orchestrator)
      - Sell decisions (DecisionService)
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 500_000.0,
        target_weights: Optional[Dict[str, float]] = None,
        risk_score: int = 65,
        model_id: str = "core",
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = float(initial_capital)
        self.risk_score = risk_score
        self.model_id = model_id

        if target_weights is not None:
            self.target_weights = target_weights
        else:
            self.target_weights = self._resolve_weights()

    def _resolve_weights(self) -> Dict[str, float]:
        """
        Resolve frontier weights for the configured risk score.
        Falls back to a balanced proxy if frontier is unavailable.
        """
        try:
            from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
            from ai_advisory.frontier.trade_flow_compat import weights_for_risk_score
            from datetime import date as _date

            store = FileSystemFrontierStore(root="data/frontiers")
            as_of = self.end_date[:10]
            latest = store.get_latest(as_of, self.model_id)
            if latest and store.exists(as_of, latest):
                return weights_for_risk_score(store, as_of, self.model_id, self.risk_score)
        except Exception:
            pass
        # Balanced proxy fallback
        return {"SPY": 0.60, "IEF": 0.30, "BIL": 0.10}

    def simulate(self) -> Dict[str, Any]:
        """
        Run the model portfolio backtest. Returns complete result dict:
          {summary, time_series, audit_log}
        """
        return run_mp_backtest(
            target_weights=self.target_weights,
            initial_capital=self.initial_capital,
            start_date=self.start_date,
            end_date=self.end_date,
        )
