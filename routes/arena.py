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

@router.get("/", response_class=HTMLResponse)
async def arena_page(request: Request):
    return templates.TemplateResponse("pages/arena.html", {"request": request, "title": "Arena"})

@router.get("/api/search")
async def arena_search(q: str = ''):
    """Search assets for arena battle autocomplete"""
    if len(q) < 1:
        return JSONResponse({'status': 'success', 'results': []})
    try:
        results = db_instance.search_assets(q, limit=10)
        simplified = [{'ticker': r.get('ticker', ''), 'empresa': r.get('empresa', ''), 
                       'market': r.get('market', ''), 'asset_type': r.get('asset_type', '')} for r in results]
        return JSONResponse({'status': 'success', 'results': simplified})
    except:
        return JSONResponse({'status': 'error', 'results': []})

@router.post("/api/battle")
async def battle(request: Request):
    data = await request.json()
    t1, t2 = data.get('ticker1', '').upper(), data.get('ticker2', '').upper()
    
    # Search across stocks, then ETFs/FIIs via search_assets
    asset1 = db_instance.get_stock_by_ticker(t1, 'BR') or db_instance.get_stock_by_ticker(t1, 'US')
    asset2 = db_instance.get_stock_by_ticker(t2, 'BR') or db_instance.get_stock_by_ticker(t2, 'US')
    
    # Fallback: search in all asset types
    if not asset1:
        results = db_instance.search_assets(t1, limit=1)
        asset1 = results[0] if results else None
    if not asset2:
        results = db_instance.search_assets(t2, limit=1)
        asset2 = results[0] if results else None
    
    if not asset1 or not asset2:
        raise HTTPException(status_code=404, detail="Ativos nao encontrados no banco.")

    # Fetch investor style_prompt if specified
    investor_style_prompt = None
    investor_name = data.get('investor', '')
    if investor_name:
        inv = db_instance.get_investor_by_name(investor_name)
        if inv and inv.get('style_prompt'):
            investor_style_prompt = inv['style_prompt']

    analysis = data_utils.get_battle_analysis(t1, str(asset1), t2, str(asset2), investor_style_prompt=investor_style_prompt)
    return JSONResponse({'status': 'success', 'analysis': analysis})