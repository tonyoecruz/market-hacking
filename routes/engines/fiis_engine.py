"""
FIIs ENGINE — Strategy-based Screener
=======================================
Implements 5 investment models for Fundos Imobiliários:

  1. renda_constante      — Sustainable Income (DY + quality + P/VP sweet spot)
  2. desconto_patrimonial — Deep Value (lowest P/VP, DY > 6%, quality weighted)
  3. bazin_fii            — Preço Teto FII (margin of safety + quality)
  4. magic_fii            — Triple Rank (DY + P/VP + liquidity)
  5. qualidade_premium    — Tijolo Seguro (quality-first, institutional grade)

All models use COMPOSITE SCORING — not pure single-metric sorts.
This ensures high-quality, institutional-grade FIIs rank above junk
high-yield FIIs with unsustainable dividends.
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


def _norm(s: pd.Series) -> pd.Series:
    """Min-max normalize to 0-1 range."""
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)


def _dy_pct(df: pd.DataFrame) -> pd.Series:
    """Normalize DY to percentage (0.08 → 8.0, 8.0 stays 8.0)."""
    dy = _safe(df, 'dy')
    return dy.apply(lambda x: x * 100 if 0 < x < 1 else x)


def _quality_score(df: pd.DataFrame) -> pd.Series:
    """
    Institutional quality proxy based on log-scale liquidity.
    R$50K daily = 0.0, R$30M daily = 1.0
    High liquidity = institutional investors = quality signal.
    """
    log_liq = np.log10(_safe(df, 'liquidezmediadiaria').clip(1))
    return ((log_liq - 4.7) / (7.5 - 4.7)).clip(0, 1)


def _sustainability_score(dy_pct: pd.Series) -> pd.Series:
    """
    DY sustainability: 6-10% is the sweet spot for FIIs.
    DY > 13% is likely unsustainable (fund selling assets, special distributions).
    """
    return dy_pct.apply(
        lambda v: 1.0 if v <= 12 else max(0.1, 1.0 - (v - 12) / 10)
    ).fillna(0)


def _pvp_sweet_spot(df: pd.DataFrame, ideal_min=0.85, ideal_max=1.10) -> pd.Series:
    """Score P/VP: 1.0 in sweet spot, tapering off outside."""
    pvp = _safe(df, 'pvp')
    def score(v):
        if ideal_min <= v <= ideal_max:
            return 1.0
        if v < ideal_min:
            return max(0.0, 1.0 - (ideal_min - v) / 0.30)
        return max(0.0, 1.0 - (v - ideal_max) / 0.30)
    return pvp.apply(score).fillna(0)


# ══════════════════════════════════════════════════════════════════════════════
# MODEL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _model_renda_constante(df: pd.DataFrame) -> tuple:
    """
    Renda Constante (Sustainable Income)
    Composite: 35% DY + 30% quality + 20% P/VP sweet spot + 15% sustainability
    Filters: Liq > 500K, P/VP 0.70–1.20, DY > 0, Vacância < 15%
    """
    caveats = []
    df = df.copy()

    # Liquidity filter
    df = df[_safe(df, 'liquidezmediadiaria').fillna(0) > 500_000]

    # P/VP range
    pvp = _safe(df, 'pvp')
    df = df[(pvp >= 0.70) & (pvp <= 1.20)]

    # Vacância filter
    if _col(df, 'vacancia'):
        vac = _safe(df, 'vacancia')
        vac_norm = vac.apply(lambda x: x / 100 if x > 1 else x)
        df = df[vac_norm < 0.15]
    else:
        caveats.append("Vacância Física não disponível — filtro omitido.")

    # DY normalization
    df['_dy_display'] = _dy_pct(df)
    df = df[df['_dy_display'] > 0]

    if df.empty:
        return df, {}, caveats

    # Composite score
    dy_norm = (df['_dy_display'] / 12.0).clip(0, 1)  # 12% = full score
    quality = _quality_score(df)
    pvp_ss = _pvp_sweet_spot(df)
    sustain = _sustainability_score(df['_dy_display'])

    df['_composite'] = (
        0.35 * dy_norm +
        0.30 * quality +
        0.20 * pvp_ss +
        0.15 * sustain
    ).fillna(0)

    df = df.sort_values('_composite', ascending=False)

    score_col = {'key': '_dy_display', 'label': 'DY 12m (%)', 'pct': False}
    return df, score_col, caveats


def _model_desconto_patrimonial(df: pd.DataFrame) -> tuple:
    """
    Desconto Patrimonial (Deep Value FII)
    Composite: 35% discount (1 - P/VP) + 30% DY + 25% quality + 10% sustainability
    Filters: DY > 6%, P/VP 0.4–0.95
    """
    caveats = []
    df = df.copy()

    # DY > 6%
    df['_dy_display'] = _dy_pct(df)
    df = df[df['_dy_display'] > 6]

    # P/VP range
    pvp = _safe(df, 'pvp')
    df = df[(pvp > 0.4) & (pvp < 0.95)]

    if df.empty:
        return df, {}, caveats

    # Composite score
    discount = _norm((1 - pvp.loc[df.index]).clip(0, 1))
    dy_norm = (df['_dy_display'] / 12.0).clip(0, 1)
    quality = _quality_score(df)
    sustain = _sustainability_score(df['_dy_display'])

    df['_composite'] = (
        0.35 * discount +
        0.30 * dy_norm +
        0.25 * quality +
        0.10 * sustain
    ).fillna(0)

    df = df.sort_values('_composite', ascending=False)

    score_col = {'key': 'pvp', 'label': 'P/VP', 'pct': False}
    return df, score_col, caveats


def _model_bazin_fii(df: pd.DataFrame) -> tuple:
    """
    Bazin Imobiliário (Preço Teto FII)
    Formula: Preço Teto = DivAnual / 0.06  (6% target yield)
    Composite: 35% margin + 30% quality + 20% sustainability + 15% P/VP
    """
    caveats = []
    df = df.copy()

    # Liquidity filter
    df = df[_safe(df, 'liquidezmediadiaria').fillna(0) > 500_000]

    dy = _safe(df, 'dy')
    price = _safe(df, 'price')

    # Normalize DY to decimal
    dy_dec = dy.apply(lambda x: x / 100 if x > 1 else x)

    # Annual dividend = DY_decimal * Price
    div_anual = dy_dec * price
    df['_preco_teto'] = div_anual / 0.06
    df['_margem_seg'] = ((df['_preco_teto'] / price) - 1) * 100

    # Only show FIIs with positive margin
    df = df[df['_margem_seg'] > 0]
    df = df.dropna(subset=['_preco_teto', '_margem_seg'])

    df['_dy_display'] = _dy_pct(df)

    if df.empty:
        return df, {}, caveats

    # Composite score
    margin_norm = _norm(df['_margem_seg'])
    quality = _quality_score(df)
    sustain = _sustainability_score(df['_dy_display'])
    pvp_ss = _pvp_sweet_spot(df, ideal_min=0.75, ideal_max=1.15)

    df['_composite'] = (
        0.35 * margin_norm +
        0.30 * quality +
        0.20 * sustain +
        0.15 * pvp_ss
    ).fillna(0)

    df = df.sort_values('_composite', ascending=False)

    score_col = {'key': '_margem_seg', 'label': 'Margem Seg. (%)', 'pct': False}
    caveats.append("Preço teto calculado com taxa alvo de 6% a.a. Dividendo anual aproximado via DY atual × preço.")
    return df, score_col, caveats


def _model_magic_fii(df: pd.DataFrame) -> tuple:
    """
    Magic Formula FIIs (Triple Rank)
    Rank 1: DY descending (highest DY = rank 1)
    Rank 2: P/VP ascending (lowest P/VP = rank 1)
    Rank 3: Liquidity descending (highest volume = rank 1)
    Sort:   Ascending weighted sum (lower = better)
    """
    caveats = []
    df = df.copy()

    df['_dy_display'] = _dy_pct(df)

    # Filter: need positive DY, P/VP, and some liquidity
    df = df[
        (df['_dy_display'] > 0) &
        (_safe(df, 'pvp') > 0) &
        (_safe(df, 'liquidezmediadiaria').fillna(0) > 100_000)
    ]

    if df.empty:
        return df, {}, caveats

    df['_rank_dy'] = df['_dy_display'].rank(ascending=False, method='min', na_option='bottom')
    df['_rank_pvp'] = _safe(df, 'pvp').rank(ascending=True, method='min', na_option='bottom')
    df['_rank_liq'] = _safe(df, 'liquidezmediadiaria').rank(ascending=False, method='min', na_option='bottom')

    # Weighted sum: DY and P/VP equally important, liquidity as tiebreaker
    df['_score'] = df['_rank_dy'] + df['_rank_pvp'] + 0.5 * df['_rank_liq']

    df = df.sort_values('_score', ascending=True)

    score_col = {'key': '_score', 'label': 'Score (menor=melhor)', 'pct': False}
    return df, score_col, caveats


def _model_qualidade_premium(df: pd.DataFrame) -> tuple:
    """
    Qualidade Premium (Tijolo Seguro — Institutional Grade)
    Composite: 30% quality + 30% DY + 20% P/VP sweet spot + 20% sustainability
    Filters: Segment, Vacância < 10%, P/VP < 1.20, Liq > 1M
    """
    caveats = []
    df = df.copy()

    # Higher liquidity floor — institutional grade
    df = df[_safe(df, 'liquidezmediadiaria').fillna(0) > 1_000_000]

    # Segment filter (if available)
    if _col(df, 'segmento'):
        allowed = ['lajes', 'galpões', 'galpoes', 'shoppings', 'shopping',
                    'logística', 'logistica', 'renda urbana', 'híbrido', 'hibrido',
                    'corporativ', 'comerci', 'varejo', 'educacional', 'hotel',
                    'hospital', 'agro', 'industrial', 'tijolo']
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

    # Vacancy filter
    if _col(df, 'vacancia'):
        vac = _safe(df, 'vacancia')
        vac_norm = vac.apply(lambda x: x / 100 if x > 1 else x)
        df = df[vac_norm < 0.10]
    else:
        caveats.append("Vacância Física não disponível — filtro omitido.")

    # P/VP < 1.20
    pvp = _safe(df, 'pvp')
    df = df[pvp < 1.20]

    df['_dy_display'] = _dy_pct(df)
    df = df[df['_dy_display'] > 0]

    if df.empty:
        return df, {}, caveats

    # Composite score — quality-first
    quality = _quality_score(df)
    dy_norm = (df['_dy_display'] / 10.0).clip(0, 1)  # 10% = full score (quality focus)
    pvp_ss = _pvp_sweet_spot(df, ideal_min=0.85, ideal_max=1.10)
    sustain = _sustainability_score(df['_dy_display'])

    df['_composite'] = (
        0.30 * quality +
        0.30 * dy_norm +
        0.20 * pvp_ss +
        0.20 * sustain
    ).fillna(0)

    df = df.sort_values('_composite', ascending=False)

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
