from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException

app = FastAPI(title="AI-Advisory API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
QUESTIONNAIRE_PATH = BASE_DIR / "Simplified Risk Profile Questionarre Algo.xlsx"
STORE_ROOT = BASE_DIR / "data" / "frontiers"


@app.get("/health")
def health():
    return {
        "ok": True,
        "questionnaire_exists": QUESTIONNAIRE_PATH.exists(),
        "questionnaire_path": str(QUESTIONNAIRE_PATH),
        "store_root_exists": STORE_ROOT.exists(),
        "store_root": str(STORE_ROOT),
    }


@app.post("/risk/score")
def risk_score(payload: dict):
    """
    payload:
      {
        "answers_by_group": { "Group Name": 1 or "label", ... },
        "strict": false
      }
    """
    try:
        from ai_advisory.risk.risk_engine_simplified import (
            load_simplified_questionnaire,
            score_simplified_1_to_100,
        )

        answers = payload.get("answers_by_group", {})
        strict = bool(payload.get("strict", False))

        q = load_simplified_questionnaire(QUESTIONNAIRE_PATH)
        rp = score_simplified_1_to_100(
            answers_by_group=answers,
            questionnaire=q,
            strict=strict,
        )
        return {
            "risk_score": rp.risk_score,
            "confidence": rp.confidence,
            "drivers": rp.drivers,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))