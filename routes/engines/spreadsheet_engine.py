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
            ("ev_ebit", True),
            ("pl", True),
            ("pvp", True),
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
            ("pvp", True),
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
            ("pvp", True),
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


def _compute(df: pd.DataFrame, criteria: List[Criterion], min_liq: float, strategy: str = ""):
    out = df.copy()
    out["_score"] = 0.0
    rank_cols_added = []

    for col, lower in criteria:
        if col not in out.columns:
            logger.warning(f"[spreadsheet][{strategy}] column '{col}' NOT in DataFrame — skipped")
            continue
        vals = _transform(out[col], lower)
        if vals.isna().all():
            logger.warning(f"[spreadsheet][{strategy}] column '{col}' is ALL NaN after transform — skipped")
            continue

        ranks = _rank(vals)
        rank_col_name = f"_r_{col}"
        out[rank_col_name] = ranks
        rank_cols_added.append(rank_col_name)
        out["_score"] += ranks
        logger.debug(f"[spreadsheet][{strategy}] criterion '{col}' (lower={lower}): "
                      f"non-null={vals.notna().sum()}, rank range=[{ranks.min():.1f}, {ranks.max():.1f}]")

    if LIQ_COL in out.columns:
        liq = pd.to_numeric(out[LIQ_COL], errors="coerce").fillna(0)
        penalized = (liq <= float(min_liq)).sum()
        out.loc[liq <= float(min_liq), "_score"] += LIQ_PENALTY
        logger.debug(f"[spreadsheet][{strategy}] liquidity penalty applied to {penalized} stocks (liq <= {min_liq})")

    return out


def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = DEFAULT_MIN_LIQ,
    top_n: int = 100,
):
    preset = SPREADSHEET_PRESETS.get(strategy)
    if not preset:
        logger.warning(f"[spreadsheet] unknown strategy '{strategy}'")
        return df_universe.head(top_n), ["Estratégia não encontrada"]

    # 🔥 PATCH CRÍTICO: FILTRAR SOMENTE B3 IGUAL PLANILHA
    if "market" in df_universe.columns:
        df_universe = df_universe[df_universe["market"] == "BR"].copy()

    logger.info(f"[spreadsheet] strategy='{strategy}' | universe={len(df_universe)} stocks | min_liq={min_liq}")

    criteria = preset["criteria"]
    df_scored = _compute(df_universe, criteria, min_liq, strategy)

    df_ranked = df_scored.sort_values("_score", ascending=True, kind="mergesort")

    # Log top 10 for debugging
    if not df_ranked.empty:
        top10 = df_ranked.head(10)
        rank_cols = [c for c in top10.columns if c.startswith("_r_")]
        log_cols = ["ticker", "_score"] + rank_cols
        available_log_cols = [c for c in log_cols if c in top10.columns]
        logger.info(f"[spreadsheet][{strategy}] TOP 10:\n{top10[available_log_cols].to_string(index=False)}")

    return df_ranked.head(top_n), []
