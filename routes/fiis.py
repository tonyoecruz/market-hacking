"""
FIIs Router — Strategy Screener
=================================
Two modes:
  GET /fiis/api/data              → Legacy simple DY-sorted list
  GET /fiis/api/data-estrategia   → Strategy-based engine (5 models)
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
from database.db_manager import DatabaseManager
from routes.engines.fiis_engine import apply_fiis_strategy
import pandas as pd
import logging

import data_utils

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")
db = DatabaseManager()


# ══════════════════════════════════════════════════════════════════════════════
# SHARED: Build FII Universe DataFrame
# ══════════════════════════════════════════════════════════════════════════════
def _build_fii_universe() -> pd.DataFrame | None:
    fiis = db.get_fiis()
    if not fiis:
        return None

    df = pd.DataFrame(fiis)

    numeric_cols = ['liquidezmediadiaria', 'dy', 'price', 'pvp']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Filter: price > 0
    df = df[df['price'].fillna(0) > 0].copy()
    return df


def _clean_for_response(df: pd.DataFrame) -> pd.DataFrame:
    """Drop internal _* columns and replace NaN with None for JSON."""
    internal = [c for c in df.columns if c.startswith('_')]
    keep = [c for c in df.columns if not c.startswith('_')]
    # Also keep score/display columns that start with _
    score_cols = [c for c in internal if any(k in c for k in ['_dy_display', '_margem_seg', '_preco_teto', '_score', '_rank_dy', '_rank_pvp'])]
    result = df[keep + score_cols].copy()
    return result.replace({float('nan'): None})


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTE
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
async def fiis_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/fiis.html", {"request": request, "title": "FIIs", "user": user})


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT — STRATEGY ENGINE
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/data-estrategia")
async def get_fiis_data_estrategia(
    strategy: str = 'renda_constante',
):
    """
    Strategy-based FII screener.
    Available strategies: renda_constante, desconto_patrimonial, bazin_fii, magic_fii, qualidade_premium
    """
    try:
        df_universe = _build_fii_universe()
        if df_universe is None or df_universe.empty:
            return JSONResponse({
                'status': 'success', 'total_count': 0,
                'ranking': [], 'strategy': strategy,
                'caveats': [], 'score_col': {}
            })

        total = len(df_universe)
        df_ranked, score_col, caveats = apply_fiis_strategy(df_universe, strategy)
        df_ranked = _clean_for_response(df_ranked)

        return JSONResponse({
            'status': 'success',
            'total_count': total,
            'ranking': df_ranked.to_dict('records'),
            'strategy': strategy,
            'caveats': caveats,
            'score_col': score_col,
        })

    except Exception as e:
        logger.error(f"[fiis/api/data-estrategia] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY API ENDPOINT (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/api/scan")
async def scan_fiis(request: Request):
    """Trigger FII data scan/update"""
    try:
        from scheduler.data_updater import update_fiis
        result = update_fiis()
        return JSONResponse({
            'status': 'success',
            'message': f'FIIs atualizados com sucesso!'
        })
    except Exception as e:
        logger.error(f"Erro ao escanear FIIs: {e}", exc_info=True)
        return JSONResponse({
            'status': 'error',
            'message': f'Erro ao escanear FIIs: {str(e)}'
        }, status_code=500)


@router.get("/api/data")
async def get_fiis_data(min_dy: float = 0.0, min_liq: float = 0, max_pvp: float = 999.0, filter_risky: bool = False):
    try:
        fiis = db.get_fiis(min_dy=min_dy)
        if not fiis:
            return JSONResponse({'status': 'success', 'message': 'Aguardando atualizacao de dados.', 'top_dy': []})

        df = pd.DataFrame(fiis)

        # Coerce numeric
        numeric_cols = ['liquidezmediadiaria', 'dy', 'price', 'pvp']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        if min_liq > 0:
            df_filtered = df[df['liquidezmediadiaria'].fillna(0) >= min_liq].copy()
        else:
            df_filtered = df[df['price'].fillna(0) > 0].copy()

        # P/VP filter
        if max_pvp < 999:
            df_filtered = df_filtered[df_filtered['pvp'] <= max_pvp]

        # Risk filter: remove FIIs with very low liquidity
        if filter_risky:
            df_filtered = df_filtered[df_filtered['liquidezmediadiaria'] >= 50000]

        top_dy = df_filtered.sort_values('dy', ascending=False).head(20)

        # Replace NaN for JSON
        top_dy = top_dy.replace({float('nan'): None})

        return JSONResponse({'status': 'success', 'top_dy': top_dy.to_dict('records')})
    except Exception as e:
        print(f"ERRO API FIIS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/decode/{ticker}")
async def decode_fii(ticker: str, investor: str = ''):
    """AI analysis for a specific FII"""
    try:
        fii = db.get_fii_by_ticker(ticker)
        if not fii:
            raise HTTPException(status_code=404, detail='FII nao encontrado')

        price = fii.get('price', 0) or 0
        pvp = fii.get('pvp', 0) or 0
        dy = fii.get('dy', 0) or 0

        # Fetch investor style_prompt if specified
        investor_style_prompt = None
        if investor:
            inv = db.get_investor_by_name(investor)
            if inv and inv.get('style_prompt'):
                investor_style_prompt = inv['style_prompt']

        analysis = data_utils.get_fii_analysis(
            ticker, price, pvp, dy,
            details={},
            investor_style_prompt=investor_style_prompt
        )

        return JSONResponse({
            'status': 'success',
            'analysis': analysis,
            'data': fii
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro decode FII {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))