"""
Spreadsheet Ranking Engine — Excel-exact algorithm
====================================================
Reproduces the EXACT ranking logic from the Excel spreadsheet
(Fundamentos Ações - V1.xlsm):

Algorithm:
  1. For each criterion, transform the raw value:
     - "Maior" (higher is better): use raw value; NaN/null → 0
     - "Menor" (lower is better): use 1/value; NaN/null/zero/negative → 0
  2. Rank ALL stocks DESC (method='min') on the transformed value
     → rank 1 = best (highest transformed value)
  3. Apply tie-breaker: rankFinal = rankBase + (rankBase / 10000.0)
  4. Score = SUM of all rankFinal values across active criteria
     (criteria with weight > 1 are summed that many times)
  5. Liquidity penalty: score += 1000 if liquidez <= min_liq
  6. Sort ASC by score (lowest = best)
"""
from __future__ import annotations
import logging
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

LIQ_COL = "liquidezmediadiaria"
DEFAULT_MIN_LIQ = 500_000
LIQ_PENALTY = 1000.0

# (column_name, lower_is_better, weight)
Criterion = Tuple[str, bool, int]

SPREADSHEET_PRESETS: Dict[str, Dict[str, object]] = {

    "magic": {
        "criteria": [
            ("ev_ebit", True, 1),
            ("roic", False, 1),
        ],
    },

    "magic_lucros": {
        "criteria": [
            ("ev_ebit", True, 1),
            ("roic", False, 1),
            ("cagr_lucros", False, 1),
        ],
    },

    "baratas": {
        "criteria": [
            ("ev_ebit", True, 1),
            ("pl", True, 1),
            ("pvp", True, 1),
        ],
    },

    "solidas": {
        "criteria": [
            ("div_pat", True, 1),     # Dív/Patrimônio — lower is better
            ("roe", False, 1),        # ROE — higher is better
            ("margem_liquida", False, 1),  # Margem Líquida — higher is better
        ],
    },

    "mix": {
        "criteria": [
            ("pl", True, 1),          # P/L — lower is better
            ("dy", False, 1),         # DY — higher is better
            ("roe", False, 1),        # ROE — higher is better
        ],
    },

    "dividendos": {
        "criteria": [
            ("dy", False, 3),         # DY — weight 3 (summed 3x)
            ("cagr_lucros", False, 1),
        ],
    },

    "graham": {
        "criteria": [
            ("pl", True, 1),
            ("pvp", True, 1),
        ],
    },

    "greenblatt": {
        "criteria": [
            ("ev_ebit", True, 1),
            ("roic", False, 1),
        ],
    },
}


def _transform(series: pd.Series, lower_is_better: bool) -> pd.Series:
    """
    Transform raw metric values exactly as the Excel spreadsheet does.

    - "Maior" (higher is better, lower_is_better=False):
        valor_transformado = valor (NaN → 0)

    - "Menor" (lower is better, lower_is_better=True):
        valor_transformado = 1 / valor
        if valor is NaN, 0, negative, or division error → 0

    After transformation, ranking is always DESC (highest transformed = rank 1).
    """
    s = pd.to_numeric(series, errors="coerce")

    if lower_is_better:
        # 1/value; invalid → 0
        safe = s.where((s.notna()) & (s > 0), other=np.nan)
        transformed = 1.0 / safe
        transformed = transformed.fillna(0.0)
    else:
        # Direct value; NaN → 0
        transformed = s.fillna(0.0)

    return transformed


def _rank_desc(values: pd.Series) -> pd.Series:
    """
    Rank DESC with method='min' — exactly like Excel RANK(value, range, 0).

    Equal values get the same rank (like Excel RANK).
    Then add tie-breaker: rankFinal = rankBase + (rankBase / 10000.0)
    """
    # rank ascending=False, method='min' matches Excel RANK(..., 0)
    r = values.rank(ascending=False, method="min")
    return r + (r / 10000.0)


def _compute(
    df: pd.DataFrame,
    criteria: List[Criterion],
    min_liq: float,
    strategy: str = "",
) -> pd.DataFrame:
    """
    Compute the spreadsheet score for every stock in the universe.

    Score = SUM(rank_final for each criterion × weight) + liquidity_penalty
    """
    out = df.copy()
    out["_score"] = 0.0
    rank_cols_added = []

    for col, lower, weight in criteria:
        if col not in out.columns:
            logger.warning(
                f"[spreadsheet][{strategy}] column '{col}' NOT in DataFrame — skipped"
            )
            continue

        vals = _transform(out[col], lower)

        ranks = _rank_desc(vals)
        rank_col_name = f"_r_{col}"
        out[rank_col_name] = ranks
        rank_cols_added.append(rank_col_name)

        # Apply weight (e.g., DY weight=3 → sum the rank 3 times)
        out["_score"] += ranks * weight

        logger.debug(
            f"[spreadsheet][{strategy}] criterion '{col}' "
            f"(lower={lower}, weight={weight}): "
            f"non-zero={( vals != 0).sum()}, "
            f"rank range=[{ranks.min():.1f}, {ranks.max():.1f}]"
        )

    # Liquidity penalty: +1000 if liquidity <= min_liq
    if LIQ_COL in out.columns:
        liq = pd.to_numeric(out[LIQ_COL], errors="coerce").fillna(0)
        penalized = (liq <= float(min_liq)).sum()
        out["_liq_penalty"] = 0.0
        out.loc[liq <= float(min_liq), "_liq_penalty"] = LIQ_PENALTY
        out["_score"] += out["_liq_penalty"]
        logger.debug(
            f"[spreadsheet][{strategy}] liquidity penalty applied to "
            f"{penalized} stocks (liq <= {min_liq})"
        )

    return out


def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = DEFAULT_MIN_LIQ,
    top_n: int = 100,
):
    """
    Apply the spreadsheet ranking engine to the full universe.

    Returns (df_ranked[:top_n], caveats_list).
    """
    preset = SPREADSHEET_PRESETS.get(strategy)
    if not preset:
        logger.warning(f"[spreadsheet] unknown strategy '{strategy}'")
        return df_universe.head(top_n), ["Estratégia não encontrada"]

    # Filter to B3 only (matches Excel universe)
    if "market" in df_universe.columns:
        df_universe = df_universe[df_universe["market"] == "BR"].copy()

    logger.info(
        f"[spreadsheet] strategy='{strategy}' | "
        f"universe={len(df_universe)} stocks | min_liq={min_liq}"
    )

    criteria = preset["criteria"]
    df_scored = _compute(df_universe, criteria, min_liq, strategy)

    # Sort by score ASC (lowest score = best) — stable sort preserves input order for ties
    df_ranked = df_scored.sort_values("_score", ascending=True, kind="mergesort")

    # Log top 10 for debugging
    if not df_ranked.empty:
        top10 = df_ranked.head(10)
        rank_cols = [c for c in top10.columns if c.startswith("_r_")]
        log_cols = ["ticker", "_score"] + rank_cols
        available_log_cols = [c for c in log_cols if c in top10.columns]
        logger.info(
            f"[spreadsheet][{strategy}] TOP 10:\n"
            f"{top10[available_log_cols].to_string(index=False)}"
        )

    return df_ranked.head(top_n), []
