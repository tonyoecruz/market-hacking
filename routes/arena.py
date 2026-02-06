"""
Arena Routes - Asset comparison and battle
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.auth import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def arena_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Render Arena page
    """
    return templates.TemplateResponse(
        "pages/arena.html",
        {
            "request": request,
            "user": user
        }
    )


@router.post("/api/battle")
async def battle_assets(
    ticker1: str,
    ticker2: str,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    API endpoint to compare two assets
    TODO: Implement asset comparison
    """
    return {
        "ticker1": ticker1.upper(),
        "ticker2": ticker2.upper(),
        "winner": None,
        "message": "Comparação em desenvolvimento"
    }
