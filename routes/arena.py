from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="templates")

from routes.acoes import session_store

@router.get("/", response_class=HTMLResponse)
async def arena_page(request: Request, user: dict = Depends(get_optional_user)):
    """Página Arena"""
    return templates.TemplateResponse("pages/arena.html", {
        "request": request,
        "title": "Arena",
        "user": user
    })

@router.post("/api/battle")
async def battle(request: Request):
    """API para batalha entre dois ativos"""
    try:
        data = await request.json()
        ticker1 = data.get('ticker1', '').upper().strip()
        ticker2 = data.get('ticker2', '').upper().strip()
        
        if not ticker1 or not ticker2:
            raise HTTPException(status_code=400, detail='Dois tickers são necessários')
        
        if ticker1 == ticker2:
            raise HTTPException(status_code=400, detail='Os tickers devem ser diferentes')
        
        session_id = "default"
        df1_data = None
        df2_data = None
        
        # Check in market_data (Ações)
        if session_id in session_store and 'market_data' in session_store[session_id]:
            df = pd.DataFrame(session_store[session_id]['market_data'])
            row1 = df[df['ticker'] == ticker1]
            row2 = df[df['ticker'] == ticker2]
            
            if not row1.empty:
                df1_data = row1.iloc[0].to_dict()
            if not row2.empty:
                df2_data = row2.iloc[0].to_dict()
        
        # Check in FIIs data
        if session_id in session_store and 'fiis_data' in session_store[session_id]:
            df = pd.DataFrame(session_store[session_id]['fiis_data'])
            if df1_data is None:
                row1 = df[df['ticker'] == ticker1]
                if not row1.empty:
                    df1_data = row1.iloc[0].to_dict()
            if df2_data is None:
                row2 = df[df['ticker'] == ticker2]
                if not row2.empty:
                    df2_data = row2.iloc[0].to_dict()
        
        # Check in ETFs data
        if session_id in session_store and 'market_data_etfs' in session_store[session_id]:
            df = pd.DataFrame(session_store[session_id]['market_data_etfs'])
            if df1_data is None:
                row1 = df[df['ticker'] == ticker1]
                if not row1.empty:
                    df1_data = row1.iloc[0].to_dict()
            if df2_data is None:
                row2 = df[df['ticker'] == ticker2]
                if not row2.empty:
                    df2_data = row2.iloc[0].to_dict()
        
        if df1_data is None or df2_data is None:
            missing = []
            if df1_data is None:
                missing.append(ticker1)
            if df2_data is None:
                missing.append(ticker2)
            
            raise HTTPException(status_code=404, detail=f'Tickers não encontrados: {", ".join(missing)}')
        
        # Format data for AI
        def format_asset_data(ticker, data):
            lines = [f"TICKER: {ticker}"]
            lines.append(f"Preço: R$ {data.get('price', 0):.2f}")
            
            if 'lpa' in data and 'vpa' in data:
                lines.append(f"LPA: {data.get('lpa', 0):.2f}")
                lines.append(f"VPA: {data.get('vpa', 0):.2f}")
                lines.append(f"P/L: {data.get('pl', 0):.2f}")
                lines.append(f"P/VP: {data.get('pvp', 0):.2f}")
            
            if 'ev_ebit' in data:
                lines.append(f"EV/EBIT: {data.get('ev_ebit', 0):.2f}")
            
            if 'roic' in data:
                lines.append(f"ROIC: {data.get('roic', 0):.1%}")
            
            if 'Margem' in data:
                lines.append(f"Margem Graham: {data.get('Margem', 0):.1%}")
            
            if 'dy' in data:
                lines.append(f"Dividend Yield: {data.get('dy', 0):.1%}")
            
            if 'segmento' in data:
                lines.append(f"Segmento: {data.get('segmento', 'N/A')}")
            
            return "\n".join(lines)
        
        data1_str = format_asset_data(ticker1, df1_data)
        data2_str = format_asset_data(ticker2, df2_data)
        
        # Get AI battle analysis
        analysis = utils.get_battle_analysis(ticker1, data1_str, ticker2, data2_str)
        
        # Store analysis in session for audio generation
        battle_key = f"battle_{ticker1}_{ticker2}"
        if session_id not in session_store:
            session_store[session_id] = {}
        session_store[session_id][battle_key] = analysis
        
        # Generate audio
        audio_path = utils.generate_audio(analysis, key_suffix=battle_key)
        
        return JSONResponse({
            'status': 'success',
            'ticker1': ticker1,
            'ticker2': ticker2,
            'data1': df1_data,
            'data2': df2_data,
            'analysis': analysis,
            'audio_available': audio_path is not None and not audio_path.startswith('ERROR'),
            'audio_path': f"/arena/api/audio/{ticker1}/{ticker2}" if audio_path and not audio_path.startswith('ERROR') else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/audio/{ticker1}/{ticker2}")
async def get_audio(ticker1: str, ticker2: str):
    """API para obter áudio da batalha"""
    try:
        session_id = "default"
        battle_key = f"battle_{ticker1}_{ticker2}"
        
        if session_id not in session_store or battle_key not in session_store[session_id]:
            raise HTTPException(status_code=404, detail='Batalha não encontrada. Execute a batalha primeiro.')
        
        analysis = session_store[session_id][battle_key]
        
        # Generate audio
        audio_path = utils.generate_audio(analysis, key_suffix=battle_key)
        
        if audio_path and not audio_path.startswith('ERROR') and os.path.exists(audio_path):
            return FileResponse(audio_path, media_type='audio/mpeg')
        else:
            raise HTTPException(status_code=500, detail='Erro ao gerar áudio')
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
