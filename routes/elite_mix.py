from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
import pandas as pd
from database.db_manager import DatabaseManager
db_instance = DatabaseManager()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def elite_mix_page(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/elite_mix.html", {"request": request, "title": "Elite Mix", "user": user})

@router.get("/api/data")
async def get_elite_mix_data(min_liq: float = 200000):
    try:
        stocks = db_instance.get_stocks(min_liq=min_liq)
        df = pd.DataFrame(stocks)
        # Elite Mix: Filtros combinados
        df_elite = df[(df['margem'] > 0) & (df['roic'] > 0.10)].sort_values('magic_rank').head(10)
        return JSONResponse({'status': 'success', 'elite': df_elite.to_dict('records')})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))