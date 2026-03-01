from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import pandas as pd


class RiskEngineError(Exception):
    pass


@dataclass(frozen=True)
class RiskProfile:
    """
    risk_score: 1..100 (higher = more risk capacity/willingness per your simplified sheet)
    confidence: 0..1 (coverage-based for MVP)
    drivers: explainability payload
    """
    risk_score: int
    confidence: float
    drivers: Dict[str, Any]


@dataclass(frozen=True)
class AnswerOption:
    option_id: int
    label: str
    penalty: float  # the sheet's "Risk Score" (fractional penalty)


@dataclass(frozen=True)
class QuestionGroup:
    name: str
    question: str
    options: Tuple[AnswerOption, ...]


# -----------------------------
# Loader (Simplified Excel)
# -----------------------------

def load_simplified_questionnaire(xlsx_path: Union[str, Path]) -> Tuple[QuestionGroup, ...]:
    """
    Parse 'Simplified Risk Profile Questionarre Algo.xlsx' (sheet 'Questions').

    The sheet is laid out like:
      Row: [GroupName] [QuestionText] ... [Risk Score header]
      Rows: [1] [Option Label] ... [Risk Score value]
      Rows: [2] [Option Label] ... [Risk Score value]
      ...
      Next group...

    This parser is intentionally tolerant of 'Unnamed:*' columns.
    """
    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    df = pd.read_excel(path, sheet_name="Questions")

    # Find the column that contains the numeric penalties.
    # In your preview, it appeared under 'Unnamed: 4' with label 'Risk Score' in header row.
    penalty_col = _find_penalty_column(df)

    groups: List[QuestionGroup] = []
    current_name: Optional[str] = None
    current_q: Optional[str] = None
    current_opts: List[AnswerOption] = []

    def flush():
        nonlocal current_name, current_q, current_opts
        if current_name and current_q and current_opts:
            # sort by option_id
            opts = tuple(sorted(current_opts, key=lambda o: o.option_id))
            groups.append(QuestionGroup(name=current_name, question=current_q, options=opts))
        current_name = None
        current_q = None
        current_opts = []

    # We treat first column as either group header (string) or option id (number)
    col0 = df.columns[0]
    col1 = df.columns[1] if len(df.columns) > 1 else None

    for _, row in df.iterrows():
        a0 = row.get(col0)
        a1 = row.get(col1) if col1 is not None else None
        pen = row.get(penalty_col)

        # Skip totally empty lines
        if _is_empty(a0) and _is_empty(a1) and _is_empty(pen):
            continue

        # Detect group header: first cell is a non-numeric string and second cell is question text
        if _is_group_header(a0, a1):
            flush()
            current_name = str(a0).strip()
            current_q = str(a1).strip()
            continue

        # Detect option row: first cell is numeric option id and second cell is option label
        opt_id = _as_int(a0)
        if opt_id is not None and not _is_empty(a1):
            if current_name is None or current_q is None:
                # option before any header -> ignore
                continue

            penalty = _as_float(pen)
            if penalty is None:
                raise RiskEngineError(
                    f"Missing penalty score for group '{current_name}' option '{a1}' (option_id={opt_id})."
                )

            current_opts.append(
                AnswerOption(option_id=opt_id, label=str(a1).strip(), penalty=float(penalty))
            )
            continue

        # Anything else: ignore (notes/formula/footer)
        continue

    flush()

    if not groups:
        raise RiskEngineError("No question groups parsed from simplified questionnaire.")

    return tuple(groups)


def _find_penalty_column(df: pd.DataFrame) -> str:
    """
    Heuristic to locate penalty column.
    Preference:
      1) a column containing numeric values in most option rows
      2) header row containing 'Risk Score' somewhere nearby
    """
    # First try: exact header match
    for c in df.columns:
        if isinstance(c, str) and c.strip().lower() == "risk score":
            return c

    # Next: find a column where many rows are numeric and within a reasonable range (0..1)
    best_col = None
    best_count = -1

    for c in df.columns:
        numeric = pd.to_numeric(df[c], errors="coerce")
        # count values between 0 and 1 inclusive
        count = int(((numeric >= 0.0) & (numeric <= 1.0)).sum())
        if count > best_count:
            best_count = count
            best_col = c

    if best_col is None or best_count <= 0:
        raise RiskEngineError("Could not detect penalty (Risk Score) column in simplified sheet.")

    return best_col


