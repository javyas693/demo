from __future__ import annotations
from pathlib import Path
from typing import Optional, Union

from ai_advisory.risk.risk_engine_simplified import (
    load_simplified_questionnaire,
    score_simplified_1_to_100,
)
from .api_models import RiskScoreRequest, RiskScoreResponse


class RiskService:
    def __init__(self, questionnaire_xlsx: Union[str, Path]):
        self._q = load_simplified_questionnaire(questionnaire_xlsx)

    def score(self, req: RiskScoreRequest) -> RiskScoreResponse:
        rp = score_simplified_1_to_100(
            answers_by_group=req.answers_by_group,
            questionnaire=self._q,
            strict=req.strict,
        )
        return RiskScoreResponse(
            risk_score=rp.risk_score,
            confidence=rp.confidence,
            drivers=rp.drivers,
        )