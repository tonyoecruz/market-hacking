from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import pandas as pd
import logging

import data_utils

from database.db_manager import DatabaseManager
db = DatabaseManager()

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# 9 MODEL PRESETS — backend configuration for each ranking strategy.
#
# Each criterion tuple: (db_column, ascending, weight)
#   ascending=True  → "Menor" (lowest value = rank 1)
#   ascending=False → "Maior" (highest value = rank 1)
#   weight          → multiplier for the rank position
#
# Algorithm:
#   Step A  — For each indicator, rank ALL stocks (ties get same position)
#   Step B  — Multiply rank × weight
#   Step C  — Sum all weighted ranks = Score
#   Step D  — Sort ascending (lowest Score = best)
# ════════════════════════════════════════════════════════════════════════════
MODEL_PRESETS = {
    # ── 1. Graham ──────────────────────────────────────────────────────────
    'graham': {
        'name': 'Graham',
        'criteria': [
            ('pl',  True, 1),   # P/L   Menor  peso 1
            ('pvp', True, 1),   # P/VP  Menor  peso 1
        ],
        'filter_positive': ['pl', 'pvp'],
    },
    # ── 2. Bazin ───────────────────────────────────────────────────────────
    'bazin': {
        'name': 'Bazin',
        'criteria': [
            ('dy',      False, 2),  # DY                Maior  peso 2
            ('div_pat', True,  1),  # Dív.Bruta/Patri.  Menor  peso 1
        ],
        'filter_positive': ['dy'],
    },
    # ── 3. Greenblatt (Magic Formula) ──────────────────────────────────────
    'greenblatt': {
        'name': 'Greenblatt',
        'criteria': [
            ('ev_ebit', True,  1),  # EV/EBIT  Menor  peso 1
            ('roic',    False, 1),  # ROIC     Maior  peso 1
        ],
        'filter_positive': ['ev_ebit', 'roic'],
    },
    # ── 4. Dividendos ─────────────────────────────────────────────────────
    'dividendos': {
        'name': 'Dividendos',
        'criteria': [
            ('dy', False, 1),  # DY  Maior  peso 1
            # Payout not in DB yet — skipped gracefully
        ],
        'filter_positive': ['dy'],
    },
    # ── 5. Valor ──────────────────────────────────────────────────────────
    'valor': {
        'name': 'Valor',
        'criteria': [
            ('pvp',      True, 2),  # P/VP      Menor  peso 2
            ('ev_ebit',  True, 1),  # EV/EBITDA Menor  peso 1 (using ev_ebit as proxy)
        ],
        'filter_positive': ['pvp'],
    },
    # ── 6. Crescimento ────────────────────────────────────────────────────
    'crescimento': {
        'name': 'Crescimento',
        'criteria': [
            ('cagr_lucros', False, 2),  # CAGR Lucro    Maior  peso 2
            # cagr_receita not in DB — skipped gracefully
            ('roe',         False, 1),  # ROE           Maior  peso 1
        ],
    },
    # ── 7. Rentabilidade ──────────────────────────────────────────────────
    'rentabilidade': {
        'name': 'Rentabilidade',
        'criteria': [
            ('roe',  False, 1),  # ROE             Maior  peso 1
            ('roic', False, 1),  # ROIC            Maior  peso 1
            # margem_liquida not in DB — skipped gracefully
        ],
    },
    # ── 8. Preço Justo ────────────────────────────────────────────────────
    'preco_justo': {
        'name': 'Preço Justo',
        'criteria': [
            ('pl',  True,  1),  # P/L  Menor  peso 1
            ('roe', False, 1),  # ROE  Maior  peso 1
        ],
        'filter_positive': ['pl'],
    },
    # ── 9. Small Caps ─────────────────────────────────────────────────────
    'small_caps': {
        'name': 'Small Caps',
        'criteria': [
            # valor_mercado not in DB — using liquidezmediadiaria as size proxy
            ('liquidezmediadiaria', True,  2),  # Menor  peso 2 (smaller = more "small cap")
            ('ev_ebit',             True,  1),  # EV/EBIT  Menor  peso 1
        ],
        'filter_positive': ['ev_ebit'],
        'filter_min_liquidity': 100000,  # Guarantee some minimum liquidity
    },
}


# ════════════════════════════════════════════════════════════════════════════
# RANKING ENGINE
# ════════════════════════════════════════════════════════════════════════════
def weighted_rank(df_in, criteria):
    """
    Weighted-rank scoring algorithm (replicates the spreadsheet logic).

    For each criterion (column, ascending, weight):
      Step A — Rank all rows by the column (ties: same position, skip next)
      Step B — Multiply rank position × weight
      Step C — Sum all weighted ranks = Score

    Step D — Sort ascending (lowest score = best).

    Columns that are missing or entirely null are gracefully skipped.
    """
    df_r = df_in.copy()
    df_r['_score'] = 0.0

    for col, asc, weight in criteria:
        if col not in df_r.columns or df_r[col].isna().all():
            continue  # gracefully skip missing / all-null columns

        # Step A: Rank — use method='min' for tie-breaking (1,2,2,4...)
        rank_col = df_r[col].rank(ascending=asc, method='min', na_option='bottom')

        # Step B: Multiply by weight
        df_r['_score'] += rank_col * weight

    # Step D: Sort ascending (lowest total score = best)
    return df_r.sort_values('_score', ascending=True)


@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request, "title": "Ações", "user": user
    })

