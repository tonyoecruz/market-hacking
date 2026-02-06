"""
ETFs Routes - Exchange Traded Funds Analysis
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.auth import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def etfs_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Render ETFs analysis page
    """
    return templates.TemplateResponse(
        "pages/etfs.html",
        {
            "request": request,
            "user": user
        }
    )


@router.get("/api/list")
async def list_etfs(
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    API endpoint to list available ETFs
    TODO: Implement ETF listing
    """
    return {
        "etfs": [],
        "message": "Listagem em desenvolvimento"
    }
