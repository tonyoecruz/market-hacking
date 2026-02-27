"""
Spreadsheet Ranking Engine — Excel-exact algorithm V3.0
========================================================
Reproduces the EXACT ranking logic from the Excel spreadsheet
(Fundamentos Ações - V1.xlsm).

Algorithm:
  1. For each criterion, transform the raw value:
     - "Maior" (higher is better): use raw value; NaN/null → 0
     - "Menor" (lower is better): use 1/value; NaN/null/zero/negative → 0
  2. Rank ALL stocks DESC (method='min') on the transformed value
     → rank 1 = best (highest transformed value)
  3. Apply tie-breaker: rankFinal = rankBase + (rankBase / 10000.0)
  4. Score = SUM of all rankFinal values across active criteria
     (criteria with weight > 1 are summed that many times)
  5. Liquidity filter: EXCLUDE stocks with liquidez < min_liq (matches Excel)
  6. Sort ASC by score (lowest = best)
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

LIQ_COL = "liquidezmediadiaria"
DEFAULT_MIN_LIQ = 500_000

# (column_name, lower_is_better, weight)
Criterion = Tuple[str, bool, int]

# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY PRESETS — criteria + optional pre-filters
# ══════════════════════════════════════════════════════════════════════════════
SPREADSHEET_PRESETS: Dict[str, Dict[str, Any]] = {

    "magic": {
        "criteria": [
            ("ev_ebit", True, 1),       # EV/EBIT — lower is better
            ("roic",    False, 1),       # ROIC — higher is better
        ],
        # Magic/Greenblatt: only rank stocks with valid EV/EBIT > 0 and ROIC > 0
        "pre_filter": {
            "ev_ebit": {"op": ">", "val": 0},
            "roic":    {"op": ">", "val": 0},
        },
    },

    "magic_lucros": {
        "criteria": [
            ("ev_ebit",     True, 1),
            ("roic",        False, 1),
            ("cagr_lucros", False, 1),
        ],
        "pre_filter": {
            "ev_ebit": {"op": ">", "val": 0},
            "roic":    {"op": ">", "val": 0},
        },
    },

    "baratas": {
        "criteria": [
            ("queda_maximo", True, 1),   # Queda do Máximo 52sem — lower drop is better (Menor)
            ("pl",           True, 1),   # P/L — lower is better
            ("pvp",          True, 1),   # P/VP — lower is better
        ],
        "pre_filter": {
            "pl":  {"op": ">", "val": 0},
            "pvp": {"op": ">", "val": 0},
        },
    },

    "solidas": {
        "criteria": [
            ("div_pat",       True, 1),     # Dív.Líq/Patrimônio — lower is better
            ("liq_corrente",  False, 1),    # Liq. Corrente — higher is better
            ("cagr_lucros",   False, 1),    # CAGR Lucros 5 anos — higher is better
        ],
    },

    "mix": {
        "criteria": [
            ("pl",           True, 1),     # P/L — lower is better
            ("pvp",          True, 1),     # P/VP — lower is better
            ("liq_corrente", False, 1),    # Liq. Corrente — higher is better
            ("roe",          False, 1),    # ROE — higher is better
            ("cagr_lucros",  False, 1),    # CAGR Lucros 5 anos — higher is better
        ],
    },

    "dividendos": {
        "criteria": [
            ("cagr_lucros", False, 1),    # CAGR Lucros 5 anos — higher is better
            ("dy",          False, 1),    # DY — higher is better
        ],
    },

    "graham": {
        "criteria": [
            ("pl",  True, 1),
            ("pvp", True, 1),
        ],
        "pre_filter": {
            "pl":  {"op": ">", "val": 0},
            "pvp": {"op": ">", "val": 0},
        },
    },

    "greenblatt": {
        "criteria": [
            ("ev_ebit", True, 1),
            ("roic",    False, 1),
        ],
        "pre_filter": {
            "ev_ebit": {"op": ">", "val": 0},
            "roic":    {"op": ">", "val": 0},
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _transform(series: pd.Series, lower_is_better: bool) -> pd.Series:
    """
    Transform raw metric values exactly as the Excel spreadsheet does.

    - "Maior" (higher is better, lower_is_better=False):
        valor_transformado = valor (NaN → 0)

    - "Menor" (lower is better, lower_is_better=True):
        valor_transformado = 1 / valor
        if valor is NaN, 0, negative, or division error → 0
    """
    s = pd.to_numeric(series, errors="coerce")

    if lower_is_better:
        safe = s.where((s.notna()) & (s > 0), other=np.nan)
        transformed = 1.0 / safe
        transformed = transformed.fillna(0.0)
    else:
        transformed = s.fillna(0.0)

    return transformed


def _rank_desc(values: pd.Series) -> pd.Series:
    """
    Rank DESC with method='min' — exactly like Excel RANK(value, range, 0).

    Equal values get the same rank (like Excel RANK).
    Then add tie-breaker: rankFinal = rankBase + (rankBase / 10000.0)
    """
    r = values.rank(ascending=False, method="min")
    return r + (r / 10000.0)


def _apply_pre_filters(
    df: pd.DataFrame,
    pre_filter: Dict[str, Dict],
    strategy: str,
) -> pd.DataFrame:
    """
    Apply strategy-specific pre-filters to remove stocks that should not
    participate in the ranking universe (e.g., EV/EBIT <= 0 for Magic).
    This matches the Excel behavior of excluding invalid rows BEFORE ranking.
    """
    mask = pd.Series(True, index=df.index)
    removed_reasons = []

    for col, rule in pre_filter.items():
        if col not in df.columns:
            continue
        col_vals = pd.to_numeric(df[col], errors="coerce").fillna(0)
        op = rule["op"]
        val = rule["val"]
        if op == ">":
            col_mask = col_vals > val
        elif op == ">=":
            col_mask = col_vals >= val
        elif op == "<":
            col_mask = col_vals < val
        elif op == "<=":
            col_mask = col_vals <= val
        else:
            continue
        excluded = (~col_mask).sum()
        if excluded > 0:
            removed_reasons.append(f"{col} {op} {val}: excluded {excluded}")
        mask = mask & col_mask

    filtered = df[mask].copy()
    total_removed = len(df) - len(filtered)

    if total_removed > 0:
        logger.info(
            f"[spreadsheet][{strategy}] Pre-filter removed {total_removed} stocks: "
            + "; ".join(removed_reasons)
        )

    return filtered


def _compute(
    df: pd.DataFrame,
    criteria: List[Criterion],
    strategy: str = "",
) -> pd.DataFrame:
    """
    Compute the spreadsheet score for every stock in the universe.

    Score = SUM(rank_final for each criterion × weight)
    """
    out = df.copy()
    out["_score"] = 0.0

    for col, lower, weight in criteria:
        if col not in out.columns:
            logger.warning(
                f"[spreadsheet][{strategy}] column '{col}' NOT in DataFrame — skipped"
            )
            continue

        # Store raw values for audit
        raw_col = f"_raw_{col}"
        out[raw_col] = pd.to_numeric(out[col], errors="coerce")

        # Transform
        vals = _transform(out[col], lower)
        norm_col = f"_norm_{col}"
        out[norm_col] = vals

        # Rank
        ranks = _rank_desc(vals)
        rank_col = f"_r_{col}"
        out[rank_col] = ranks

        # Apply weight
        out["_score"] += ranks * weight

        logger.info(
            f"[spreadsheet][{strategy}] '{col}' "
            f"(lower={lower}, w={weight}): "
            f"valid={vals[vals != 0].count()}/{len(vals)}, "
            f"rank=[{ranks.min():.1f}..{ranks.max():.1f}]"
        )

    return out


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT MODULE
# ══════════════════════════════════════════════════════════════════════════════

def _build_audit(
    df_ranked: pd.DataFrame,
    criteria: List[Criterion],
    top_n: int = 10,
) -> List[Dict]:
    """
    Build audit trail for the top N stocks showing:
    - Ticker
    - Raw values from DB
    - Normalized values (after 1/x if applicable)
    - Individual rank scores (with decimal tie-breaker)
    - Sum breakdown
    """
    audit = []
    for idx, (_, row) in enumerate(df_ranked.head(top_n).iterrows()):
        entry = {
            "pos": idx + 1,
            "ticker": row.get("ticker", "?"),
            "empresa": row.get("empresa", ""),
            "setor": row.get("setor", ""),
            "liquidez": row.get(LIQ_COL),
            "score_final": round(row.get("_score", 0), 4),
            "criterios": [],
        }

        score_sum = 0.0
        for col, lower, weight in criteria:
            raw_val = row.get(f"_raw_{col}")
            norm_val = row.get(f"_norm_{col}")
            rank_val = row.get(f"_r_{col}")

            crit_entry = {
                "col": col,
                "direcao": "Menor" if lower else "Maior",
                "peso": weight,
                "bruto": round(raw_val, 6) if pd.notna(raw_val) else None,
                "normalizado": round(norm_val, 6) if pd.notna(norm_val) else None,
                "rank": round(rank_val, 4) if pd.notna(rank_val) else None,
                "contribuicao": round(rank_val * weight, 4) if pd.notna(rank_val) else None,
            }
            entry["criterios"].append(crit_entry)
            if pd.notna(rank_val):
                score_sum += rank_val * weight

        entry["soma_ranks"] = round(score_sum, 4)
        audit.append(entry)

    return audit


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = DEFAULT_MIN_LIQ,
    top_n: int = 100,
) -> Tuple[pd.DataFrame, List[str], int, Optional[List[Dict]]]:
    """
    Apply the spreadsheet ranking engine to the full universe.

    Returns: (df_ranked[:top_n], caveats, universe_size, audit_top10)
    """
    preset = SPREADSHEET_PRESETS.get(strategy)
    if not preset:
        logger.warning(f"[spreadsheet] unknown strategy '{strategy}'")
        return df_universe.head(top_n), ["Estratégia não encontrada"], 0, None

    caveats = []

    # 1. Filter to B3 only (matches Excel universe)
    if "market" in df_universe.columns:
        df_universe = df_universe[df_universe["market"] == "BR"].copy()

    initial_count = len(df_universe)
    logger.info(
        f"[spreadsheet] strategy='{strategy}' | "
        f"initial_universe={initial_count} BR stocks | min_liq={min_liq:,.0f}"
    )

    # 2. Apply strategy-specific pre-filters
    pre_filter = preset.get("pre_filter")
    if pre_filter:
        df_universe = _apply_pre_filters(df_universe, pre_filter, strategy)
        if len(df_universe) < initial_count:
            removed = initial_count - len(df_universe)
            caveats.append(
                f"Pré-filtro removeu {removed} ativos com valores inválidos"
            )

    # 3. Liquidity exclusion filter (matches Excel: exclude before ranking)
    if min_liq > 0 and LIQ_COL in df_universe.columns:
        liq = pd.to_numeric(df_universe[LIQ_COL], errors="coerce").fillna(0)
        before_liq = len(df_universe)
        df_universe = df_universe[liq >= min_liq].copy()
        liq_removed = before_liq - len(df_universe)
        if liq_removed > 0:
            caveats.append(
                f"Filtro de liquidez removeu {liq_removed} ativos "
                f"(mín. {min_liq:,.0f})"
            )
            logger.info(
                f"[spreadsheet][{strategy}] liquidity filter: "
                f"excluded {liq_removed} stocks < {min_liq:,.0f}"
            )

    universe_size = len(df_universe)
    logger.info(
        f"[spreadsheet][{strategy}] ranking_universe={universe_size} stocks "
        f"(after all filters)"
    )

    if df_universe.empty:
        return df_universe, ["Nenhum ativo no universo após filtros"], 0, None

    # 4. Compute scores
    criteria = preset["criteria"]
    df_scored = _compute(df_universe, criteria, strategy)

    # 5. Sort by score ASC (lowest = best) — stable mergesort
    df_ranked = df_scored.sort_values("_score", ascending=True, kind="mergesort")

    # 6. Build audit trail for top 10
    audit = _build_audit(df_ranked, criteria, top_n=10)

    # 7. Log top 10
    if not df_ranked.empty:
        top10 = df_ranked.head(10)
        rank_cols = sorted([c for c in top10.columns if c.startswith("_r_")])
        log_cols = ["ticker", "_score"] + rank_cols
        available = [c for c in log_cols if c in top10.columns]
        logger.info(
            f"[spreadsheet][{strategy}] TOP 10:\n"
            f"{top10[available].to_string(index=False)}"
        )

    return df_ranked.head(top_n), caveats, universe_size, audit