@router.get("/api/data")
async def get_acoes_data(
    market: str = None,
    min_liq: float = 500000,   # ← Default: R$ 500.000,00
    filter_units: bool = False,
    filter_risky: bool = False,
    strategy: str = 'greenblatt'
):
    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Fetch ALL stocks — NO liquidity filter at DB level.
        # Ranking is computed on the FULL universe first, then
        # the liquidity filter is applied AFTER to preserve global
        # rank positions (matching the spreadsheet behavior).
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        stocks = db.get_stocks(market=market)
        if not stocks:
            return JSONResponse({
                'status': 'success',
                'total_count': 0,
                'ranking': [],
                'strategy': strategy
            })

        df = pd.DataFrame(stocks)

        # Force numeric columns
        numeric_cols = [
            'liquidezmediadiaria', 'lpa', 'vpa', 'margem', 'magic_rank',
            'price', 'valor_justo', 'roic', 'ev_ebit', 'pl', 'pvp', 'dy',
            'div_pat', 'cagr_lucros', 'liq_corrente'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df[col] = float('nan')

        # Derived field: ROE = LPA / VPA
        df['roe'] = df['lpa'] / df['vpa'].replace(0, float('nan'))

        # ── Full universe: price > 0 ────────────────────────────────────
        df_universe = df[df['price'].fillna(0) > 0].copy()

        if filter_units:
            df_universe = df_universe[df_universe['ticker'].str.endswith('11')]

        if filter_risky:
            df_universe = data_utils.filter_risky_stocks(df_universe)

        # ── Get model preset ────────────────────────────────────────────
        preset = MODEL_PRESETS.get(strategy)

        if preset:
            df_r = df_universe.copy()

            # ── Step 1: Remove nulls in active indicator columns ────────
            active_cols = [col for col, asc, w in preset['criteria']
                          if col in df_r.columns]
            if active_cols:
                df_r = df_r.dropna(subset=active_cols)

            # Filter positive values where required
            filter_pos = preset.get('filter_positive', [])
            for col in filter_pos:
                if col in df_r.columns:
                    df_r = df_r[df_r[col] > 0]

            # Small Caps: minimum liquidity floor
            min_liq_floor = preset.get('filter_min_liquidity', 0)
            if min_liq_floor > 0:
                df_r = df_r[
                    df_r['liquidezmediadiaria'].fillna(0) >= min_liq_floor
                ]

            # Sector exclusions (if any)
            exclude_sectors = preset.get('exclude_sectors', [])
            if exclude_sectors:
                df_r = df_r[~df_r['setor'].fillna('').isin(exclude_sectors)]

            # ── Steps A-D: Execute the weighted-rank algorithm ──────────
            df_ranked = weighted_rank(df_r, preset['criteria'])

        else:
            # Fallback: sort by liquidity
            df_ranked = df_universe.sort_values(
                'liquidezmediadiaria', ascending=False
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Apply liquidity filter AFTER ranking (preserves global ranks)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if min_liq > 0:
            df_ranked = df_ranked[
                df_ranked['liquidezmediadiaria'].fillna(0) >= min_liq
            ]

        # Take top 100
        df_ranked = df_ranked.head(100)

        # Drop internal columns
        for drop_col in ['_score', 'roe']:
            if drop_col in df_ranked.columns:
                df_ranked = df_ranked.drop(columns=[drop_col])

        df_ranked = df_ranked.replace({float('nan'): None})

        return JSONResponse({
            'status': 'success',
            'total_count': len(df_universe),
            'ranking': df_ranked.to_dict('records'),
            'strategy': strategy
        })
    except Exception as e:
        logger.error(f"ERRO API ACOES: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/api/search")
async def search_acoes(q: str = '', limit: int = 15):
    """Search assets by ticker across all markets"""
    if len(q) < 1:
        return JSONResponse({'status': 'success', 'results': []})
    try:
        results = db.search_assets(q, limit=limit)
        simplified = []
        for r in results:
            simplified.append({
                'ticker': r.get('ticker', ''),
                'empresa': r.get('empresa', ''),
                'price': r.get('price'),
                'market': r.get('market', ''),
                'asset_type': r.get('asset_type', 'stock'),
            })
        return JSONResponse({'status': 'success', 'results': simplified})
    except Exception as e:
        logger.error(f"Erro search: {e}", exc_info=True)
        return JSONResponse({'status': 'error', 'results': []})

@router.get("/api/decode/{ticker}")
async def decode_acao(ticker: str, market: str = 'BR', investor: str = ''):
    try:
        stock = db.get_stock_by_ticker(ticker, market)
        if not stock:
            other = 'US' if market == 'BR' else 'BR'
            stock = db.get_stock_by_ticker(ticker, other)

        if not stock:
            raise HTTPException(status_code=404, detail='Ticker nao encontrado')

        details = data_utils.get_stock_details(ticker)

        price = stock.get('price', 0) or 0
        valor_justo = stock.get('valor_justo', 0) or 0
        graham_ok = valor_justo > price if price > 0 else False
        magic_rank = stock.get('magic_rank')
        magic_ok = magic_rank is not None and magic_rank > 0 and magic_rank <= 50

        if details.get('Empresa') and not stock.get('empresa'):
            stock['empresa'] = details.get('Empresa')

        investor_style_prompt = None
        if investor:
            inv = db.get_investor_by_name(investor)
            if inv and inv.get('style_prompt'):
                investor_style_prompt = inv['style_prompt']

        analysis = data_utils.get_sniper_analysis(
            ticker,
            price,
            valor_justo,
            details,
            graham_ok=graham_ok,
            magic_ok=magic_ok,
            investor_style_prompt=investor_style_prompt
        )
        
        return JSONResponse({
            'status': 'success', 
            'analysis': analysis, 
            'data': stock
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro decode {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))