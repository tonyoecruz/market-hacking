from __future__ import annotations
import logging
from typing import Dict, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

LIQ_COL = "liquidezmediadiaria"
DEFAULT_MIN_LIQ = 500_000
LIQ_PENALTY = 1000.0

Criterion = Tuple[str, bool]

SPREADSHEET_PRESETS: Dict[str, Dict[str, object]] = {

    "magic": {
        "criteria": [
            ("ev_ebit", True),
            ("roic", False),
        ],
    },

    "magic_lucros": {
        "criteria": [
            ("ev_ebit", True),
            ("roic", False),
            ("cagr_lucros", False),
        ],
    },

    "baratas": {
        "criteria": [
            ("queda_do_maximo", False),
            ("pl", True),
            ("pvp", False),
        ],
    },

    "solidas": {
        "criteria": [
            ("div_pat", True),
            ("roe", False),
            ("cagr_lucros", False),
        ],
    },

    "mix": {
        "criteria": [
            ("pl", True),
            ("pvp", False),
            ("roe", False),
            ("roa", False),
            ("cagr_lucros", False),
        ],
    },

    "dividendos": {
        "criteria": [
            ("dy", False),
            ("cagr_lucros", False),
        ],
    },

    "graham": {
        "criteria": [
            ("pl", True),
            ("pvp", False),
        ],
    },

    "greenblatt": {
        "criteria": [
            ("ev_ebit", True),
            ("roic", False),
        ],
    },
}


def _transform(series: pd.Series, lower: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if lower:
        s = s.where(s > 0, pd.NA)
        return 1.0 / s.astype("float64")
    return s.astype("float64")


def _rank(values: pd.Series) -> pd.Series:
    r = values.rank(ascending=False, method="min", na_option="bottom")
    return r + (r / 10000.0)


def _compute(df: pd.DataFrame, criteria: List[Criterion], min_liq: float):
    out = df.copy()
    out["_score"] = 0.0

    for col, lower in criteria:
        if col not in out.columns:
            continue
        vals = _transform(out[col], lower)
        if vals.isna().all():
            continue
        out["_score"] += _rank(vals)

    if LIQ_COL in out.columns:
        liq = pd.to_numeric(out[LIQ_COL], errors="coerce").fillna(0)
        out.loc[liq <= float(min_liq), "_score"] += LIQ_PENALTY

    return out


def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = DEFAULT_MIN_LIQ,
    top_n: int = 100,
):
    preset = SPREADSHEET_PRESETS.get(strategy)
    if not preset:
        return df_universe.head(top_n), ["Estratégia não encontrada"]

    # 🔥 PATCH CRÍTICO: FILTRAR SOMENTE B3 IGUAL PLANILHA
    if "market" in df_universe.columns:
        df_universe = df_universe[df_universe["market"] == "BR"].copy()

    criteria = preset["criteria"]
    df_scored = _compute(df_universe, criteria, min_liq)

    df_ranked = df_scored.sort_values("_score", ascending=True, kind="mergesort")

    return df_ranked.head(top_n), []