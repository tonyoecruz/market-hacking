"""
MODO PLANILHA — Weighted-Rank Engine
=====================================
Implements the spreadsheet-style relative ranking algorithm.

Algorithm:
  1. For each indicator, rank ALL stocks globally (method='min' handles ties: 1,2,2,4...)
  2. Multiply rank position × weight
  3. Sum weighted ranks → Score
  4. Sort ascending (lowest Score = best)

No absolute value filters — only relative positions matter.
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PLANILHA MODEL PRESETS
# Each criterion: (db_column, ascending, weight)
#   ascending=True  → Menor (lower value = rank 1)
#   ascending=False → Maior (higher value = rank 1)
# ══════════════════════════════════════════════════════════════════════════════
SPREADSHEET_PRESETS = {

    # ── 1. Magic ─────────────────────────────────────────────────────────────
    # Magic Formula clássica: EV/EBIT baixo + ROIC alto
    'magic': {
        'name': 'Magic',
        'criteria': [
            ('ev_ebit', True,  1),  # EV/EBIT  Menor  peso 1
            ('roic',    False, 1),  # ROIC     Maior  peso 1
        ],
        'require_positive': ['ev_ebit', 'roic'],
    },

    # ── 2. MagicLucros ───────────────────────────────────────────────────────
    # Magic + crescimento de lucros (exclui setores sem CAGR)
    'magic_lucros': {
        'name': 'MagicLucros',
        'criteria': [
            ('ev_ebit',    True,  1),  # EV/EBIT        Menor  peso 1
            ('roic',       False, 1),  # ROIC           Maior  peso 1
            ('cagr_lucros',False, 2),  # CAGR Lucros 5a Maior  peso 2
        ],
        'require_positive': ['ev_ebit', 'roic'],
    },

    # ── 3. Baratas ───────────────────────────────────────────────────────────
    # Deep value: P/VP baixo + P/L baixo + EV/EBITDA baixo
    'baratas': {
        'name': 'Baratas',
        'criteria': [
            ('pvp',      True, 2),  # P/VP      Menor  peso 2
            ('pl',       True, 1),  # P/L       Menor  peso 1
            ('ev_ebitda',True, 1),  # EV/EBITDA Menor  peso 1 ✅ dado real
        ],
        'require_positive': ['pvp', 'pl'],
    },

    # ── 4. Sólidas ───────────────────────────────────────────────────────────
    # Quality: ROE alto + Margem Líquida alta + alavancagem baixa
    'solidas': {
        'name': 'Sólidas',
        'criteria': [
            ('roe',           False, 2),  # ROE              Maior   peso 2
            ('margem_liquida',False, 1),  # Margem Líquida   Maior   peso 1 ✅ dado real
            ('div_liq_ebitda',True,  2),  # Dív.Líq/EBIT     Menor   peso 2 ✅ dado real
        ],
    },

    # ── 5. Mix ───────────────────────────────────────────────────────────────
    # Balanceado: P/L + DY + ROE
    'mix': {
        'name': 'Mix',
        'criteria': [
            ('pl',  True,  1),  # P/L  Menor  peso 1
            ('dy',  False, 1),  # DY   Maior  peso 1
            ('roe', False, 1),  # ROE  Maior  peso 1
        ],
        'require_positive': ['pl'],
    },

    # ── 6. Dividendos ────────────────────────────────────────────────────────
    # Renda: DY alto + Payout razoável
    'dividendos': {
        'name': 'Dividendos',
        'criteria': [
            ('dy',     False, 3),  # DY     Maior  peso 3
            ('payout', True,  1),  # Payout Menor  peso 1 ✅ dado real (menor payout = mais sustentável)
        ],
        'require_positive': ['dy'],
    },

    # ── 7. Graham ────────────────────────────────────────────────────────────
    # Graham puro: menores P/L e P/VP
    'graham': {
        'name': 'Graham',
        'criteria': [
            ('pl',  True, 1),  # P/L   Menor  peso 1
            ('pvp', True, 1),  # P/VP  Menor  peso 1
        ],
        'require_positive': ['pl', 'pvp'],
    },

    # ── 8. GreenBla ──────────────────────────────────────────────────────────
    # Variação pura Greenblatt: Earnings Yield alto + ROIC alto
    # EarningsYield = EBIT/EV = 1/(EV/EBIT) — calculado inline
    'greenblatt': {
        'name': 'GreenBla',
        'criteria': [
            ('earnings_yield', False, 1),  # EY = 1/EV_EBIT  Maior  peso 1
            ('roic',           False, 1),  # ROIC            Maior  peso 1
        ],
        'require_positive': ['ev_ebit', 'roic'],
        'derive': {'earnings_yield': ('reciprocal', 'ev_ebit')},
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# DERIVED FIELDS HELPER
# ══════════════════════════════════════════════════════════════════════════════
def _apply_derived_fields(df: pd.DataFrame, preset: dict) -> pd.DataFrame:
    """Compute derived columns specified in preset['derive']."""
    for new_col, (op, source_col) in preset.get('derive', {}).items():
        if source_col in df.columns:
            if op == 'reciprocal':
                df[new_col] = 1.0 / df[source_col].replace(0, float('nan'))
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CORE RANKING ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def weighted_rank(df_in: pd.DataFrame, criteria: list) -> pd.DataFrame:
    """
    Step A: Rank all rows per indicator (method='min' → ties: 1,2,2,4…)
    Step B: Multiply rank × weight
    Step C: Sum → _score
    Step D: Sort ascending (lowest score = best)
    """
    df_r = df_in.copy()
    df_r['_score'] = 0.0

    for col, ascending, weight in criteria:
        if col not in df_r.columns or df_r[col].isna().all():
            logger.debug(f"[spreadsheet] skipping column '{col}' — missing or all-null")
            continue
        ranks = df_r[col].rank(ascending=ascending, method='min', na_option='bottom')
        df_r['_score'] += ranks * weight

    return df_r.sort_values('_score', ascending=True)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = 500_000,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Apply the Planilha weighted-rank engine.

    Returns:
        (df_ranked, caveats)
        df_ranked — sorted DataFrame (top 100, post-liquidity filter)
        caveats   — list of human-readable notes about missing data
    """
    caveats: list[str] = []
    preset = SPREADSHEET_PRESETS.get(strategy)

    if not preset:
        logger.warning(f"[spreadsheet] unknown strategy '{strategy}'")
        return df_universe.head(100), [f"Estratégia '{strategy}' não encontrada."]

    df = df_universe.copy()

    # ── Derive computed columns (e.g. earnings_yield = 1/ev_ebit) ────────────
    df = _apply_derived_fields(df, preset)

    # ── Remove rows with null in ALL active indicator columns ─────────────────
    active_cols = [
        col for col, _, _ in preset['criteria']
        if col in df.columns and not df[col].isna().all()
    ]
    if active_cols:
        before = len(df)
        df = df.dropna(subset=active_cols)
        dropped = before - len(df)
        if dropped > 0:
            caveats.append(f"{dropped} ativo(s) removido(s) por dados ausentes.")

    # ── Require positive values in key columns ────────────────────────────────
    for col in preset.get('require_positive', []):
        if col in df.columns:
            df = df[df[col] > 0]

    # ── Note missing DB columns ───────────────────────────────────────────────
    missing = [
        col for col, _, _ in preset['criteria']
        if col not in df.columns or df[col].isna().all()
    ]
    if missing:
        caveats.append(f"Indicador(es) sem dados: {', '.join(missing)}.")

    # ── Rank × Weight → Score → Sort ─────────────────────────────────────────
    df_ranked = weighted_rank(df, preset['criteria'])

    # ── Post-hoc liquidity filter (preserves global rank positions) ───────────
    if min_liq > 0 and 'liquidezmediadiaria' in df_ranked.columns:
        df_ranked = df_ranked[df_ranked['liquidezmediadiaria'].fillna(0) >= min_liq]

    return df_ranked.head(100), caveats
