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
        
        if not stocks:
            return JSONResponse({'status': 'success', 'elite': [], 'count': 0})
        
        df = pd.DataFrame(stocks)
        
        # Coerce numeric columns
        numeric_cols = ['margem', 'roic', 'magic_rank', 'price']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Elite Mix: Filtros combinados
        df_elite = df[(df['margem'] > 0) & (df['roic'] > 0.10) & (df['magic_rank'] > 0)].sort_values('magic_rank').head(10)
        
        # Replace NaN for JSON
        df_elite = df_elite.replace({float('nan'): None})
        
        return JSONResponse({'status': 'success', 'elite': df_elite.to_dict('records'), 'count': len(df_elite)})
    except Exception as e:
        print(f"ERRO API ELITE MIX: {e}")
        raise HTTPException(status_code=500, detail=str(e))