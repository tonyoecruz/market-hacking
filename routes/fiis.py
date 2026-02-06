from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os

# Import data utilities
import importlib.util
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="templates")

from routes.acoes import session_store

@router.get("/", response_class=HTMLResponse)
async def fiis_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página de FIIs"""
    return templates.TemplateResponse("pages/fiis.html", {
        "request": request,
        "title": "FIIs",
        "user": user
    })

@router.post("/api/scan")
async def scan_fiis(request: Request):
    """API para iniciar varredura de FIIs"""
    try:
        data = await request.json()
        selected_markets = data.get('markets', ["🇧🇷 Brasil (B3)"])
        
        df_fiis = data_utils.load_data_fiis_pipeline(selected_markets)
        
        if df_fiis is not None and not df_fiis.empty:
            session_id = "default"
            if session_id not in session_store:
                session_store[session_id] = {}
            
            session_store[session_id]['fiis_data'] = df_fiis.to_dict('records')
            session_store[session_id]['selected_markets_fiis'] = selected_markets
            
            return JSONResponse({
                'status': 'success',
                'message': f'Carregados {len(df_fiis)} FIIs',
                'count': len(df_fiis)
            })
        else:
            raise HTTPException(status_code=404, detail='Nenhum dado encontrado')
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data")
async def get_fiis_data(min_dy: float = 0.0, max_pvp: float = 999.0, min_liq: float = 100000):
    """API para obter dados de FIIs"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'fiis_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['fiis_data'])
        
        df_filtered = df[
            (df['dy'] >= min_dy) &
            (df['pvp'] <= max_pvp) &
            (df['liquidezmediadiaria'] >= min_liq)
        ].copy()
        
        df_top_dy = df_filtered.sort_values('dy', ascending=False).head(10)
        
        return JSONResponse({
            'status': 'success',
            'total_count': len(df),
            'filtered_count': len(df_filtered),
            'top_dy': df_top_dy.to_dict('records')
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/decode/{ticker}")
async def decode_fii(ticker: str):
    """API para análise IA de um FII"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'fiis_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['fiis_data'])
        row = df[df['ticker'] == ticker]
        
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        details = data_utils.get_stock_details(ticker)
        
        analysis = data_utils.get_fii_analysis(
            ticker,
            row['price'],
            row['pvp'],
            row['dy'],
            details
        )
        
        return JSONResponse({
            'status': 'success',
            'ticker': ticker,
            'details': details,
            'analysis': analysis,
            'data': row.to_dict()
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
