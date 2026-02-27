"""
FIIs ENGINE — Strategy-based Screener
=======================================
Implements 5 investment models for Fundos Imobiliários:

  1. renda_constante   — Max Yield (high DY, P/VP 0.8–1.10)
  2. desconto_patrimonial — Deep Value (lowest P/VP, DY > 6%)
  3. bazin_fii          — Preço Teto FII (DivAnual / 0.08, margin of safety)
  4. magic_fii          — Dual Rank (DY desc + P/VP asc, lowest sum wins)
  5. qualidade_premium  — Safe Brick (filtered segment, low vacancy, DY sorted)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _safe(df: pd.DataFrame, col: str) -> pd.Series:
    """Return numeric series or NaN series if column missing."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce')
    return pd.Series([float('nan')] * len(df), index=df.index)


def _col(df: pd.DataFrame, name: str) -> bool:
    """True if column exists and has at least one non-null value."""
    return name in df.columns and not df[name].isna().all()


# ══════════════════════════════════════════════════════════════════════════════
# MODEL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _model_renda_constante(df: pd.DataFrame) -> tuple:
    """
    Renda Constante (Max Yield)
    Filters: Liq > 500K, P/VP 0.8–1.10, Vacância < 15% (if available)
    Sort:    Descending DY
    """
    caveats = []
    df = df.copy()

    # Liquidity filter
    df = df[_safe(df, 'liquidezmediadiaria').fillna(0) > 500_000]

    # P/VP range filter
    pvp = _safe(df, 'pvp')
    df = df[(pvp >= 0.80) & (pvp <= 1.10)]

    # Vacância filter (if column available)
    if _col(df, 'vacancia'):
        vac = _safe(df, 'vacancia')
        vac_norm = vac.apply(lambda x: x / 100 if x > 1 else x)
        df = df[vac_norm < 0.15]
    else:
        caveats.append("Vacância Física não disponível — filtro omitido.")

    # Normalize DY for sorting
    dy = _safe(df, 'dy')
    df['_dy_display'] = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
    df = df[df['_dy_display'] > 0]
    df = df.sort_values('_dy_display', ascending=False)

    score_col = {'key': '_dy_display', 'label': 'DY 12m (%)', 'pct': False}
    return df, score_col, caveats


def _model_desconto_patrimonial(df: pd.DataFrame) -> tuple:
    """
    Desconto Patrimonial (Deep Value FII)
    Filters: DY > 6%, P/VP 0.4–0.95
    Sort:    Ascending P/VP (most discounted wins)
    """
    caveats = []
    df = df.copy()

    # DY > 6%
    dy = _safe(df, 'dy')
    dy_pct = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
    df['_dy_display'] = dy_pct
    df = df[dy_pct > 6]

    # P/VP range
    pvp = _safe(df, 'pvp')
    df = df[(pvp > 0.4) & (pvp < 0.95)]

    df = df.sort_values('pvp', ascending=True)

    score_col = {'key': 'pvp', 'label': 'P/VP', 'pct': False}
    return df, score_col, caveats


def _model_bazin_fii(df: pd.DataFrame) -> tuple:
    """
    Bazin Imobiliário (Preço Teto FII)
    Formula: Preço Teto = DivAnual / 0.08
    Sort:    Descending margin of safety ((PrecoTeto / Price) - 1) * 100
    """
    caveats = []
    df = df.copy()

    # Liquidity filter
    df = df[_safe(df, 'liquidezmediadiaria').fillna(0) > 500_000]

    dy = _safe(df, 'dy')
    price = _safe(df, 'price')

    # Normalize DY to decimal if stored as percentage
    dy_dec = dy.apply(lambda x: x / 100 if x > 1 else x)

    # Annual dividend approximation = DY_decimal * Price
    div_anual = dy_dec * price
    df['_preco_teto'] = div_anual / 0.08
    df['_margem_seg'] = ((df['_preco_teto'] / price) - 1) * 100

    # Only show FIIs with positive margin (below teto)
    df = df[df['_margem_seg'] > 0]
    df = df.dropna(subset=['_preco_teto', '_margem_seg'])
    df = df.sort_values('_margem_seg', ascending=False)

    dy_pct = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
    df['_dy_display'] = dy_pct

    score_col = {'key': '_margem_seg', 'label': 'Margem Seg. (%)', 'pct': False}
    caveats.append("Dividendo anual aproximado via DY atual × preço (sem histórico real).")
    return df, score_col, caveats


