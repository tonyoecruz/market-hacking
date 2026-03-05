"""
Scope Router — Habit-Based Daily Investment Recommender
=======================================================
Helps users build a daily investing habit by recommending the single best
asset (Acao or FII) they can buy TODAY with whatever budget they have.

Logic:
  1. Load all stocks (BR) + FIIs from DB
  2. Filter: price <= user budget  (must be able to buy at least 1 share)
  3. Score each candidate for income + safety + momentum
  4. Return top recommendation with full technical justification
  5. Allow adding to an existing wallet or creating a new one
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
from database.db_manager import DatabaseManager
from database.queries import WalletQueries, AssetQueries
import pandas as pd
import logging
import math


def _clean(v):
    """Return None for NaN/Inf so JSONResponse doesn't choke."""
    if v is None:
        return None
    try:
        if math.isnan(v) or math.isinf(v):
            return None
    except (TypeError, ValueError):
        pass
    return v

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

db = DatabaseManager()

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
# For ACOES: income (DY) + value (Graham margin) + quality (ROIC) + safety (liquidity)
STOCK_W = {"dy": 0.35, "margem": 0.25, "roic": 0.25, "liq": 0.15}

# For FIIs: income (DY) is king, then price/value (PVP < 1), then safety (liq)
FII_W = {"dy": 0.55, "pvp_score": 0.25, "liq": 0.20}

MIN_LIQ = 100_000  # R$ 100k min daily liquidity


def _score_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise and score stock candidates."""
    df = df.copy()
    for col in ["dy", "margem", "roic", "liquidezmediadiaria", "price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Normalise 0-1 (min-max per column)
    def norm(s):
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)

    df["n_dy"]  = norm(df["dy"].clip(0))
    df["n_mg"]  = norm(df["margem"].clip(-1, 5))
    df["n_roic"]= norm(df["roic"].clip(0))
    df["n_liq"] = norm(df["liquidezmediadiaria"].clip(0))

    df["score"] = (
        STOCK_W["dy"]     * df["n_dy"]   +
        STOCK_W["margem"] * df["n_mg"]   +
        STOCK_W["roic"]   * df["n_roic"] +
        STOCK_W["liq"]    * df["n_liq"]
    ).fillna(0)
    df["asset_type"] = "Acao"
    return df


def _score_fiis(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise and score FII candidates."""
    df = df.copy()
    for col in ["dy", "pvp", "liquidezmediadiaria", "price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    def norm(s):
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)

    # PVP score: lower PVP is better (below 1 = bargain); invert
    df["pvp_inv"] = (1 / df["pvp"].replace(0, float("nan")).clip(0.1, 5)).fillna(0)
    df["n_dy"]    = norm(df["dy"].clip(0))
    df["n_pvp"]   = norm(df["pvp_inv"])
    df["n_liq"]   = norm(df["liquidezmediadiaria"].clip(0))

    df["score"] = (
        FII_W["dy"]        * df["n_dy"]  +
        FII_W["pvp_score"] * df["n_pvp"] +
        FII_W["liq"]       * df["n_liq"]
    ).fillna(0)
    df["asset_type"] = "FII"
    df["margem"] = None
    df["roic"]   = None
    df["pvp"]    = df["pvp"]
    return df


