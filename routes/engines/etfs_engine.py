"""
ETFs ENGINE — Strategy-based Screener
=======================================
Implements 4 investment models for ETFs:

  1. boglehead     — Lowest admin fee (PL > 50M, Liq > 1M)
  2. sharpe        — Highest Sharpe ratio (requires volatility data)
  3. momentum      — Highest 12-month return (PL > 50M)
  4. renda_etf     — Highest DY (dividend-paying ETFs only)
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

def _model_boglehead(df: pd.DataFrame) -> tuple:
    """
    Boglehead (Eficiência de Custo)
    Filters: PL > 50M, Liq > 1M
    Sort:    Ascending taxa_admin (lowest fee wins)
    """
    caveats = []
    df = df.copy()

    # PL filter
    if _col(df, 'patrimonio_liquido'):
        df = df[_safe(df, 'patrimonio_liquido') > 50_000_000]
    else:
        caveats.append("Patrimônio Líquido não disponível — filtro PL > 50M omitido.")

    # Liquidity filter
    liq = _safe(df, 'liquidezmediadiaria')
    df = df[liq.fillna(0) > 1_000_000]

    # Sort by admin fee
    if _col(df, 'taxa_admin'):
        df = df[_safe(df, 'taxa_admin') > 0]
        df = df.sort_values('taxa_admin', ascending=True)
        score_col = {'key': 'taxa_admin', 'label': 'Taxa Admin (%)', 'pct': False}
    else:
        caveats.append("Taxa de Administração não disponível — ordenando por liquidez como proxy.")
        df = df.sort_values('liquidezmediadiaria', ascending=False)
        score_col = {'key': 'liquidezmediadiaria', 'label': 'Liquidez Diária', 'pct': False}

    return df, score_col, caveats


def _model_sharpe(df: pd.DataFrame) -> tuple:
    """
    Risco-Retorno (Índice Sharpe)
    Formula: Sharpe = (Retorno Anualizado - Taxa Selic) / Volatilidade
    Sort:    Descending Sharpe
    """
    caveats = []
    df = df.copy()

    SELIC = 0.1375  # 13.75% — approximate current Selic

    has_sharpe_data = _col(df, 'retorno_12m') and _col(df, 'volatilidade')

    if has_sharpe_data:
        ret = _safe(df, 'retorno_12m')
        vol = _safe(df, 'volatilidade')
        # Normalize if stored as percentage
        ret_dec = ret.apply(lambda x: x / 100 if abs(x) > 5 else x)
        vol_dec = vol.apply(lambda x: x / 100 if abs(x) > 5 else x)

        df['_sharpe'] = (ret_dec - SELIC) / vol_dec.replace(0, float('nan'))
        df = df.dropna(subset=['_sharpe'])
        df = df.sort_values('_sharpe', ascending=False)
        score_col = {'key': '_sharpe', 'label': 'Índice Sharpe', 'pct': False}
    else:
        caveats.append("Retorno e/ou Volatilidade não disponíveis — ordenando por liquidez como proxy.")
        caveats.append("Para o Índice Sharpe ideal, são necessários dados de retorno anualizado e volatilidade.")
        liq = _safe(df, 'liquidezmediadiaria')
        df = df[liq.fillna(0) > 0]
        df = df.sort_values('liquidezmediadiaria', ascending=False)
        score_col = {'key': 'liquidezmediadiaria', 'label': 'Liquidez Diária', 'pct': False}

    return df, score_col, caveats


def _model_momentum(df: pd.DataFrame) -> tuple:
    """
    Momentum (Performance de Curto/Médio Prazo)
    Filters: PL > 50M (if available)
    Sort:    Descending 12-month return
    """
    caveats = []
    df = df.copy()

    # PL filter
    if _col(df, 'patrimonio_liquido'):
        df = df[_safe(df, 'patrimonio_liquido') > 50_000_000]
    else:
        caveats.append("Patrimônio Líquido não disponível — filtro PL > 50M omitido.")

    if _col(df, 'retorno_12m'):
        df['_ret_display'] = _safe(df, 'retorno_12m')
        df = df.dropna(subset=['_ret_display'])
        df = df.sort_values('_ret_display', ascending=False)
        score_col = {'key': '_ret_display', 'label': 'Retorno 12m (%)', 'pct': False}
    else:
        caveats.append("Retorno 12 meses não disponível — ordenando por liquidez como proxy.")
        liq = _safe(df, 'liquidezmediadiaria')
        df = df[liq.fillna(0) > 0]
        df = df.sort_values('liquidezmediadiaria', ascending=False)
        score_col = {'key': 'liquidezmediadiaria', 'label': 'Liquidez Diária', 'pct': False}

    return df, score_col, caveats


def _model_renda_etf(df: pd.DataFrame) -> tuple:
    """
    Renda ETF (Foco em Distribuição)
    Filters: ETFs that pay dividends (DY > 0)
    Sort:    Descending DY
    """
    caveats = []
    df = df.copy()

    if _col(df, 'dy'):
        dy = _safe(df, 'dy')
        dy_pct = dy.apply(lambda x: x * 100 if 0 < x < 1 else x)
        df['_dy_display'] = dy_pct
        df = df[dy_pct > 0]

        if len(df) == 0:
            caveats.append("Nenhum ETF com histórico de dividendos encontrado.")

        df = df.sort_values('_dy_display', ascending=False)
        score_col = {'key': '_dy_display', 'label': 'DY 12m (%)', 'pct': False}
    else:
        caveats.append("Dividend Yield não disponível para ETFs — modelo sem dados suficientes.")
        score_col = {'key': 'price', 'label': 'Preço', 'pct': False}

    return df, score_col, caveats


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════
_MODELS = {
    'boglehead':  _model_boglehead,
    'sharpe':     _model_sharpe,
    'momentum':   _model_momentum,
    'renda_etf':  _model_renda_etf,
}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def apply_etfs_strategy(
    df_universe: pd.DataFrame,
    strategy: str,
) -> tuple:
    """
    Apply an ETF strategy engine.

    Returns:
        (df_ranked, score_col, caveats)
    """
    model_fn = _MODELS.get(strategy)
    if not model_fn:
        logger.warning(f"[etfs_engine] unknown strategy '{strategy}'")
        return df_universe.head(100), {}, [f"Modelo '{strategy}' não encontrado."]

    df = df_universe.copy()

    try:
        df_ranked, score_col, caveats = model_fn(df)
    except Exception as e:
        logger.error(f"[etfs_engine] error in model '{strategy}': {e}", exc_info=True)
        return df_universe.head(0), {}, [f"Erro ao executar modelo: {str(e)}"]

    return df_ranked.head(100), score_col, caveats
