from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
from database.db_manager import DatabaseManager
import pandas as pd
import os
import logging
import importlib.util

spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")
db = DatabaseManager()

@router.get("/", response_class=HTMLResponse)
async def fiis_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/fiis.html", {"request": request, "title": "FIIs", "user": user})

@router.post("/api/scan")
async def scan_fiis(request: Request):
    """Trigger FII data scan/update"""
    try:
        from scheduler.data_updater import update_fiis
        result = update_fiis()
        return JSONResponse({
            'status': 'success',
            'message': f'FIIs atualizados com sucesso!'
        })
    except Exception as e:
        logger.error(f"Erro ao escanear FIIs: {e}", exc_info=True)
        return JSONResponse({
            'status': 'error',
            'message': f'Erro ao escanear FIIs: {str(e)}'
        }, status_code=500)

@router.get("/api/data")
async def get_fiis_data(min_dy: float = 0.0, min_liq: float = 100000):
    try:
        fiis = db.get_fiis(min_dy=min_dy)
        if not fiis:
            return JSONResponse({'status': 'success', 'message': 'Aguardando atualização de dados.', 'top_dy': []})
            
        df = pd.DataFrame(fiis)
        
        # Coerce numeric
        numeric_cols = ['liquidezmediadiaria', 'dy', 'price', 'pvp']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df_filtered = df[df['liquidezmediadiaria'] >= min_liq].copy()
        top_dy = df_filtered.sort_values('dy', ascending=False).head(10)
        
        # Replace NaN for JSON
        top_dy = top_dy.replace({float('nan'): None})
        
        return JSONResponse({'status': 'success', 'top_dy': top_dy.to_dict('records')})
    except Exception as e:
        print(f"ERRO API FIIS: {e}")
        raise HTTPException(status_code=500, detail=str(e))