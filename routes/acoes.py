"""
Ações Router — Hybrid Screener V2.0
======================================
Two calculation modes, two API endpoints:

  GET /acoes/api/data           → Modo Planilha (weighted-rank engine)
  GET /acoes/api/data-teorico   → Modo Teórico  (absolute-formula engine)

Each endpoint delegates entirely to its respective engine module:
  routes/engines/spreadsheet_engine.py
  routes/engines/teorico_engine.py
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import pandas as pd
import logging

import data_utils
from database.db_manager import DatabaseManager
from routes.engines.spreadsheet_engine import apply_spreadsheet_mode
from routes.engines.teorico_engine import apply_teorico_mode

db = DatabaseManager()
router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED: Fetch + normalise the universe DataFrame
# ══════════════════════════════════════════════════════════════════════════════
def _build_universe(market: str | None, filter_risky: bool) -> pd.DataFrame | None:
    stocks = db.get_stocks(market=market)
    if not stocks:
        return None

    df = pd.DataFrame(stocks)

    numeric_cols = [
        'liquidezmediadiaria', 'lpa', 'vpa', 'margem', 'magic_rank',
        'price', 'valor_justo', 'roic', 'ev_ebit', 'pl', 'pvp', 'dy',
        'div_pat', 'cagr_lucros', 'liq_corrente',
        # ── Hybrid Screener V2.0 columns ──
        'roe', 'roa', 'margem_liquida', 'ev_ebitda', 'payout', 'valor_mercado', 'div_liq_ebitda',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            df[col] = float('nan')

    # Derived: ROE = LPA / VPA (fallback if 'roe' not already in DB)
    if 'roe' not in df.columns or df['roe'].isna().all():
        df['roe'] = df['lpa'] / df['vpa'].replace(0, float('nan'))
    else:
        # roe comes from StatusInvest as ratio (already divided by 100 in extractor)
        df['roe'] = pd.to_numeric(df['roe'], errors='coerce')
        # Fill nulls with LPA/VPA proxy
        mask = df['roe'].isna()
        if mask.any():
            df.loc[mask, 'roe'] = df.loc[mask, 'lpa'] / df.loc[mask, 'vpa'].replace(0, float('nan'))

    # Universe: price > 0
    df = df[df['price'].fillna(0) > 0].copy()

    if filter_risky:
        try:
            df = data_utils.filter_risky_stocks(df)
        except Exception:
            pass  # best-effort

    return df


def _clean_for_response(df: pd.DataFrame) -> pd.DataFrame:
    """Drop internal _* columns and replace NaN with None for JSON."""
    internal = [c for c in df.columns if c.startswith('_')]
    if internal:
        df = df.drop(columns=internal)
    return df.replace({float('nan'): None})


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTE
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request, "title": "Ações", "user": user
    })


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT 1 — MODO PLANILHA (Weighted-Rank)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/data")
async def get_acoes_data(
    market: str = None,
    min_liq: float = 500_000,
    filter_risky: bool = False,
    strategy: str = 'magic',
    mode: str = 'planilha',      # kept for symmetry / logging
):
    """
    Modo Planilha: relative weighted-rank scoring.
    Rankings are global (all stocks) → liquidity filter applied after.
    """
    try:
        df_universe = _build_universe(market, filter_risky)
        if df_universe is None or df_universe.empty:
            return JSONResponse({
                'status': 'success', 'total_count': 0,
                'ranking': [], 'strategy': strategy,
                'mode': 'planilha', 'caveats': [], 'audit': []
            })

        df_ranked, caveats, universe_size, audit = apply_spreadsheet_mode(
            df_universe, strategy, min_liq
        )
        df_clean = _clean_for_response(df_ranked)

        return JSONResponse({
            'status': 'success',
            'total_count': universe_size,
            'ranking': df_clean.to_dict('records'),
            'strategy': strategy,
            'mode': 'planilha',
            'caveats': caveats,
            'audit': audit or [],
        })

    except Exception as e:
        logger.error(f"[api/data] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT — DEBUG RANKING (returns _score + _r_* rank columns)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/debug-ranking")
async def debug_ranking(
    market: str = "BR",
    min_liq: float = 500_000,
    strategy: str = 'magic',
    top_n: int = 50,
):
    """
    Debug endpoint: returns ranking with _score and per-criterion _r_* columns
    visible, not stripped by _clean_for_response.
    """
    try:
        df_universe = _build_universe(market, filter_risky=False)
        if df_universe is None or df_universe.empty:
            return JSONResponse({'status': 'error', 'message': 'No data'})

        df_ranked, caveats, universe_size, audit = apply_spreadsheet_mode(
            df_universe, strategy, min_liq, top_n=top_n
        )

        # Keep internal columns for debugging — only replace NaN
        df_debug = df_ranked.replace({float('nan'): None})

        # Select columns: ticker, key metrics, _score, _raw_*, _norm_*, _r_*
        raw_cols = sorted([c for c in df_debug.columns if c.startswith('_raw_')])
        norm_cols = sorted([c for c in df_debug.columns if c.startswith('_norm_')])
        rank_cols = sorted([c for c in df_debug.columns if c.startswith('_r_')])
        display_cols = [
            'ticker', 'empresa', 'setor', 'price', 'liquidezmediadiaria',
            'ev_ebit', 'roic', 'pl', 'pvp', 'dy', 'roe', 'div_pat',
            'cagr_lucros', 'margem_liquida',
            '_score', '_liq_penalty',
        ] + raw_cols + norm_cols + rank_cols
        available_cols = [c for c in display_cols if c in df_debug.columns]

        return JSONResponse({
            'status': 'success',
            'strategy': strategy,
            'market': market,
            'min_liq': min_liq,
            'total_universe': universe_size,
            'ranked_count': len(df_debug),
            'caveats': caveats,
            'audit': audit or [],
            'ranking': df_debug[available_cols].to_dict('records'),
        })

    except Exception as e:
        logger.error(f"[api/debug-ranking] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT — DIAGNÓSTICO: checar dados de tickers específicos
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/diagnostico")
async def diagnostico(
    tickers: str = "PRIO3,WEGE3,MWET4,RIAA3,WIZC3",
    market: str = "BR",
):
    """
    Diagnostic endpoint: returns raw DB values for specific tickers.
    Usage: /acoes/api/diagnostico?tickers=PRIO3,WEGE3,MWET4
    """
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        df_universe = _build_universe(market, filter_risky=False)
        if df_universe is None or df_universe.empty:
            return JSONResponse({'status': 'error', 'message': 'No data'})

        # Filter to requested tickers
        df_match = df_universe[df_universe['ticker'].isin(ticker_list)]
        df_missing = [t for t in ticker_list if t not in df_match['ticker'].values]

        cols = [
            'ticker', 'empresa', 'setor', 'price',
            'ev_ebit', 'roic', 'pl', 'pvp', 'dy',
            'roe', 'roa', 'div_pat', 'cagr_lucros', 'margem_liquida',
            'liquidezmediadiaria', 'magic_rank',
        ]
        available = [c for c in cols if c in df_match.columns]
        result = df_match[available].replace({float('nan'): None}).to_dict('records')

        return JSONResponse({
            'status': 'success',
            'found': len(result),
            'missing_tickers': df_missing,
            'total_universe': len(df_universe),
            'data': result,
        })
    except Exception as e:
        logger.error(f"[diagnostico] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT 2 — MODO TEÓRICO (Absolute Formulas)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/data-teorico")
async def get_acoes_data_teorico(
    market: str = None,
    min_liq: float = 500_000,
    filter_risky: bool = False,
    strategy: str = 'graham',
):
    """
    Modo Teórico: absolute mathematical formulas and hard filters.
    """
    try:
        df_universe = _build_universe(market, filter_risky)
        if df_universe is None or df_universe.empty:
            return JSONResponse({
                'status': 'success', 'total_count': 0,
                'ranking': [], 'strategy': strategy,
                'mode': 'teorico', 'caveats': [], 'score_col': {}
            })

        total = len(df_universe)
        df_ranked, score_col, caveats = apply_teorico_mode(df_universe, strategy, min_liq)
        df_ranked = _clean_for_response(df_ranked)

        return JSONResponse({
            'status': 'success',
            'total_count': total,
            'ranking': df_ranked.to_dict('records'),
            'strategy': strategy,
            'mode': 'teorico',
            'caveats': caveats,
            'score_col': score_col,
        })

    except Exception as e:
        logger.error(f"[api/data-teorico] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH + DECODE (unchanged)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/search")
async def search_acoes(q: str = '', limit: int = 15):
    if len(q) < 1:
        return JSONResponse({'status': 'success', 'results': []})
    try:
        results = db.search_assets(q, limit=limit)
        return JSONResponse({
            'status': 'success',
            'results': [
                {
                    'ticker': r.get('ticker', ''),
                    'empresa': r.get('empresa', ''),
                    'price': r.get('price'),
                    'market': r.get('market', ''),
                    'asset_type': r.get('asset_type', 'stock'),
                }
                for r in results
            ]
        })
    except Exception as e:
        logger.error(f"[search] {e}", exc_info=True)
        return JSONResponse({'status': 'error', 'results': []})


@router.get("/api/decode/{ticker}")
async def decode_acao(ticker: str, market: str = 'BR', investor: str = ''):
    try:
        stock = db.get_stock_by_ticker(ticker, market)
        if not stock:
            other = 'US' if market == 'BR' else 'BR'
            stock = db.get_stock_by_ticker(ticker, other)
        if not stock:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')

        details = data_utils.get_stock_details(ticker)
        price = stock.get('price', 0) or 0
        valor_justo = stock.get('valor_justo', 0) or 0
        graham_ok = valor_justo > price if price > 0 else False
        magic_rank = stock.get('magic_rank')
        magic_ok = magic_rank is not None and 0 < magic_rank <= 50

        if details.get('Empresa') and not stock.get('empresa'):
            stock['empresa'] = details.get('Empresa')

        investor_style_prompt = None
        if investor:
            inv = db.get_investor_by_name(investor)
            if inv and inv.get('style_prompt'):
                investor_style_prompt = inv['style_prompt']

        analysis = data_utils.get_sniper_analysis(
            ticker, price, valor_justo, details,
            graham_ok=graham_ok, magic_ok=magic_ok,
            investor_style_prompt=investor_style_prompt
        )
        return JSONResponse({'status': 'success', 'analysis': analysis, 'data': stock})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[decode/{ticker}] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))