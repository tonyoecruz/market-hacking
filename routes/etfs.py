from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Shared session store
from routes.acoes import session_store

@router.get("/", response_class=HTMLResponse)
async def etfs_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página de ETFs"""
    return templates.TemplateResponse("pages/etfs.html", {
        "request": request,
        "title": "ETFs",
        "user": user
    })

@router.post("/api/scan")
async def scan_etfs(request: Request):
    """API para iniciar varredura de ETFs"""
    try:
        data = await request.json()
        selected_markets = data.get('markets', ["🇧🇷 Brasil (B3)"])
        
        df_etfs = utils.load_data_etfs_pipeline(selected_markets)
        
        if df_etfs is not None and not df_etfs.empty:
            session_id = "default"
            if session_id not in session_store:
                session_store[session_id] = {}
            
            session_store[session_id]['market_data_etfs'] = df_etfs.to_dict('records')
            session_store[session_id]['selected_markets_etfs'] = selected_markets
            
            return JSONResponse({
                'status': 'success',
                'message': f'Carregados {len(df_etfs)} ETFs',
                'count': len(df_etfs)
            })
        else:
            raise HTTPException(status_code=404, detail='Nenhum dado encontrado')
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data")
async def get_etfs_data():
    """API para obter dados de ETFs"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data_etfs' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data_etfs'])
        df_sorted = df.sort_values('liquidezmediadiaria', ascending=False).head(20)
        
        return JSONResponse({
            'status': 'success',
            'count': len(df),
            'etfs': df_sorted.to_dict('records')
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/decode/{ticker}")
async def decode_etf(ticker: str):
    """API para análise IA de um ETF"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data_etfs' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data_etfs'])
        row = df[df['ticker'] == ticker]
        
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        details = utils.get_stock_details(ticker)
        
        prompt = f"""
        ANÁLISE DE ETF: {ticker}
        Preço: R$ {row['price']:.2f}
        Liquidez Diária: R$ {row['liquidezmediadiaria']:,.0f}
        
        Forneça uma análise objetiva sobre:
        1. Objetivo do ETF e ativos subjacentes
        2. Adequação para diferentes perfis de investidor
        3. Custos (taxa de administração típica)
        4. Vantagens e desvantagens
        
        REGRAS:
        - NUNCA use "Recomendação"
        - Use termos como "Adequado para", "Interessante para"
        - Max 6 linhas
        - RODAPÉ: "Fontes: Prospecto do ETF e Regulamentação CVM."
        """
        
        analysis = utils.get_ai_generic_analysis(prompt)
        
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
        fig = utils.get_candle_chart(ticker)
        if fig:
            return JSONResponse({'status': 'success', 'chart': fig.to_json()})
        else:
            raise HTTPException(status_code=404, detail='Gráfico indisponível')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
