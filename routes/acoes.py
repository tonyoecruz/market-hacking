from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# In-memory session storage (replace with Redis or database in production)
session_store = {}

@router.get("/", response_class=HTMLResponse)
async def acoes_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página de Ações"""
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request,
        "title": "Ações",
        "user": user
    })

@router.post("/api/scan")
async def scan_acoes(request: Request):
    """API para iniciar varredura de ações"""
    try:
        data = await request.json()
        selected_markets = data.get('markets', ["🇧🇷 Brasil (B3)"])
        
        # Load data using pipeline
        df_acoes = utils.load_data_acoes_pipeline(selected_markets)
        
        if df_acoes is not None and not df_acoes.empty:
            # Store in session (use session ID from cookie in production)
            session_id = "default"  # Replace with actual session management
            if session_id not in session_store:
                session_store[session_id] = {}
            
            session_store[session_id]['market_data'] = df_acoes.to_dict('records')
            session_store[session_id]['selected_markets'] = selected_markets
            
            return JSONResponse({
                'status': 'success',
                'message': f'Carregados {len(df_acoes)} ativos',
                'count': len(df_acoes)
            })
        else:
            raise HTTPException(status_code=404, detail='Nenhum dado encontrado')
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data")
async def get_acoes_data(min_liq: float = 200000, filter_units: bool = False):
    """API para obter dados de ações"""
    try:
        session_id = "default"  # Replace with actual session management
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados. Execute a varredura primeiro.')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        
        # Apply filters
        df_filtered = df[df['liquidezmediadiaria'] > min_liq].copy()
        
        if filter_units:
            df_filtered = df_filtered[df_filtered['ticker'].str.endswith('11')]
        
        # Get Graham selection (top 10)
        df_graham = df_filtered[(df_filtered['lpa']>0) & (df_filtered['vpa']>0)].sort_values('Margem', ascending=False)
        df_graham = utils.filter_risky_stocks(df_graham).head(10)
        
        # Get Magic selection (top 10)
        df_magic = df_filtered.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True)
        df_magic = utils.filter_risky_stocks(df_magic).head(10)
        
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
async def decode_acao(ticker: str):
    """API para análise IA de uma ação"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        
        # Find ticker
        row = df[df['ticker'] == ticker]
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        
        # Get stock details
        details = utils.get_stock_details(ticker)
        
        # Check methods
        graham_ok = row['Margem'] > 0
        magic_ok = (row['roic'] > 0.10) and (row['ev_ebit'] > 0)
        
        # Get AI analysis
        analysis = utils.get_sniper_analysis(
            ticker,
            row['price'],
            row['ValorJusto'],
            details,
            graham_ok,
            magic_ok
        )
        
        # Check if critical
        is_critical = "[CRITICAL]" in analysis
        display_text = analysis.replace("[CRITICAL]", "").strip()
        
        return JSONResponse({
            'status': 'success',
            'ticker': ticker,
            'details': details,
            'graham_ok': bool(graham_ok),
            'magic_ok': bool(magic_ok),
            'analysis': display_text,
            'is_critical': is_critical,
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
            return JSONResponse({
                'status': 'success',
                'chart': fig.to_json()
            })
        else:
            raise HTTPException(status_code=404, detail='Gráfico indisponível')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/graham/{ticker}")
async def graham_analysis(ticker: str):
    """API para análise Graham"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        row = df[df['ticker'] == ticker]
        
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        
        analysis = utils.get_graham_analysis(
            ticker,
            row['price'],
            row['ValorJusto'],
            row['lpa'],
            row['vpa']
        )
        
        return JSONResponse({
            'status': 'success',
            'analysis': analysis,
            'data': {
                'lpa': float(row['lpa']),
                'vpa': float(row['vpa']),
                'valor_justo': float(row['ValorJusto']),
                'margem': float(row['Margem'])
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/magic/{ticker}")
async def magic_analysis(ticker: str):
    """API para análise Magic Formula"""
    try:
        session_id = "default"
        
        if session_id not in session_store or 'market_data' not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Dados não carregados')
        
        df = pd.DataFrame(session_store[session_id]['market_data'])
        row = df[df['ticker'] == ticker]
        
        if row.empty:
            raise HTTPException(status_code=404, detail='Ticker não encontrado')
        
        row = row.iloc[0]
        
        analysis = utils.get_magic_analysis(
            ticker,
            row['ev_ebit'],
            row['roic'],
            int(row.get('Score', 0))
        )
        
        return JSONResponse({
            'status': 'success',
            'analysis': analysis,
            'data': {
                'ev_ebit': float(row['ev_ebit']),
                'roic': float(row['roic']),
                'score': int(row.get('Score', 0)),
                'rank': int(row.get('MagicRank', 0))
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))