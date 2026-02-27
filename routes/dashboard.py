"""
Dashboard Routes - Portfolio Management & Analytics
"""
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from database.queries import WalletQueries, AssetQueries
from database.db_manager import SessionLocal
from database.orm_models import StockDB, ETFDB, FIIDB
from routes.auth import get_current_user_from_cookie

logger = logging.getLogger(__name__)

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


@router.get("/api/analytics")
async def get_analytics(
    wallet_ids: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(get_current_user_from_cookie)
):
    """
    Comprehensive analytics endpoint for user dashboard.
    Cross-references Supabase portfolio with SQLAlchemy market data.
    """
    user_id = user["id"]

    # 1. Fetch wallets and portfolio from Supabase
    wallets = WalletQueries.get_wallets(user_id)
    portfolio = AssetQueries.get_portfolio(user_id)

    # 2. Filter by wallet_ids if provided
    if wallet_ids:
        try:
            selected_ids = [int(wid) for wid in wallet_ids.split(",") if wid.strip()]
            if selected_ids:
                portfolio = [a for a in portfolio if a.get("wallet_id") in selected_ids]
        except ValueError:
            pass

    # 3. Filter by date range on created_at
    if date_from:
        try:
            df = datetime.fromisoformat(date_from)
            portfolio = [a for a in portfolio if a.get("created_at") and datetime.fromisoformat(a["created_at"].replace("Z", "+00:00").split("+")[0]) >= df]
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            portfolio = [a for a in portfolio if a.get("created_at") and datetime.fromisoformat(a["created_at"].replace("Z", "+00:00").split("+")[0]) < dt]
        except (ValueError, TypeError):
            pass

    # 4. Cross-reference with market data (batch queries)
    tickers = list(set(a["ticker"] for a in portfolio if a.get("ticker")))

    stock_map = {}
    etf_map = {}
    fii_map = {}

    if tickers:
        db = SessionLocal()
        try:
            for s in db.query(StockDB).filter(StockDB.ticker.in_(tickers)).all():
                stock_map[s.ticker] = s.to_dict()
            for e in db.query(ETFDB).filter(ETFDB.ticker.in_(tickers)).all():
                etf_map[e.ticker] = e.to_dict()
            for f in db.query(FIIDB).filter(FIIDB.ticker.in_(tickers)).all():
                fii_map[f.ticker] = f.to_dict()
        except Exception as e:
            logger.warning(f"[ANALYTICS] Market data query failed: {e}")
        finally:
            db.close()

    # 5. Build enriched asset list
    wallet_name_map = {w["id"]: w["name"] for w in wallets}
    assets_detail = []
    total_invested = 0.0
    total_current = 0.0
    total_dividends = 0.0

    # Accumulators for grouping
    class_invested = defaultdict(float)
    class_current = defaultdict(float)
    wallet_invested = defaultdict(float)
    wallet_current = defaultdict(float)
    monthly_data = defaultdict(lambda: {"invested": 0.0, "current": 0.0})

    for asset in portfolio:
        ticker = asset.get("ticker", "")
        qty = float(asset.get("quantity", 0))
        avg_price = float(asset.get("avg_price", 0))
        invested = qty * avg_price
        wid = asset.get("wallet_id")
        wname = wallet_name_map.get(wid, "Sem Carteira")

        # Classify and get current price
        current_price = avg_price  # fallback
        dy = 0.0
        classe = "Acao"

        if ticker in fii_map:
            classe = "FII"
            current_price = fii_map[ticker].get("price") or avg_price
            dy = fii_map[ticker].get("dy") or 0.0
        elif ticker in etf_map:
            classe = "ETF"
            current_price = etf_map[ticker].get("price") or avg_price
        elif ticker in stock_map:
            classe = "Acao"
            current_price = stock_map[ticker].get("price") or avg_price
            dy = stock_map[ticker].get("dy") or 0.0

        current_value = qty * current_price
        gain_pct = ((current_value - invested) / invested * 100) if invested > 0 else 0.0
        est_dividends = qty * current_price * (dy / 100) if dy > 0 else 0.0

        total_invested += invested
        total_current += current_value
        total_dividends += est_dividends

        class_invested[classe] += invested
        class_current[classe] += current_value
        wallet_invested[wname] += invested
        wallet_current[wname] += current_value

        # Monthly timeline (by created_at)
        created = asset.get("created_at", "")
        if created:
            try:
                month_key = created[:7]  # "YYYY-MM"
                monthly_data[month_key]["invested"] += invested
                monthly_data[month_key]["current"] += current_value
            except (IndexError, TypeError):
                pass

        assets_detail.append({
            "ticker": ticker,
            "classe": classe,
            "wallet_name": wname,
            "quantity": qty,
            "avg_price": round(avg_price, 2),
            "current_price": round(current_price, 2),
            "invested": round(invested, 2),
            "current_value": round(current_value, 2),
            "gain_pct": round(gain_pct, 2),
            "dy": round(dy, 2),
            "est_dividends": round(est_dividends, 2),
        })

    # Sort assets by current_value descending
    assets_detail.sort(key=lambda x: x["current_value"], reverse=True)

    # 6. Build evolucao patrimonial (cumulative timeline)
    sorted_months = sorted(monthly_data.keys())
    cumulative_invested = 0.0
    cumulative_current = 0.0
    evolucao_labels = []
    evolucao_aporte = []
    evolucao_valor = []

    for month in sorted_months:
        cumulative_invested += monthly_data[month]["invested"]
        cumulative_current += monthly_data[month]["current"]
        evolucao_labels.append(month)
        evolucao_aporte.append(round(cumulative_invested, 2))
        evolucao_valor.append(round(cumulative_current, 2))

    # 7. Build comparativo carteiras
    wallet_names = sorted(wallet_invested.keys())
    comp_investido = [round(wallet_invested[w], 2) for w in wallet_names]
    comp_atual = [round(wallet_current[w], 2) for w in wallet_names]
    comp_rent = [
        round(((wallet_current[w] - wallet_invested[w]) / wallet_invested[w] * 100) if wallet_invested[w] > 0 else 0, 2)
        for w in wallet_names
    ]

    # 8. Build distribuicao por classe
    class_order = ["Acao", "FII", "ETF"]
    dist_labels = []
    dist_valores = []
    dist_pct = []
    for c in class_order:
        val = class_current.get(c, 0)
        if val > 0:
            dist_labels.append({"Acao": "Acoes", "FII": "FIIs", "ETF": "ETFs"}.get(c, c))
            dist_valores.append(round(val, 2))
            dist_pct.append(round(val / total_current * 100, 2) if total_current > 0 else 0)

    # 9. Build performance por classe
    perf_labels = []
    perf_investido = []
    perf_atual = []
    perf_rent = []
    for c in class_order:
        inv = class_invested.get(c, 0)
        cur = class_current.get(c, 0)
        if inv > 0 or cur > 0:
            perf_labels.append({"Acao": "Acoes", "FII": "FIIs", "ETF": "ETFs"}.get(c, c))
            perf_investido.append(round(inv, 2))
            perf_atual.append(round(cur, 2))
            perf_rent.append(round(((cur - inv) / inv * 100) if inv > 0 else 0, 2))

    # 10. KPIs
    rentabilidade = round(((total_current - total_invested) / total_invested * 100) if total_invested > 0 else 0, 2)

    return {
        "kpis": {
            "patrimonio_total": round(total_current, 2),
            "total_investido": round(total_invested, 2),
            "rentabilidade_pct": rentabilidade,
            "dividendos_estimados": round(total_dividends, 2),
            "num_ativos": len(assets_detail),
        },
        "wallets": [{"id": w["id"], "name": w["name"]} for w in wallets],
        "evolucao_patrimonial": {
            "labels": evolucao_labels,
            "aporte_acumulado": evolucao_aporte,
            "valor_atual_acumulado": evolucao_valor,
        },
        "comparativo_carteiras": {
            "labels": wallet_names,
            "investido": comp_investido,
            "valor_atual": comp_atual,
            "rentabilidade_pct": comp_rent,
        },
        "distribuicao_classe": {
            "labels": dist_labels,
            "valores": dist_valores,
            "percentuais": dist_pct,
        },
        "performance_classe": {
            "labels": perf_labels,
            "investido": perf_investido,
            "valor_atual": perf_atual,
            "rentabilidade_pct": perf_rent,
        },
        "assets_detail": assets_detail,
    }


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


@router.post("/api/wallet/create")
async def create_wallet_api(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Create a new wallet via JSON"""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome da carteira é obrigatório")

    success, message = WalletQueries.create_wallet(user["id"], name)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Return the new wallet's ID
    wallets = WalletQueries.get_wallets(user["id"])
    new_wallet = next((w for w in wallets if w.get("name") == name), None)
    wallet_id = new_wallet["id"] if new_wallet else None

    return {"success": True, "message": message, "wallet_id": wallet_id}


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
    purchase_date = body.get("date", "")  # Future use: purchase date

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


@router.delete("/api/wallet/{wallet_id}")
async def delete_wallet_api(
    wallet_id: int,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Delete a wallet and all its assets"""
    success, message = WalletQueries.delete_wallet(user["id"], wallet_id)
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
