"""
Fixed Income (Renda Fixa) Routes
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user_from_cookie
from database.queries import WalletQueries, AssetQueries
from modules.fixed_income import FixedIncomeManager

router = APIRouter(prefix="/renda-fixa", tags=["renda-fixa"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def renda_fixa_page(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Render Fixed Income page"""
    wallets = WalletQueries.get_wallets(user["id"])
    return templates.TemplateResponse(
        "pages/renda_fixa.html",
        {
            "request": request,
            "user": user,
            "wallets": wallets,
            "page_title": "Renda Fixa"
        }
    )

@router.get("/api/top-opportunities")
async def get_top_opportunities(
    user: dict = Depends(get_current_user_from_cookie)
):
    """Get Top 10 Fixed Income opportunities"""
    opportunities = FixedIncomeManager.get_top_opportunities()
    return {"opportunities": opportunities}

@router.post("/api/add")
async def add_fixed_income_asset(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Add Fixed Income asset to wallet with specific yield metadata"""
    body = await request.json()
    
    # Extract fields
    product_type = body.get("type", "CDB") # CDB, LCI, LCA
    issuer = body.get("issuer", "Banco")
    
    # Construct a "Ticker" for internal tracking if not provided
    # e.g. "CDB-MASTER-130"
    ticker = body.get("ticker")
    if not ticker:
        ticker = f"{product_type}-{issuer[:10].upper().replace(' ', '')}"
    
    quantity = float(body.get("quantity", 1)) # Usually 1 for Fixed Income, value is in price
    invested_value = float(body.get("value", 0)) 
    
    # If qty is 1, price = invested_value. If user inputs "Quantity", then avg_price is unit price.
    # Logic: Renda Fixa usually works by "Amount Invested". So we set Quantity=1, Price=Amount.
    # UNLESS the user explicitly wants to track quantity.
    # Let's assume standard: User inputs "Valor Investido".
    if quantity == 1 and invested_value > 0:
        price = invested_value
    else:
        price = invested_value / quantity if quantity > 0 else 0

    wallet_id = int(body.get("wallet_id", 1))
    
    # Yield Data
    pct_cdi = float(body.get("pct_cdi", 0))
    pct_pre = float(body.get("pct_pre", 0))
    
    # Interpret 0 logic as requested:
    # "Se o usuário não escrever nada ficará sempre 100% do CDI"
    # "ou ele pode zerar um dos dois"
    # This logic is handled in frontend to send proper values, but we double check here.
    if pct_cdi == 0 and pct_pre == 0:
        pct_cdi = 100.0
        
    metadata = {
        "yield_type": "hybrid" if (pct_cdi > 0 and pct_pre > 0) else ("CDI" if pct_cdi > 0 else "PRE"),
        "pct_cdi": pct_cdi,
        "pct_pre": pct_pre,
        "issuer": issuer,
        "product_type": product_type,
        "maturity_date": body.get("maturity_date")
    }
    
    success, message = AssetQueries.add_to_wallet(
        user_id=user["id"],
        ticker=ticker,
        quantity=quantity,
        price=price,
        wallet_id=wallet_id,
        metadata=metadata
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {"success": True, "message": message}
