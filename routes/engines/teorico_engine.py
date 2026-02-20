"""
MODO TEÓRICO — Absolute Formula Engine
========================================
Implements investment models based on financial literature formulas.

Unlike the Planilha mode, this engine uses HARD FILTERS and absolute
mathematical formulas to compute intrinsic values, price targets, and
composite scores. No weighting — pure model logic.

Available models:
  1. graham        — Benjamin Graham (Valor Intrínseco via √(22.5×LPA×VPA))
  2. bazin         — Décio Bazin (Preço Teto = div_anual / 0.06)
  3. greenblatt    — Magic Formula original (rank EY + rank ROIC, excl. Financeiro)
  4. dividendos    — Income (DY > 6%, Payout 30-80%)
  5. valor         — Deep Value (EV/EBITDA positivo, sort by EV/EBIT + P/VP)
  6. crescimento   — Growth PEG (PEG = P/L / (CAGR × 100))
  7. rentabilidade — Quality (Margem Líq > 10%, DívLíq/EBITDA < 2, sort ROE)
  8. gordon        — Gordon DDM (P.Justo = Div_proj / (k - g))
  9. small_caps    — Small Caps (val. mercado < 2B, liq > 500K, sort P/L)
"""

import math
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

FINANCIAL_SECTORS = ['Bancos', 'Seguros', 'Financeiro', 'Previdência', 'Banco']
GORDON_K = 0.10   # Taxa de desconto
GORDON_G = 0.03   # Crescimento perpétuo


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _col(df: pd.DataFrame, name: str) -> bool:
    """True if column exists and has at least one non-null value."""
    return name in df.columns and not df[name].isna().all()


def _safe(df: pd.DataFrame, col: str) -> pd.Series:
    """Return numeric series or NaN series if column missing."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce')
    return pd.Series([float('nan')] * len(df), index=df.index)


# ══════════════════════════════════════════════════════════════════════════════
# MODEL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _model_graham(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Benjamin Graham — Preço Justo
    Filters : 0 < P/L ≤ 15  AND  0 < P/VP ≤ 1.5
    Formula : VI = √(22.5 × LPA × VPA)
    Sort    : Descending by margin (VI/price - 1)
    """
    caveats = []
    df = df[(df['pl'] > 0) & (df['pl'] <= 15)].copy()
    df = df[(df['pvp'] > 0) & (df['pvp'] <= 1.5)].copy()

    lpa = _safe(df, 'lpa')
    vpa = _safe(df, 'vpa')
    graham_term = 22.5 * lpa * vpa
    df['_vi'] = graham_term.apply(lambda x: math.sqrt(x) if x > 0 else float('nan'))
    df['_upside'] = (df['_vi'] / df['price'] - 1).where(df['price'] > 0)
    df = df.dropna(subset=['_vi', '_upside'])
    df = df.sort_values('_upside', ascending=False)

    score_col = {'key': '_upside', 'label': 'Upside Graham', 'pct': True}
    return df, score_col, caveats