def _build_justification(row: dict) -> dict:
    """Build a human-readable technical justification dict for the winner."""
    atype = row.get("asset_type", "Ativo")
    ticker = row.get("ticker", "")
    empresa = row.get("empresa", ticker)
    dy    = _clean(row.get("dy"))    or 0
    price = _clean(row.get("price")) or 0
    pvp   = _clean(row.get("pvp"))   or 0
    roic  = _clean(row.get("roic"))  or 0
    margem= _clean(row.get("margem"))or 0

    reasons = []

    if dy and dy > 0:
        reasons.append(f"Dividend Yield de {dy:.1f}% a.a. — cada R$ investido gera renda passiva real")

    if atype == "Acao":
        if margem and margem > 0.1:
            reasons.append(f"Margem de segurança Graham de {margem*100:.0f}% — ativo negociado abaixo do valor justo calculado")
        if roic and roic > 0.1:
            reasons.append(f"ROIC de {roic*100:.0f}% — empresa eficiente no uso do capital investido")
    elif atype == "FII":
        if pvp and pvp < 1:
            reasons.append(f"P/VP de {pvp:.2f} — você está comprando R$ 1 de patrimônio por menos de R$ 1")
        elif pvp and pvp > 0:
            reasons.append(f"P/VP de {pvp:.2f} — referência para avaliar preço vs. valor patrimonial")

    if not reasons:
        reasons.append("Melhor relação risco-retorno disponível dentro do seu orçamento hoje")

    return {
        "ticker": ticker,
        "empresa": empresa,
        "asset_type": atype,
        "price": _clean(price),
        "dy": _clean(dy),
        "pvp": _clean(pvp) or None,
        "roic": _clean(roic) or None,
        "margem": _clean(margem) or None,
        "score": _clean(round(row.get("score") or 0, 4)),
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def scope_page(request: Request, user: dict = Depends(get_optional_user)):
    wallets = []
    if user:
        try:
            wallets = WalletQueries.get_wallets(user["id"]) or []
        except Exception:
            wallets = []
    return templates.TemplateResponse(
        "pages/scope.html",
        {"request": request, "user": user, "wallets": wallets}
    )


@router.get("/api/recommend")
async def recommend(budget: float = 50.0, user: dict = Depends(get_optional_user)):
    """
    Return ordered list of best buy candidates within `budget` (price <= budget).
    Returns up to 5 candidates so the UI can show a ranked list.
    """
    try:
        if budget <= 0:
            return JSONResponse({"status": "error", "message": "Informe um valor positivo."})

        # --- Load Stocks (BR) ---
        stocks_raw = db.get_stocks(market="BR", min_liq=MIN_LIQ) or []
        df_stocks = pd.DataFrame(stocks_raw) if stocks_raw else pd.DataFrame()

        # --- Load FIIs ---
        fiis_raw = db.get_fiis() or []
        df_fiis = pd.DataFrame(fiis_raw) if fiis_raw else pd.DataFrame()

        candidates = []

        if not df_stocks.empty:
            # Must have positive price and DY, and be affordable
            df_stocks["price"] = pd.to_numeric(df_stocks.get("price", 0), errors="coerce").fillna(0)
            df_stocks["dy"]    = pd.to_numeric(df_stocks.get("dy", 0),    errors="coerce").fillna(0)
            df_s = df_stocks[
                (df_stocks["price"] > 0) &
                (df_stocks["price"] <= budget) &
                (df_stocks["dy"] > 0)
            ].copy()
            if not df_s.empty:
                df_s = _score_stocks(df_s)
                candidates.append(df_s)

        if not df_fiis.empty:
            df_fiis["price"] = pd.to_numeric(df_fiis.get("price", 0), errors="coerce").fillna(0)
            df_fiis["dy"]    = pd.to_numeric(df_fiis.get("dy", 0),    errors="coerce").fillna(0)
            df_f = df_fiis[
                (df_fiis["price"] > 0) &
                (df_fiis["price"] <= budget) &
                (df_fiis["dy"] > 0)
            ].copy()
            if not df_f.empty:
                df_f = _score_fiis(df_f)
                candidates.append(df_f)

        if not candidates:
            return JSONResponse({
                "status": "empty",
                "message": f"Nenhum ativo com preço abaixo de R$ {budget:.2f} e dividendos encontrado no banco de dados.",
            })

        combined = pd.concat(candidates, ignore_index=True)
        combined = combined.sort_values("score", ascending=False).head(5)

        results = []
        for _, row in combined.iterrows():
            info = _build_justification(row.to_dict())
            dy_pct = info["dy"] or 0
            p = info["price"] or 0
            proj_monthly_per_share = round((dy_pct / 100) * p / 12, 4) if p > 0 else 0
            shares = math.floor(budget / p) if p > 0 else 0
            proj_monthly_total = round(proj_monthly_per_share * shares, 4)
            info["shares_buyable"] = shares
            info["proj_monthly_per_share"] = _clean(proj_monthly_per_share) or 0
            info["proj_monthly_total"] = _clean(proj_monthly_total) or 0
            results.append(info)

        return JSONResponse({
            "status": "success",
            "budget": budget,
            "count": len(results),
            "recommendations": results,
        })

    except Exception as e:
        logger.error(f"[scope] recommend error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})


@router.post("/api/add-to-wallet")
async def add_to_wallet(request: Request, user: dict = Depends(get_optional_user)):
    """Add a recommended asset to the user's wallet (or create new wallet)."""
    if not user:
        return JSONResponse({"status": "error", "message": "Faça login para adicionar à carteira."}, status_code=401)

    try:
        body = await request.json()
        ticker     = body.get("ticker", "").upper()
        asset_type = body.get("asset_type", "Acao")  # "Acao" | "FII"
        quantity   = int(body.get("quantity", 1))
        price      = float(body.get("price", 0))
        wallet_id  = body.get("wallet_id")  # None = create new

        if not ticker or quantity <= 0 or price <= 0:
            return JSONResponse({"status": "error", "message": "Dados inválidos."})

        # Map asset_type to DB type string
        type_map = {"Acao": "stock", "FII": "fii"}
        db_type = type_map.get(asset_type, "stock")

        # Create wallet if not provided
        if not wallet_id:
            new_wallet = WalletQueries.create_wallet(
                user_id=user["id"],
                name=f"Scope — Hábito Diário",
                description="Carteira criada automaticamente pelo módulo Scope"
            )
            wallet_id = new_wallet["id"] if new_wallet else None

        if not wallet_id:
            return JSONResponse({"status": "error", "message": "Não foi possível criar/encontrar a carteira."})

        AssetQueries.add_asset(
            wallet_id=wallet_id,
            ticker=ticker,
            asset_type=db_type,
            quantity=quantity,
            avg_price=price,
        )

        return JSONResponse({
            "status": "success",
            "message": f"{ticker} adicionado à carteira com sucesso!",
            "wallet_id": wallet_id,
        })

    except Exception as e:
        logger.error(f"[scope] add-to-wallet error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})
