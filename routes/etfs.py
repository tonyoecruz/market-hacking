from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import os
import logging
import pandas as pd
from database.db_manager import DatabaseManager
db_instance = DatabaseManager()

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def etfs_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/etfs.html", {"request": request, "title": "ETFs", "user": user})

@router.post("/api/scan")
async def scan_etfs(request: Request):
    """Trigger ETF data scan/update"""
    try:
        from scheduler.data_updater import update_etfs
        result = update_etfs()
        return JSONResponse({
            'status': 'success',
            'message': f'ETFs atualizados com sucesso!'
        })
    except Exception as e:
        logger.error(f"Erro ao escanear ETFs: {e}", exc_info=True)
        return JSONResponse({
            'status': 'error',
            'message': f'Erro ao escanear ETFs: {str(e)}'
        }, status_code=500)

@router.get("/api/data")
async def get_etfs_data():
    try:
        etfs = db_instance.get_etfs()
        
        if not etfs:
            return JSONResponse({'status': 'success', 'etfs': []})
            
        df = pd.DataFrame(etfs)
        
        # Coerce numeric
        numeric_cols = ['liquidezmediadiaria', 'price']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df_sorted = df.sort_values('liquidezmediadiaria', ascending=False).head(20)
        
        # Replace NaN for JSON
        df_sorted = df_sorted.replace({float('nan'): None})
        
        return JSONResponse({'status': 'success', 'etfs': df_sorted.to_dict('records')})
    except Exception as e:
        print(f"ERRO API ETFS: {e}")
        raise HTTPException(status_code=500, detail=str(e))