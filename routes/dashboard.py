"""
Dashboard Routes - Portfolio Management
"""
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from database.queries import WalletQueries, AssetQueries
from routes.auth import get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Render dashboard page with user's portfolio
    """
    # Get user's portfolio
    portfolio = AssetQueries.get_portfolio(user["id"])
    
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "portfolio": portfolio
        }
    )


@router.get("/api/portfolio")
async def get_portfolio_api(
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    API endpoint to get user's portfolio as JSON
    """
    portfolio = AssetQueries.get_portfolio(user["id"])
    
    # Calculate totals
    total_invested = sum(
        float(asset["quantity"]) * float(asset["avg_price"])
        for asset in portfolio
    )
    
    return {
        "portfolio": portfolio,
        "total_invested": total_invested,
        "asset_count": len(portfolio)
    }


@router.get("/api/wallets")
async def get_wallets_api(
    user: dict = Depends(get_current_user_from_cookie)
):
    """Get user's wallets list"""
    wallets = WalletQueries.get_wallets(user["id"])
    return {"wallets": wallets}


@router.post("/api/wallet/add")
async def add_to_wallet(
    ticker: str = Form(...),
    quantity: float = Form(...),
    price: float = Form(...),
    wallet_id: int = Form(default=1),
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Add asset to wallet
    """
    success, message = AssetQueries.add_to_wallet(
        user_id=user["id"],
        ticker=ticker.upper().strip(),
        quantity=quantity,
        price=price,
        wallet_id=wallet_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.post("/api/wallet/add-json")
async def add_to_wallet_json(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Add asset to wallet via JSON (used from analysis modals)"""
    body = await request.json()
    ticker = body.get("ticker", "").upper().strip()
    quantity = float(body.get("quantity", 1))
    price = float(body.get("price", 0))
    wallet_id = int(body.get("wallet_id", 1))

    if not ticker or price <= 0:
        raise HTTPException(status_code=400, detail="Ticker e preço são obrigatórios")

    success, message = AssetQueries.add_to_wallet(
        user_id=user["id"],
        ticker=ticker,
        quantity=quantity,
        price=price,
        wallet_id=wallet_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.put("/api/wallet/edit")
async def edit_wallet_asset(
    ticker: str = Form(...),
    quantity: float = Form(...),
    price: float = Form(...),
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Edit asset in wallet
    """
    success, message = AssetQueries.update_asset(
        user_id=user["id"],
        ticker=ticker.upper().strip(),
        quantity=quantity,
        price=price
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.delete("/api/wallet/remove/{ticker}")
async def remove_from_wallet(
    ticker: str,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Remove asset from wallet
    """
    success, message = AssetQueries.remove_asset(
        user_id=user["id"],
        ticker=ticker.upper().strip()
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}