def _model_bazin(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Décio Bazin — Preço Teto
    Filters : Dív. Bruta/Patrimônio < 0.5
    Formula : Preço Teto = DY_anual × price / 0.06
              (approximation using current DY × price as annual dividend)
    Sort    : Descending by upside vs Preço Teto
    """
    caveats = []
    if _col(df, 'div_pat'):
        df = df[df['div_pat'].fillna(999) < 0.5].copy()
    else:
        caveats.append("Dívida/Patrimônio não disponível — filtro omitido.")
        df = df.copy()

    # Approximate annual dividend = DY × price
    dy = _safe(df, 'dy')
    price = _safe(df, 'price')

    # Normalize DY (some dbs store as 0-1, others as 0-100)
    dy_norm = dy.apply(lambda x: x / 100 if x > 5 else x)
    div_anual = dy_norm * price
    df['_preco_teto'] = div_anual / 0.06
    df['_upside'] = (df['_preco_teto'] / price - 1).where(price > 0)
    df = df[df['_upside'] > 0]  # only show stocks below teto
    df = df.dropna(subset=['_preco_teto', '_upside'])
    df = df.sort_values('_upside', ascending=False)

    score_col = {'key': '_upside', 'label': 'Upside Bazin', 'pct': True}
    caveats.append("Preço Teto aproximado via DY atual (sem histórico de dividendos).")
    return df, score_col, caveats


def _model_greenblatt(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Joel Greenblatt — Magic Formula Original
    Filters : Exclude financial sector
    Calc 1  : Rank by Earnings Yield = 1/(EV/EBIT) descending
    Calc 2  : Rank by ROIC descending
    Sort    : Ascending by (rank_EY + rank_ROIC) — lowest is best
    """
    caveats = []
    # Exclude financial sector
    if 'setor' in df.columns:
        df = df[~df['setor'].fillna('').isin(FINANCIAL_SECTORS)].copy()
    else:
        caveats.append("Coluna 'setor' não disponível — filtro financeiro omitido.")
        df = df.copy()

    df = df[(df['ev_ebit'] > 0) & (df['roic'] > 0)].copy()
    df['_ey'] = 1.0 / df['ev_ebit']
    df['_rank_ey'] = df['_ey'].rank(ascending=False, method='min', na_option='bottom')
    df['_rank_roic'] = df['roic'].rank(ascending=False, method='min', na_option='bottom')
    df['_score'] = df['_rank_ey'] + df['_rank_roic']
    df = df.sort_values('_score', ascending=True)

    score_col = {'key': '_score', 'label': 'Score (menor=melhor)', 'pct': False}
    return df, score_col, caveats


def _model_dividendos(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Income — Dividendos Clássico
    Filters : DY > 6%  AND  Payout 30–80%
    Sort    : Descending DY
    """
    caveats = []
    dy = _safe(df, 'dy')
    # Normalize DY
    dy_norm = dy.apply(lambda x: x / 100 if x > 5 else x)
    df = df.copy()
    df['_dy_norm'] = dy_norm
    df = df[df['_dy_norm'] > 0.06].copy()

    # Payout filter 30–80% (now available in DB)
    if _col(df, 'payout'):
        payout = _safe(df[df['payout'] > 0], 'payout')
        payout_norm = payout.apply(lambda x: x / 100 if x > 5 else x)
        df = df.loc[df.index.isin(payout_norm.index)]
        df = df[(payout_norm >= 0.30) & (payout_norm <= 0.80)]
    else:
        caveats.append("Filtro de Payout (30-80%) omitido — dado não disponível.")

    df = df.sort_values('_dy_norm', ascending=False)
    score_col = {'key': '_dy_norm', 'label': 'Dividend Yield', 'pct': True}
    return df, score_col, caveats


def _model_valor(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Deep Value
    Filters : EV/EBITDA > 0
    Sort    : Ascending EV/EBITDA, then ascending P/VP
    """
    caveats = []
    # Use real EV/EBITDA if available, fall back to EV/EBIT
    if _col(df, 'ev_ebitda'):
        ev_col = 'ev_ebitda'
    else:
        ev_col = 'ev_ebit'
        caveats.append('EV/EBITDA não disponível — usando EV/EBIT como proxy.')

    df = df[_safe(df, ev_col) > 0].copy()
    df['_rank_evb'] = _safe(df, ev_col).rank(ascending=True, method='min')
    df['_rank_pvp'] = _safe(df, 'pvp').rank(ascending=True, method='min', na_option='bottom')
    df['_score'] = df['_rank_evb'] + df['_rank_pvp']
    df = df.sort_values('_score', ascending=True)

    score_col = {'key': ev_col, 'label': 'EV/EBITDA', 'pct': False}
    return df, score_col, caveats


def _model_crescimento(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Growth — PEG Ratio
    Formula : PEG = P/L / (CAGR_Lucros × 100)
    Sort    : Ascending PEG (best: PEG < 1.0)
    """
    caveats = []
    if not _col(df, 'cagr_lucros'):
        caveats.append("CAGR de Lucros não disponível — modelo sem dados suficientes.")
        return df.head(0), {'key': '_peg', 'label': 'PEG Ratio', 'pct': False}, caveats

    df = df.copy()
    df = df[(df['pl'] > 0) & (df['cagr_lucros'] > 0)].copy()
    cagr = _safe(df, 'cagr_lucros')
    # Normalize CAGR (some dbs store as decimal 0-1, others as percent)
    cagr_pct = cagr.apply(lambda x: x if x > 1 else x * 100)
    df['_peg'] = df['pl'] / cagr_pct.replace(0, float('nan'))
    df = df.dropna(subset=['_peg'])
    df = df[df['_peg'] > 0]
    df = df.sort_values('_peg', ascending=True)

    score_col = {'key': '_peg', 'label': 'PEG Ratio', 'pct': False}
    return df, score_col, caveats


def _model_rentabilidade(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Quality — Rentabilidade
    Filters : Margem Líquida > 10%  AND  DívLíq/EBITDA < 2
    Sort    : Descending ROE, then descending ROIC
    """
    caveats = []
    df = df.copy()

    # Margem Líquida filter — real column now available
    if _col(df, 'margem_liquida'):
        ml = _safe(df, 'margem_liquida')
        ml_norm = ml.apply(lambda x: x / 100 if x > 5 else x)  # handle % vs ratio
        df = df[ml_norm > 0.10].copy()
    elif _col(df, 'roic'):
        df = df[df['roic'] > 0.10].copy()
        caveats.append('Margem Líquida indisponível nesta atualização — usando ROIC > 10% como proxy.')
    else:
        caveats.append('Filtro de Margem Líquida omitido — dado não disponível.')

    # DívLiq/EBITDA < 2 — real column now available
    if _col(df, 'div_liq_ebitda'):
        df = df[_safe(df, 'div_liq_ebitda').fillna(999) < 2].copy()
    elif _col(df, 'div_pat'):
        df = df[df['div_pat'].fillna(999) < 2].copy()
        caveats.append('Dív.Líq/EBITDA indisponível nesta atualização — usando Dív/Patrim. como proxy.')
    else:
        caveats.append('Filtro de Dív.Líq/EBITDA omitido — dado não disponível.')

    df['_rank_roe']  = _safe(df, 'roe').rank(ascending=False, method='min', na_option='bottom')
    df['_rank_roic'] = _safe(df, 'roic').rank(ascending=False, method='min', na_option='bottom')
    df['_score'] = df['_rank_roe'] + df['_rank_roic']
    df = df.sort_values('_score', ascending=True)

    score_col = {'key': 'roe', 'label': 'ROE', 'pct': True}
    return df, score_col, caveats


def _model_gordon(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Gordon Dividend Discount Model (DDM)
    Constants : k = 10%, g = 3%
    Formula   : P_justo = Div_projetado / (k - g)
                Div_projetado ≈ DY × price  (current year dividends)
    Sort      : Descending upside
    """
    caveats = ['Dividendo projetado aproximado via DY × preço corrente.']
    dy = _safe(df, 'dy')
    price = _safe(df, 'price')
    df = df.copy()

    dy_norm = dy.apply(lambda x: x / 100 if x > 5 else x)
    div_proj = dy_norm * price
    df['_gordon'] = div_proj / (GORDON_K - GORDON_G)
    df['_upside'] = (df['_gordon'] / price - 1).where(price > 0)
    df = df.dropna(subset=['_gordon', '_upside'])
    df = df[df['_dy_norm'] > 0 if '_dy_norm' in df.columns else df['_upside'] > 0]
    df = df[df['_upside'] > 0]  # only stocks with positive upside
    df = df.sort_values('_upside', ascending=False)

    score_col = {'key': '_upside', 'label': 'Upside Gordon', 'pct': True}
    return df, score_col, caveats


def _model_small_caps(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Small Caps
    Filters : Valor de Mercado < R$ 2 Bilhões  AND  Liq. Diária > R$ 500K
    Sort    : Ascending P/L
    """
    caveats = []
    df = df.copy()

    # Use real valor_mercado if available and non-zero
    vm = _safe(df, 'valor_mercado')
    has_vm = _col(df, 'valor_mercado') and (vm > 0).any()

    if has_vm:
        df = df[(vm > 0) & (vm < 2_000_000_000)].copy()
    else:
        # Fallback: use top 75% liquidity as small cap proxy
        liq = _safe(df, 'liquidezmediadiaria')
        liq_max = liq.quantile(0.75)
        df = df[liq <= liq_max].copy()
        caveats.append('Valor de Mercado não disponível ainda — proxy: liquidez < percentil 75.')

    df = df[_safe(df, 'liquidezmediadiaria') >= 500_000].copy()
    df = df[df['pl'] > 0].copy()
    df = df.sort_values('pl', ascending=True)

    score_col = {'key': 'pl', 'label': 'P/L', 'pct': False}
    return df, score_col, caveats


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════
_MODELS: dict = {
    'graham':        _model_graham,
    'bazin':         _model_bazin,
    'greenblatt':    _model_greenblatt,
    'dividendos':    _model_dividendos,
    'valor':         _model_valor,
    'crescimento':   _model_crescimento,
    'rentabilidade': _model_rentabilidade,
    'gordon':        _model_gordon,
    'small_caps':    _model_small_caps,
}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def apply_teorico_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = 500_000,
) -> tuple[pd.DataFrame, dict, list[str]]:
    """
    Apply the Teórico absolute-formula engine.

    Returns:
        (df_ranked, score_col, caveats)
        df_ranked  — sorted DataFrame (top 100, post-liquidity filter)
        score_col  — dict with {key, label, pct} for the primary sort column
        caveats    — list of notes about missing data / approximations
    """
    model_fn = _MODELS.get(strategy)
    if not model_fn:
        logger.warning(f"[teorico] unknown strategy '{strategy}'")
        return df_universe.head(100), {}, [f"Modelo '{strategy}' não encontrado."]

    df = df_universe.copy()

    # Ensure ROE computed
    if 'roe' not in df.columns:
        lpa = pd.to_numeric(df.get('lpa', float('nan')), errors='coerce')
        vpa = pd.to_numeric(df.get('vpa', float('nan')), errors='coerce')
        df['roe'] = lpa / vpa.replace(0, float('nan'))

    try:
        df_ranked, score_col, caveats = model_fn(df)
    except Exception as e:
        logger.error(f"[teorico] error in model '{strategy}': {e}", exc_info=True)
        return df_universe.head(0), {}, [f"Erro ao executar modelo: {str(e)}"]

    # Post-hoc liquidity filter
    if min_liq > 0 and 'liquidezmediadiaria' in df_ranked.columns:
        df_ranked = df_ranked[
            df_ranked['liquidezmediadiaria'].fillna(0) >= min_liq
        ]

    return df_ranked.head(100), score_col, caveats
