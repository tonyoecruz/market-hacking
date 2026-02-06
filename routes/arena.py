from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import os
import importlib.util
from database.db_manager import DatabaseManager
db_instance = DatabaseManager()

spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/api/battle")
async def battle(request: Request):
    data = await request.json()
    t1, t2 = data.get('ticker1', '').upper(), data.get('ticker2', '').upper()
    
    # Busca em todos os mercados no banco
    asset1 = db_instance.get_stock_by_ticker(t1, 'BR') or db_instance.get_stock_by_ticker(t1, 'US')
    asset2 = db_instance.get_stock_by_ticker(t2, 'BR') or db_instance.get_stock_by_ticker(t2, 'US')
    
    if not asset1 or not asset2:
        raise HTTPException(status_code=404, detail="Ativos não encontrados no banco.")
    
    analysis = data_utils.get_battle_analysis(t1, str(asset1), t2, str(asset2))
    return JSONResponse({'status': 'success', 'analysis': analysis})