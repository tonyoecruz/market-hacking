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
# MODEL PRESETS — backend configuration for each ranking strategy.
# Each tuple: (db_column, ascending, weight)
#   ascending=True  → "Menor" (lowest value = rank 1)
#   ascending=False → "Maior" (highest value = rank 1)
#   weight          → multiplier for the rank position
#
# Algorithm:  rank(indicator) × weight  →  sum all  →  sort ascending
# ════════════════════════════════════════════════════════════════════════════
MODEL_PRESETS = {
    'magic': {
        'name': 'Magic',
        'criteria': [
            ('ev_ebit', True,  21),   # EV/EBIT  Menor  peso 21
            ('roic',    False, 30),   # ROIC     Maior  peso 30
        ],
        'filter_positive': ['ev_ebit', 'roic'],
    },
    'magic_lucros': {
        'name': 'MagicLucros',
        'criteria': [
            ('ev_ebit',     True,  21),  # EV/EBIT          Menor  peso 21
            ('roic',        False, 30),  # ROIC             Maior  peso 30
            ('cagr_lucros', False, 35),  # CAGR Lucros 5a   Maior  peso 35
        ],
        'filter_positive': ['ev_ebit', 'roic'],
        'exclude_sectors': [
            'Utilidade Pública', 'Utility', 'Energia Elétrica',
            'Financeiro', 'Bancos', 'Seguros', 'Previdência e Seguros',
            'Intermediários Financeiros', 'Serviços Financeiros',
        ],
    },
    'baratas': {
        'name': 'Baratas',
        'criteria': [
            ('queda_maximo', False, 12),  # Queda do Máximo  Maior  peso 12
            ('pl',           True,  14),  # P/L              Menor  peso 14
            ('pvp',          False, 15),  # P/VP             Maior  peso 15
        ],
        'filter_positive': ['pl'],
    },
    'solidas': {
        'name': 'Sólidas',
        'criteria': [
            ('liq_corrente', False, 27),  # Liq. Corrente    Maior  peso 27
            ('div_pat',      True,  23),  # Div.Liq./Patri.  Menor  peso 23
            ('cagr_lucros',  False, 35),  # CAGR Lucros 5a   Maior  peso 35
        ],
        'require_cols': ['div_pat'],
    },
    'mix': {
        'name': 'Mix',
        'criteria': [
            ('pl',           True,  14),  # P/L              Menor  peso 14
            ('pvp',          False, 15),  # P/VP             Maior  peso 15
            ('liq_corrente', False, 27),  # Liq. Corrente    Maior  peso 27
            ('roe',          False, 28),  # ROE              Maior  peso 28
            ('cagr_lucros',  False, 35),  # CAGR Lucros 5a   Maior  peso 35
        ],
        'filter_positive': ['pl'],
    },
    'dividendos': {
        'name': 'Dividendos',
        'criteria': [
            ('dy',          False, 13),  # DY               Maior  peso 13
            ('cagr_lucros', False, 35),  # CAGR Lucros 5a   Maior  peso 35
        ],
        'filter_positive': ['dy'],
    },
    'graham': {
        'name': 'Graham',
        'criteria': [
            ('dy',  False, 13),  # DY    Maior  peso 13
            ('pl',  True,  14),  # P/L   Menor  peso 14
            ('pvp', False, 15),  # P/VP  Maior  peso 15
        ],
        'filter_positive': ['pl', 'pvp'],
    },
    'greenblatt': {
        'name': 'GreenBla',
        'criteria': [
            ('ev_ebit', True,  21),  # EV/EBIT  Menor  peso 21
            ('roic',    False, 30),  # ROIC     Maior  peso 30
        ],
        'filter_positive': ['ev_ebit', 'roic'],
        'liquidity_filter': 'below_median',  # GreenBla = Magic but less-liquid
    },
}


# ════════════════════════════════════════════════════════════════════════════
# RANKING ENGINE
# ════════════════════════════════════════════════════════════════════════════
def weighted_rank(df_in, criteria):
    """
    Weighted-rank scoring algorithm.

    For each criterion (column, ascending, weight):
      Step A — rank all rows by the column value
      Step B — multiply rank position × weight
      Step C — sum all weighted ranks = Score

    Step D — sort ascending (lowest score = best).

    Columns that are missing or entirely null are gracefully skipped.
    """
    df_r = df_in.copy()
    df_r['_score'] = 0.0
    for col, asc, weight in criteria:
        if col not in df_r.columns or df_r[col].isna().all():
            continue  # gracefully skip missing / all-null columns
        # Step A: individual rank
        rank_col = df_r[col].rank(ascending=asc, na_option='bottom')
        # Step B: multiply by weight
        df_r['_score'] += rank_col * weight
    # Step D: sort ascending
    return df_r.sort_values('_score', ascending=True)


@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request, "title": "Ações", "user": user
    })

@router.get("/api/data")
async def get_acoes_data(
    market: str = None,
    min_liq: float = 0,
    filter_units: bool = False,
    filter_risky: bool = False,
    strategy: str = 'magic'
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
            'div_pat', 'cagr_lucros', 'liq_corrente', 'queda_maximo'
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

            # Require non-null columns (if specified)
            require_cols = preset.get('require_cols', [])
            if require_cols:
                df_r = df_r.dropna(subset=require_cols)

            # Filter positive values (if specified)
            filter_pos = preset.get('filter_positive', [])
            for col in filter_pos:
                if col in df_r.columns:
                    df_r = df_r[df_r[col].fillna(0) > 0]

            # Sector exclusions (for MagicLucros)
            exclude_sectors = preset.get('exclude_sectors', [])
            if exclude_sectors:
                df_r = df_r[~df_r['setor'].fillna('').isin(exclude_sectors)]

            # GreenBla: filter to below-median liquidity
            if preset.get('liquidity_filter') == 'below_median':
                median_liq = df_universe['liquidezmediadiaria'].median()
                df_small = df_r[df_r['liquidezmediadiaria'].fillna(0) <= median_liq]
                if len(df_small) >= 10:
                    df_r = df_small

            # ── Execute the weighted-rank algorithm ─────────────────────
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