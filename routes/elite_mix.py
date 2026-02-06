"""
Elite Mix Routes - Premium stocks that pass both Graham and Magic Formula
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.auth import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def elite_mix_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Render Elite Mix page
    """
    return templates.TemplateResponse(
        "pages/elite_mix.html",
        {
            "request": request,
            "user": user
        }
    )


@router.get("/api/stocks")
async def get_elite_stocks(
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    API endpoint to get elite stocks
    TODO: Implement Graham + Magic Formula filter
    """
    return {
        "stocks": [],
        "message": "Análise em desenvolvimento"
    }
