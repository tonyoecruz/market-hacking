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
        stocks = db.get_stocks(market=market, min_liq=min_liq)
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
                df[col] = float('nan')  # ensure column always exists

        # Derived field: ROE = LPA / VPA  (computed locally)
        df['roe'] = df['lpa'] / df['vpa'].replace(0, float('nan'))

        # Base filter: price > 0
        df_base = df[df['price'].fillna(0) > 0].copy()

        # Liquidity filter
        if min_liq > 0:
            df_base = df_base[df_base['liquidezmediadiaria'].fillna(0) >= min_liq].copy()

        if filter_units:
            df_base = df_base[df_base['ticker'].str.endswith('11')]

        if filter_risky:
            df_base = data_utils.filter_risky_stocks(df_base)

        # ── Weighted combined-rank helper ────────────────────────────────────────
        # criteria = list of (column, ascending, weight)
        #   ascending=True  → Menor (lowest value = rank 1)
        #   ascending=False → Maior (highest value = rank 1)
        #   weight          → multiplier for each criterion's rank
        # Weights from spreadsheet image:
        #   EV/EBIT=21  ROIC=30  CAGR=35  P/L=14  P/VP=15
        #   Liq.Corrente=27  ROE=28  Div.Liq./Patri=23  DY=13  QuedaMax=12
        def combined_rank(df_in, criteria):
            """Weighted sum of pandas ranks. Lowest total = best rank."""
            df_r = df_in.copy()
            df_r['_rank_total'] = 0.0
            for col, asc, weight in criteria:
                if col not in df_r.columns or df_r[col].isna().all():
                    continue  # gracefully skip missing/all-null columns
                df_r['_rank_total'] += df_r[col].rank(ascending=asc, na_option='bottom') * weight
            return df_r.sort_values('_rank_total', ascending=True)

        # ── Sector exclusions for MagicLucros ──────────────────────────────────
        EXCLUDE_SECTORS = [
            'Utilidade Pública', 'Utility', 'Energia Elétrica',
            'Financeiro', 'Bancos', 'Seguros', 'Previdência e Seguros',
            'Intermediários Financeiros', 'Serviços Financeiros',
        ]

        # ── 8 strategies ───────────────────────────────────────────────────────

        if strategy == 'magic':
            # EV/EBIT Menor×21  +  ROIC Maior×30
            df_r = df_base.dropna(subset=['ev_ebit', 'roic'])
            df_r = df_r[(df_r['ev_ebit'] > 0) & (df_r['roic'] > 0)]
            df_ranked = combined_rank(df_r, [
                ('ev_ebit', True,  21),
                ('roic',    False, 30),
            ]).head(100)

        elif strategy == 'magic_lucros':
            # D28(ROIC) + D37(EV/EBIT) + D42(CAGR) — exclude Util. Pública & Financeiro
            # Re-rank within filtered set (cagr adds a dimension not in magic_rank)
            df_r = df_base.dropna(subset=['ev_ebit', 'roic'])
            df_r = df_r[(df_r['ev_ebit'] > 0) & (df_r['roic'] > 0)]
            df_r = df_r[~df_r['setor'].fillna('').isin(EXCLUDE_SECTORS)]
            df_ranked = combined_rank(df_r, [
                ('ev_ebit',    True,  21),
                ('roic',       False, 30),
                ('cagr_lucros', False, 35),  # gracefully skipped if not in DB
            ]).head(100)

        elif strategy == 'baratas':
            # D19(Queda Máximo) + D21(P/L) + D22(P/VP)
            df_r = df_base.dropna(subset=['pl', 'pvp'])
            df_r = df_r[df_r['pl'] > 0]
            df_ranked = combined_rank(df_r, [
                ('queda_maximo', False, 12),  # gracefully skipped if not in DB
                ('pl',           True,  14),
                ('pvp',          False, 15),
            ]).head(100)

        elif strategy == 'solidas':
            # D30(Liq.Corrente) + D34(Div.Liq./Patri.) + D42(CAGR)
            df_r = df_base.dropna(subset=['div_pat'])
            df_ranked = combined_rank(df_r, [
                ('liq_corrente', False, 27),
                ('div_pat',      True,  23),
                ('cagr_lucros',  False, 35),
            ]).head(100)

        elif strategy == 'mix':
            # D21(P/L) + D22(P/VP) + D34(Div.Liq./Patri. or ROE?) + D35(ROE) + D42(CAGR)
            df_r = df_base.dropna(subset=['pl', 'pvp'])
            df_r = df_r[df_r['pl'] > 0]
            df_ranked = combined_rank(df_r, [
                ('pl',           True,  14),
                ('pvp',          False, 15),
                ('liq_corrente', False, 27),
                ('roe',          False, 28),
                ('cagr_lucros',  False, 35),
            ]).head(100)

        elif strategy == 'dividendos':
            # D20(DY) + D42(CAGR)
            df_r = df_base.dropna(subset=['dy'])
            df_r = df_r[df_r['dy'] > 0]
            df_ranked = combined_rank(df_r, [
                ('dy',          False, 13),
                ('cagr_lucros', False, 35),
            ]).head(100)

        elif strategy == 'graham':
            # D21(P/L) + D22(P/VP) — no D28/D37/D42
            df_r = df_base.dropna(subset=['pl', 'pvp'])
            df_r = df_r[(df_r['pl'] > 0) & (df_r['pvp'] > 0)]
            df_ranked = combined_rank(df_r, [
                ('dy',  False, 13),
                ('pl',  True,  14),
                ('pvp', False, 15),
            ]).head(100)

        elif strategy == 'greenblatt':
            # ✅ Same as Magic (D28+D37) but applied to LESS liquid companies
            # Use magic_rank for consistency; filter to below-median liquidity
            df_r = df_base.dropna(subset=['ev_ebit', 'roic'])
            df_r = df_r[(df_r['ev_ebit'] > 0) & (df_r['roic'] > 0)]
            median_liq = df_base['liquidezmediadiaria'].median()
            df_small = df_r[df_r['liquidezmediadiaria'].fillna(0) <= median_liq]
            if len(df_small) < 10:
                df_small = df_r
            df_ranked = combined_rank(df_small, [
                ('ev_ebit', True,  21),
                ('roic',    False, 30),
            ]).head(100)

        else:
            df_ranked = df_base.sort_values('liquidezmediadiaria', ascending=False).head(100)

        # ── Drop internal rank & temp columns ──────────────────────────────────
        for drop_col in ['_rank_total', 'roe']:
            if drop_col in df_ranked.columns:
                df_ranked = df_ranked.drop(columns=[drop_col])


        df_ranked = df_ranked.replace({float('nan'): None})

        return JSONResponse({
            'status': 'success',
            'total_count': len(df_base),
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
        # Simplify for autocomplete
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
            # Try the other market
            other = 'US' if market == 'BR' else 'BR'
            stock = db.get_stock_by_ticker(ticker, other)

        if not stock:
            raise HTTPException(status_code=404, detail='Ticker nao encontrado')

        # Get additional details from Fundamentus
        details = data_utils.get_stock_details(ticker)

        # Determine Graham/Magic pass status for AI analysis
        price = stock.get('price', 0) or 0
        valor_justo = stock.get('valor_justo', 0) or 0
        graham_ok = valor_justo > price if price > 0 else False
        magic_rank = stock.get('magic_rank')
        magic_ok = magic_rank is not None and magic_rank > 0 and magic_rank <= 50

        # Merge empresa from details if not in stock
        if details.get('Empresa') and not stock.get('empresa'):
            stock['empresa'] = details.get('Empresa')

        # Fetch investor style_prompt if specified
        investor_style_prompt = None
        if investor:
            inv = db.get_investor_by_name(investor)
            if inv and inv.get('style_prompt'):
                investor_style_prompt = inv['style_prompt']

        # AI Analysis with Graham/Magic context
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