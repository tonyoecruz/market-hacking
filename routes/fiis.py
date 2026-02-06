"""
FIIs Routes - Real Estate Investment Funds Analysis
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.auth import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def fiis_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Render FIIs analysis page
    """
    return templates.TemplateResponse(
        "pages/fiis.html",
        {
            "request": request,
            "user": user
        }
    )


@router.get("/api/list")
async def list_fiis(
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    API endpoint to list FIIs
    TODO: Implement FII listing and analysis
    """
    return {
        "fiis": [],
        "message": "Listagem em desenvolvimento"
    }
