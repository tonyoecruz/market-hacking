from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os
import pandas as pd
import logging
import importlib.util

# Import data utilities
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

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
async def get_acoes_data(market: str = None, min_liq: float = 200000, filter_units: bool = False):
    try:
        stocks = db.get_stocks(market=market, min_liq=min_liq)
        if not stocks:
            return JSONResponse({
                'status': 'success',
                'total_count': 0,
                'graham': [],
                'magic': [],
                'all_stocks': []
            })
        
        df = pd.DataFrame(stocks)
        
        # Force numeric columns
        numeric_cols = ['liquidezmediadiaria', 'lpa', 'vpa', 'margem', 'magic_rank', 
                        'price', 'valor_justo', 'roic', 'ev_ebit', 'pl', 'pvp', 'dy']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Liquidity filter
        df_filtered = df[df['liquidezmediadiaria'].fillna(0) > min_liq].copy()
        
        if filter_units:
            df_filtered = df_filtered[df_filtered['ticker'].str.endswith('11')]
        
        # Graham: LPA > 0, VPA > 0 (sorted by margin descending - biggest bargain first)
        df_graham = df_filtered[
            (df_filtered['lpa'].fillna(0) > 0) & 
            (df_filtered['vpa'].fillna(0) > 0)
        ].sort_values('margem', ascending=False).head(10)
        
        # Magic Formula: magic_rank must exist and be > 0
        df_magic = df_filtered.dropna(subset=['magic_rank'])
        df_magic = df_magic[df_magic['magic_rank'] > 0].sort_values('magic_rank', ascending=True).head(10)
        
        # All stocks (sorted by liquidity, top 200 for performance)
        df_all = df_filtered.sort_values('liquidezmediadiaria', ascending=False).head(200)
        
        # NaN safety for JSON serialization
        df_graham = df_graham.replace({float('nan'): None})
        df_magic = df_magic.replace({float('nan'): None})
        df_all = df_all.replace({float('nan'): None})

        return JSONResponse({
            'status': 'success',
            'total_count': len(df_filtered),
            'graham': df_graham.to_dict('records'),
            'magic': df_magic.to_dict('records'),
            'all_stocks': df_all.to_dict('records')
        })
    except Exception as e:
        logger.error(f"ERRO API ACOES: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/decode/{ticker}")
async def decode_acao(ticker: str, market: str = 'BR'):
    try:
        stock = db.get_stock_by_ticker(ticker, market)
        if not stock:
            # Try the other market
            other = 'US' if market == 'BR' else 'BR'
            stock = db.get_stock_by_ticker(ticker, other)
        
        if not stock: 
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
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
        
        # AI Analysis with Graham/Magic context
        analysis = data_utils.get_sniper_analysis(
            ticker, 
            price, 
            valor_justo, 
            details,
            graham_ok=graham_ok,
            magic_ok=magic_ok
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