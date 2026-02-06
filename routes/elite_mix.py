from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os

# Import data utilities
import importlib.util
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="templates")

from routes.acoes import session_store

@router.get("/", response_class=HTMLResponse)
async def elite_mix_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página Elite Mix"""
    return templates.TemplateResponse("pages/elite_mix.html", {
        "request": request,
        "title": "Elite Mix",
        "user": user
    })

@router.get("/api/data")
async def get_elite_mix_data(min_liq: float = 200000):
    """API para obter dados do Elite Mix"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados. Execute a varredura em Ações primeiro.')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        df_filtered = df[df['liquidezmediadiaria'] > min_liq].copy()
        
        # ELITE MIX: Intersection of Graham AND Magic Formula
        df_elite = df_filtered[
            (df_filtered['Margem'] > 0) &
            (df_filtered['roic'] > 0.10) &
            (df_filtered['ev_ebit'] > 0)
        ].copy()
        
        df_elite = utils.filter_risky_stocks(df_elite)
        df_elite = df_elite.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True).head(10)
        
        return JSONResponse({
            'status': 'success',
            'count': len(df_elite),
            'elite': df_elite.to_dict('records')
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/decode/{ticker}")
async def decode_elite(ticker: str):
    """API para análise IA Elite Mix"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        row = df[df['ticker'] == ticker]
        
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        details = utils.get_stock_details(ticker)
        
        analysis = utils.get_mix_analysis(
            ticker,
            row['price'],
            row['ValorJusto'],
            row['ev_ebit'],
            row['roic']
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

@router.post("/api/simulate")
async def simulate_allocation(request: Request):
    """API para simular alocação de aporte"""
    try:
        data = await request.json()
        investment_amount = data.get('amount', 1000.0)
        selected_tickers = data.get('tickers', [])
        
        if not selected_tickers:
            raise HTTPException(status_code=400, detail='Nenhum ticker selecionado')
        
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        df_selected = df[df['ticker'].isin(selected_tickers)].copy()
        
        if df_selected.empty:
            raise HTTPException(status_code=404, detail='Tickers não encontrados')
        
        amount_per_asset = investment_amount / len(df_selected)
        
        allocations = []
        for _, row in df_selected.iterrows():
            qty = int(amount_per_asset / row['price']) if row['price'] > 0 else 0
            allocated = qty * row['price']
            
            allocations.append({
                'ticker': row['ticker'],
                'price': float(row['price']),
                'qty': qty,
                'allocated': float(allocated),
                'margem': float(row['Margem']),
                'roic': float(row['roic'])
            })
        
        total_allocated = sum(a['allocated'] for a in allocations)
        remaining = investment_amount - total_allocated
        
        return JSONResponse({
            'status': 'success',
            'investment_amount': investment_amount,
            'total_allocated': total_allocated,
            'remaining': remaining,
            'allocations': allocations
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chart/{ticker}")
async def get_chart(ticker: str):
    """API para obter dados do gráfico"""
    try:
        fig = utils.get_candle_chart(ticker)
        if fig:
            return JSONResponse({'status': 'success', 'chart': fig.to_json()})
        else:
            raise HTTPException(status_code=404, detail='Gráfico indisponível')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
