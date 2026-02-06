from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import os
import pandas as pd
import importlib.util

spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

from database.db_manager import DatabaseManager
db_instance = DatabaseManager()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def fiis_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/fiis.html", {"request": request, "title": "FIIs", "user": user})

@router.get("/api/data")
async def get_fiis_data(min_dy: float = 0.0, min_liq: float = 100000):
    try:
        fiis = db_instance.get_fiis(min_dy=min_dy)
        df = pd.DataFrame(fiis)
        df_filtered = df[df['liquidezmediadiaria'] >= min_liq].copy()
        top_dy = df_filtered.sort_values('dy', ascending=False).head(10)
        
        return JSONResponse({'status': 'success', 'top_dy': top_dy.to_dict('records')})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))