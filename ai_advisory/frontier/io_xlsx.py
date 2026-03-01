from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


def _parse_pct(x) -> float:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return float("nan")
    if isinstance(x, (int, float)):
        # assume already decimal (0.05) if <= 1.5, else percent (5)
        v = float(x)
        return v if abs(v) <= 1.5 else v / 100.0
    s = str(x).strip()
    if s.endswith("%"):
        return float(s[:-1].strip()) / 100.0
    # fall back: treat as decimal if <=1.5 else percent
    v = float(s)
    return v if abs(v) <= 1.5 else v / 100.0


def load_allocation_constraints(
    xlsx_path: str,
    sheet_name: Optional[str] = None,
    date_col: Optional[str] = None,  # unused, kept for symmetry
    ticker_col: str = "Ticker",
    asset_class_col: str = "Asset Class",
    sub_asset_class_col: str = "Sub-Asset Class",
    name_col: str = "Name",
    expense_ratio_col: str = "Expense Ratio",
    yield_col: str = "Yield",
    min_weight_col: str = "Min Weight",
    max_weight_col: str = "Max Weight",
) -> dict:
    """
    Robust loader:
    - If sheet_name is None, search all sheets.
    - Auto-detect header row by scanning first ~30 rows for a row containing ticker_col.
    """
    xl = pd.ExcelFile(xlsx_path)

    candidate_sheets = [sheet_name] if sheet_name else xl.sheet_names

    last_err = None
    for sh in candidate_sheets:
        try:
            raw = pd.read_excel(xlsx_path, sheet_name=sh, header=None)
            header_row = None

            # find header row where one cell equals "Ticker" (case/space-insensitive)
            target = ticker_col.strip().lower()
            for i in range(min(30, len(raw))):
                row = raw.iloc[i].astype(str).str.strip().str.lower()
                if any(cell == target for cell in row.values):
                    header_row = i
                    break

            if header_row is None:
                # try common variants
                variants = {"symbol", "ticker symbol", "tickers"}
                for i in range(min(30, len(raw))):
                    row = raw.iloc[i].astype(str).str.strip().str.lower()
                    if any(cell in variants for cell in row.values):
                        header_row = i
                        ticker_col = "Symbol"  # we'll remap below after real read
                        break

            if header_row is None:
                continue  # try next sheet

            df = pd.read_excel(xlsx_path, sheet_name=sh, header=header_row)
            # normalize column names
            df.columns = [str(c).strip() for c in df.columns]

            # remap if ticker header is a variant
            if "Ticker" not in df.columns:
                for c in df.columns:
                    if str(c).strip().lower() in {"symbol", "ticker symbol", "tickers"}:
                        df = df.rename(columns={c: "Ticker"})
                        break

            if "Ticker" not in df.columns:
                continue

            df = df[df["Ticker"].notna()].copy()
            df["Ticker"] = df["Ticker"].astype(str).str.strip()

            assets: List[str] = df["Ticker"].tolist()

            bounds: Dict[str, Tuple[float, float]] = {}
            asset_class_map: Dict[str, str] = {}
            sub_asset_class_map: Dict[str, str] = {}
            name_map: Dict[str, str] = {}
            yield_map: Dict[str, float] = {}
            expense_ratio_map: Dict[str, float] = {}

            for _, r in df.iterrows():
                t = str(r["Ticker"]).strip()

                mn = _parse_pct(r.get(min_weight_col))
                mx = _parse_pct(r.get(max_weight_col))
                if pd.isna(mn): mn = 0.0
                if pd.isna(mx): mx = 1.0
                bounds[t] = (float(mn), float(mx))

                if asset_class_col in df.columns and pd.notna(r.get(asset_class_col)):
                    asset_class_map[t] = str(r.get(asset_class_col)).strip()
                if sub_asset_class_col in df.columns and pd.notna(r.get(sub_asset_class_col)):
                    sub_asset_class_map[t] = str(r.get(sub_asset_class_col)).strip()
                if name_col in df.columns and pd.notna(r.get(name_col)):
                    name_map[t] = str(r.get(name_col)).strip()

                if yield_col in df.columns:
                    y = _parse_pct(r.get(yield_col))
                    yield_map[t] = 0.0 if pd.isna(y) else float(y)
                if expense_ratio_col in df.columns:
                    e = _parse_pct(r.get(expense_ratio_col))
                    expense_ratio_map[t] = 0.0 if pd.isna(e) else float(e)

            return {
                "sheet_used": sh,
                "header_row": header_row,
                "assets": assets,
                "bounds": bounds,
                "asset_class_map": asset_class_map,
                "sub_asset_class_map": sub_asset_class_map,
                "name_map": name_map,
                "yield_map": yield_map,
                "expense_ratio_map": expense_ratio_map,
            }

        except Exception as e:
            last_err = e
            continue

    raise KeyError(f"Could not find a sheet/header with a Ticker column in {xlsx_path}. Last error: {last_err}")

def load_prices_matrix(
    xlsx_path: str,
    sheet_name: Optional[str] = None,
    date_col: str = "Date",
) -> pd.DataFrame:
    """
    Robust loader:
    - If sheet_name is None, reads the first sheet (or the sheet containing date_col).
    - Ensures numeric columns and datetime index when date_col exists.
    """
    xl = pd.ExcelFile(xlsx_path)

    if sheet_name is None:
        # Prefer a sheet that contains the date_col in its header
        chosen = None
        for sh in xl.sheet_names:
            head = pd.read_excel(xlsx_path, sheet_name=sh, nrows=5)
            cols = [str(c).strip() for c in head.columns]
            if date_col in cols:
                chosen = sh
                break
        sheet_name = chosen if chosen else xl.sheet_names[0]

    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)

    # normalize columns
    df.columns = [str(c).strip() for c in df.columns]

    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)

    # ensure numeric
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

def load_allocation_workbook(xlsx_path: str) -> dict:
    """
    Loads both allocation sheets:
      - 'Asset Class' (top-level)
      - 'Sub-Assets'  (sub-asset universe)
    Returns dict with keys: asset_class, sub_assets
    """
    asset_class = load_allocation_constraints(xlsx_path, sheet_name="Asset Class")
    sub_assets = load_allocation_constraints(xlsx_path, sheet_name="Sub-Assets")
    return {"asset_class": asset_class, "sub_assets": sub_assets}