def _is_empty(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    if isinstance(x, str) and not x.strip():
        return True
    return False


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        # numeric strings allowed
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            return int(float(s))
        return int(float(x))
    except Exception:
        return None


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            return float(s)
        return float(x)
    except Exception:
        return None


def _is_group_header(a0: Any, a1: Any) -> bool:
    """
    Heuristic: group name is a non-empty string and not numeric; question is non-empty string.
    """
    if _is_empty(a0) or _is_empty(a1):
        return False
    # a0 should NOT be numeric
    if _as_int(a0) is not None:
        return False
    # a1 should be string-ish
    return True


# -----------------------------
# Scoring
# -----------------------------

def score_simplified_1_to_100(
    *,
    answers_by_group: Mapping[str, Union[int, str]],
    questionnaire: Tuple[QuestionGroup, ...],
    strict: bool = False,
) -> RiskProfile:
    """
    Compute risk score using the Simplified sheet formula:
      final = 100 - 100 * sum(penalties_per_group)

    answers_by_group maps group name -> selected option_id (int) OR option label (str).

    strict=False:
      - missing groups are allowed; confidence reflects coverage.
      - score uses only answered groups (scaled by answered proportion) for MVP stability.

    strict=True:
      - all groups must be answered (or raises).
    """
    groups = {g.name: g for g in questionnaire}

    required = list(groups.keys())
    missing = [gn for gn in required if gn not in answers_by_group]

    if strict and missing:
        raise RiskEngineError(f"Missing answers for groups: {', '.join(missing)}")

    penalties: Dict[str, float] = {}
    picked: Dict[str, Dict[str, Any]] = {}

    for gn, g in groups.items():
        if gn not in answers_by_group:
            continue

        sel = answers_by_group[gn]
        opt = _resolve_option(g, sel)
        penalties[gn] = float(opt.penalty)
        picked[gn] = {
            "question": g.question,
            "selected_option_id": opt.option_id,
            "selected_label": opt.label,
            "penalty": opt.penalty,
        }

    answered = len(penalties)
    total = len(groups)

    if answered == 0:
        return RiskProfile(
            risk_score=50,
            confidence=0.0,
            drivers={
                "note": "No answers provided; returning neutral 50 for MVP.",
                "missing_groups": required,
            },
        )

    # MVP scoring choice:
    # - If user answers subset, scale penalty sum by (total/answered) so score remains comparable.
    #   (Otherwise partial completion would bias score higher.)
    penalty_sum = sum(penalties.values())
    penalty_sum_scaled = penalty_sum * (total / answered)

    raw = 100.0 - 100.0 * penalty_sum_scaled
    # Clamp to 1..100
    risk_score = int(round(max(1.0, min(100.0, raw))))

    confidence = answered / total

    drivers = {
        "formula": "score = 100 - 100*(sum penalties)  [scaled if partial completion]",
        "answered_groups": answered,
        "total_groups": total,
        "confidence": confidence,
        "penalty_sum": penalty_sum,
        "penalty_sum_scaled": penalty_sum_scaled,
        "group_details": picked,
        "missing_groups": missing,
    }

    return RiskProfile(risk_score=risk_score, confidence=float(confidence), drivers=drivers)


def _resolve_option(group: QuestionGroup, selection: Union[int, str]) -> AnswerOption:
    """
    selection can be option_id (int) or option label (str).
    """
    if isinstance(selection, int):
        for o in group.options:
            if o.option_id == selection:
                return o
        raise RiskEngineError(f"Invalid option_id={selection} for group '{group.name}'")

    if isinstance(selection, str):
        s = selection.strip().lower()
        # Try exact label match
        for o in group.options:
            if o.label.strip().lower() == s:
                return o
        # Try label contains (tolerant)
        for o in group.options:
            if s and s in o.label.strip().lower():
                return o
        raise RiskEngineError(f"Invalid option label='{selection}' for group '{group.name}'")

    raise RiskEngineError(f"Unsupported selection type for group '{group.name}': {type(selection)}")


# -----------------------------
# Convenience helpers
# -----------------------------

def questionnaire_to_prompt(questionnaire: Tuple[QuestionGroup, ...]) -> str:
    """
    Useful for printing / chatbot system prompt construction.
    """
    lines: List[str] = []
    for g in questionnaire:
        lines.append(f"[{g.name}] {g.question}")
        for o in g.options:
            lines.append(f"  {o.option_id}. {o.label}  (penalty={o.penalty})")
        lines.append("")
    return "\n".join(lines)