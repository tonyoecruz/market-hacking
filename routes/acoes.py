from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os
import pandas as pd
import importlib.util

# Import data utilities
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

# CORREÇÃO: Importar a Classe DatabaseManager em vez da variável conflitante
from database.db_manager import DatabaseManager

router = APIRouter()
templates = Jinja2Templates(directory="templates")
db = DatabaseManager() # Instância para uso nas rotas

@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request, "title": "Ações", "user": user
    })

@router.get("/api/data")
async def get_acoes_data(market: str = None, min_liq: float = 200000, filter_units: bool = False):
    try:
        # Usa o método get_stocks da instância db
        stocks = db.get_stocks(market=market, min_liq=min_liq)
        if not stocks:
            raise HTTPException(status_code=404, detail='Dados não encontrados. Aguarde atualização.')
        
        df = pd.DataFrame(stocks)
        df_filtered = df[df['liquidezmediadiaria'] > min_liq].copy()
        if filter_units:
            df_filtered = df_filtered[df_filtered['ticker'].str.endswith('11')]
        
        df_graham = df_filtered[(df_filtered['lpa']>0) & (df_filtered['vpa']>0)].sort_values('margem', ascending=False).head(10)
        df_magic = df_filtered.dropna(subset=['magic_rank']).sort_values('magic_rank', ascending=True).head(10)
        
        return JSONResponse({
            'status': 'success',
            'graham': df_graham.to_dict('records'),
            'magic': df_magic.to_dict('records')
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/decode/{ticker}")
async def decode_acao(ticker: str, market: str = 'BR'):
    try:
        stock = db.get_stock_by_ticker(ticker, market)
        if not stock: raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        details = data_utils.get_stock_details(ticker)
        graham_ok = stock.get('lpa', 0) > 0 and stock.get('vpa', 0) > 0 and stock.get('margem', 0) > 0
        magic_ok = stock.get('magic_rank') is not None and stock.get('magic_rank') <= 100
        
        analysis = data_utils.get_sniper_analysis(ticker, stock.get('price', 0), stock.get('valor_justo', 0), details, graham_ok, magic_ok)
        return JSONResponse({'status': 'success', 'analysis': analysis, 'data': stock})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))