def _model_magic_fii(df: pd.DataFrame) -> tuple:
    """
    Magic Formula FIIs (Hybrid)
    Rank 1: DY descending (highest DY = rank 1)
    Rank 2: P/VP ascending (lowest P/VP = rank 1)
    Sort:   Ascending sum (Rank1 + Rank2)
    """
    caveats = []
    df = df.copy()

    dy = _safe(df, 'dy')
    dy_pct = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
    df['_dy_display'] = dy_pct

    # Filter: need positive DY and P/VP
    df = df[(dy_pct > 0) & (_safe(df, 'pvp') > 0)]

    df['_rank_dy'] = dy_pct.rank(ascending=False, method='min', na_option='bottom')
    df['_rank_pvp'] = _safe(df, 'pvp').rank(ascending=True, method='min', na_option='bottom')
    df['_score'] = df['_rank_dy'] + df['_rank_pvp']

    df = df.sort_values('_score', ascending=True)

    score_col = {'key': '_score', 'label': 'Score (menor=melhor)', 'pct': False}
    return df, score_col, caveats


def _model_qualidade_premium(df: pd.DataFrame) -> tuple:
    """
    Qualidade Premium (Tijolo Seguro)
    Filters: Segment (Lajes/Galpões/Shoppings), Qtd Imóveis > 3, Vacância < 10%, P/VP < 1.05
    Sort:    Descending DY
    """
    caveats = []
    df = df.copy()

    # Segment filter (if available)
    if _col(df, 'segmento'):
        allowed = ['lajes corporativas', 'galpões logísticos', 'shoppings',
                    'lajes comerciais', 'logística', 'shopping']
        df = df[df['segmento'].str.lower().fillna('').apply(
            lambda s: any(a in s for a in allowed)
        )]
    else:
        caveats.append("Segmento não disponível — filtro de tipo de FII omitido.")

    # Qty of properties filter (if available)
    if _col(df, 'qtd_imoveis'):
        df = df[_safe(df, 'qtd_imoveis') > 3]
    else:
        caveats.append("Qtd de Imóveis não disponível — filtro omitido.")

    # Vacancy filter (if available)
    if _col(df, 'vacancia'):
        vac = _safe(df, 'vacancia')
        vac_norm = vac.apply(lambda x: x / 100 if x > 1 else x)
        df = df[vac_norm < 0.10]
    else:
        caveats.append("Vacância Física não disponível — filtro omitido.")

    # P/VP < 1.05
    pvp = _safe(df, 'pvp')
    df = df[pvp < 1.05]

    # Sort by DY descending
    dy = _safe(df, 'dy')
    dy_pct = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
    df['_dy_display'] = dy_pct
    df = df.sort_values('_dy_display', ascending=False)

    score_col = {'key': '_dy_display', 'label': 'DY 12m (%)', 'pct': False}
    return df, score_col, caveats


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════
_MODELS = {
    'renda_constante':      _model_renda_constante,
    'desconto_patrimonial': _model_desconto_patrimonial,
    'bazin_fii':            _model_bazin_fii,
    'magic_fii':            _model_magic_fii,
    'qualidade_premium':    _model_qualidade_premium,
}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def apply_fiis_strategy(
    df_universe: pd.DataFrame,
    strategy: str,
) -> tuple:
    """
    Apply a FII strategy engine.

    Returns:
        (df_ranked, score_col, caveats)
    """
    model_fn = _MODELS.get(strategy)
    if not model_fn:
        logger.warning(f"[fiis_engine] unknown strategy '{strategy}'")
        return df_universe.head(100), {}, [f"Modelo '{strategy}' não encontrado."]

    df = df_universe.copy()

    try:
        df_ranked, score_col, caveats = model_fn(df)
    except Exception as e:
        logger.error(f"[fiis_engine] error in model '{strategy}': {e}", exc_info=True)
        return df_universe.head(0), {}, [f"Erro ao executar modelo: {str(e)}"]

    return df_ranked.head(100), score_col, caveats
