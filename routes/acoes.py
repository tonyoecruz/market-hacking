from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os
import pandas as pd

# Import data utilities
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

# Import database manager
from database.db_manager import db_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página de Ações"""
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request,
        "title": "Ações",
        "user": user
    })


@router.get("/api/data")
async def get_acoes_data(market: str = None, min_liq: float = 200000, filter_units: bool = False):
    """API para obter dados de ações do banco de dados (atualizado automaticamente a cada hora)"""
    try:
        # Get stocks from database
        stocks = db_manager.get_stocks(market=market, min_liq=min_liq)
        
        if not stocks:
            raise HTTPException(status_code=404, detail='Nenhum dado encontrado. Aguarde a atualização automática.')
        
        df = pd.DataFrame(stocks)
        
        # Apply filters
        df_filtered = df[df['liquidezmediadiaria'] > min_liq].copy()
        
        if filter_units:
            df_filtered = df_filtered[df_filtered['ticker'].str.endswith('11')]
        
        # Get Graham selection (top 10)
        df_graham = df_filtered[(df_filtered['lpa']>0) & (df_filtered['vpa']>0)].sort_values('margem', ascending=False)
        df_graham = data_utils.filter_risky_stocks(df_graham).head(10)
        
        # Get Magic selection (top 10)
        df_magic = df_filtered.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True)
        df_magic = data_utils.filter_risky_stocks(df_magic).head(10)
        
        return JSONResponse({
            'status': 'success',
            'total_count': len(df),
            'filtered_count': len(df_filtered),
            'graham': df_graham.to_dict('records'),
            'magic': df_magic.to_dict('records')
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/decode/{ticker}")
async def decode_acao(ticker: str, market: str = 'BR'):
    """API para análise IA de uma ação"""
    try:
        # Get stock from database
        stock = db_manager.get_stock_by_ticker(ticker, market)
        
        if not stock:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        # Get additional details
        details = data_utils.get_stock_details(ticker)
        
        # Check if passes Graham and Magic
        graham_ok = stock.get('lpa', 0) > 0 and stock.get('vpa', 0) > 0 and stock.get('margem', 0) > 0
        magic_ok = stock.get('MagicRank') is not None and stock.get('MagicRank') <= 100
        
        # Get AI analysis
        analysis = data_utils.get_sniper_analysis(
            ticker,
            stock.get('price', 0),
            stock.get('valor_justo', 0),
            details,
            graham_ok,
            magic_ok
        )
        
        return JSONResponse({
            'status': 'success',
            'ticker': ticker,
            'details': details,
            'analysis': analysis,
            'data': stock,
            'graham_ok': graham_ok,
            'magic_ok': magic_ok
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/chart/{ticker}")
async def get_chart(ticker: str):
    """API para obter dados do gráfico"""
    try:
        fig = data_utils.get_candle_chart(ticker)
        if fig:
            return JSONResponse({'status': 'success', 'chart': fig.to_json()})
        else:
            raise HTTPException(status_code=404, detail='Gráfico indisponível')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/graham/{ticker}")
async def get_graham_analysis(ticker: str, market: str = 'BR'):
    """API para análise Graham detalhada"""
    try:
        stock = db_manager.get_stock_by_ticker(ticker, market)
        
        if not stock:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        analysis = data_utils.get_graham_analysis(
            ticker,
            stock.get('price', 0),
            stock.get('valor_justo', 0),
            stock.get('lpa', 0),
            stock.get('vpa', 0)
        )
        
        return JSONResponse({
            'status': 'success',
            'ticker': ticker,
            'analysis': analysis,
            'data': stock
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/magic/{ticker}")
async def get_magic_analysis(ticker: str, market: str = 'BR'):
    """API para análise Magic Formula detalhada"""
    try:
        stock = db_manager.get_stock_by_ticker(ticker, market)
        
        if not stock:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        analysis = data_utils.get_magic_analysis(
            ticker,
            stock.get('ev_ebit', 0),
            stock.get('roic', 0),
            stock.get('MagicRank', 999)
        )
        
        return JSONResponse({
            'status': 'success',
            'ticker': ticker,
            'analysis': analysis,
            'data': stock
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
