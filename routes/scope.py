"""
Scope Router — Habit-Based Daily Investment Recommender
=======================================================
Conservative, safety-first daily investment recommendations.

Philosophy:
  SAFETY FIRST — only healthy, well-established assets pass the filters.
  Then among those, pick the best dividend payers for the user's budget.

Pipeline:
  1. Load stocks (BR) + FIIs from database
  2. HARD FILTERS — eliminate risky/unhealthy assets
  3. Score survivors on a balanced mix of safety + income
  4. Return top 5 with full technical justification
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
from database.db_manager import DatabaseManager
from database.queries import WalletQueries, AssetQueries
from modules.config import RISKY_TICKERS
import pandas as pd
import numpy as np
import logging
import math
import json

# ---------------------------------------------------------------------------
# NaN/Inf safety helpers (JSONResponse chokes on float('nan'))
# ---------------------------------------------------------------------------

def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (np.floating, np.integer)):
        v2 = float(v)
        return None if (math.isnan(v2) or math.isinf(v2)) else v2
    return v


def _safe_dict(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _safe_dict(v)
        elif isinstance(v, list):
            out[k] = [_safe_dict(i) if isinstance(i, dict) else _clean(i) for i in v]
        else:
            out[k] = _clean(v)
    return out


class _NanSafeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, (np.floating, np.integer)):
            f = float(o)
            return None if (math.isnan(f) or math.isinf(f)) else f
        if isinstance(o, np.bool_):
            return bool(o)
        return super().default(o)


def _json_response(payload: dict) -> JSONResponse:
    """Serialize safely, replacing any remaining NaN/Inf with null."""
    body = json.loads(json.dumps(payload, cls=_NanSafeEncoder))
    return JSONResponse(body)


router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)
db = DatabaseManager()

# ---------------------------------------------------------------------------
# Blacklist — tickers with known legal/financial problems
# ---------------------------------------------------------------------------
_RISKY_SET = {t.replace('.SA', '').upper() for t in RISKY_TICKERS}

# ---------------------------------------------------------------------------
# HARD FILTERS — assets MUST pass ALL of these to be considered
# ---------------------------------------------------------------------------
# Stocks
STOCK_MIN_LIQ       = 200_000   # R$ daily liquidity
STOCK_MAX_DY        = 15.0      # % — above = unsustainable or error
STOCK_MIN_DY        = 1.0       # % — must pay dividends
STOCK_MAX_PL        = 25.0      # P/L — too expensive above
STOCK_MIN_PL        = 3.0       # P/L — likely problem below
STOCK_MAX_DIV_EBITDA= 3.5       # leverage ceiling
STOCK_MIN_LIQ_CORR  = 1.0       # can pay short-term debts
STOCK_MIN_ROE       = 0.05      # 5% minimum profitability
STOCK_MIN_MARGEM_LIQ= 0.0       # not losing money

# FIIs
FII_MIN_LIQ         = 100_000
FII_MAX_DY          = 14.0
FII_MIN_DY          = 3.0
FII_MIN_PVP         = 0.70
FII_MAX_PVP         = 1.40

# ---------------------------------------------------------------------------
# SCORING — balanced safety + income (NOT income-only!)
# ---------------------------------------------------------------------------
STOCK_W = {"safety": 0.40, "income": 0.30, "value": 0.30}
FII_W   = {"safety": 0.35, "income": 0.40, "value": 0.25}


def _norm(s: pd.Series) -> pd.Series:
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)


def _filter_and_score_stocks(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    df = df.copy()

    num_cols = [
        "price", "dy", "pl", "pvp", "roic", "ev_ebit",
        "liquidezmediadiaria", "margem", "liq_corrente",
        "div_liq_ebitda", "roe", "margem_liquida", "payout",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    # --- HARD FILTERS ---
    if "ticker" in df.columns:
        df = df[~df["ticker"].str.replace(".SA", "", regex=False).str.upper().isin(_RISKY_SET)]

    df = df[(df["price"] > 0) & (df["price"] <= budget)]
    logger.info(f"[scope] Stocks after price filter (<=R${budget}): {len(df)}")
    df = df[(df["dy"] >= STOCK_MIN_DY) & (df["dy"] <= STOCK_MAX_DY)]
    logger.info(f"[scope] Stocks after DY filter ({STOCK_MIN_DY}-{STOCK_MAX_DY}%): {len(df)}")
    df = df[((df["pl"] >= STOCK_MIN_PL) & (df["pl"] <= STOCK_MAX_PL)) | (df["pl"] == 0)]
    logger.info(f"[scope] Stocks after P/L filter: {len(df)}")
    df = df[(df["liquidezmediadiaria"] >= STOCK_MIN_LIQ) | (df["liquidezmediadiaria"] == 0)]
    df = df[(df["div_liq_ebitda"] <= STOCK_MAX_DIV_EBITDA) | (df["div_liq_ebitda"] == 0)]
    df = df[(df["liq_corrente"] >= STOCK_MIN_LIQ_CORR) | (df["liq_corrente"] == 0)]
    df = df[(df["roe"] >= STOCK_MIN_ROE) | (df["roe"] == 0)]
    df = df[(df["margem_liquida"] >= STOCK_MIN_MARGEM_LIQ) | (df["margem_liquida"] == 0)]
    logger.info(f"[scope] Stocks after ALL filters: {len(df)}")

    if df.empty:
        return df

    # --- SCORING ---
    df["_debt_inv"] = (1 / df["div_liq_ebitda"].replace(0, float("nan")).clip(0.1, 10)).fillna(1)
    df["safety_score"] = (
        0.30 * _norm(df["liq_corrente"].clip(0, 10)) +
        0.30 * _norm(df["_debt_inv"]) +
        0.20 * _norm(df["margem_liquida"].clip(-0.5, 1)) +
        0.20 * _norm(df["liquidezmediadiaria"])
    ).fillna(0)

    df["income_score"] = _norm(df["dy"].clip(0)).fillna(0)

    df["value_score"] = (
        0.5 * _norm(df["margem"].clip(-1, 5)) +
        0.5 * _norm(df["roic"].clip(0, 1))
    ).fillna(0)

    df["score"] = (
        STOCK_W["safety"] * df["safety_score"] +
        STOCK_W["income"] * df["income_score"] +
        STOCK_W["value"]  * df["value_score"]
    ).fillna(0)

    df["asset_type"] = "Acao"
    return df


def _filter_and_score_fiis(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    df = df.copy()

    for col in ["price", "dy", "pvp", "liquidezmediadiaria"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    # --- HARD FILTERS ---
    if "ticker" in df.columns:
        df = df[~df["ticker"].str.replace(".SA", "", regex=False).str.upper().isin(_RISKY_SET)]

    df = df[(df["price"] > 0) & (df["price"] <= budget)]
    logger.info(f"[scope] FIIs after price filter (<=R${budget}): {len(df)}")
    df = df[(df["dy"] >= FII_MIN_DY) & (df["dy"] <= FII_MAX_DY)]
    logger.info(f"[scope] FIIs after DY filter ({FII_MIN_DY}-{FII_MAX_DY}%): {len(df)}")
    df = df[((df["pvp"] >= FII_MIN_PVP) & (df["pvp"] <= FII_MAX_PVP)) | (df["pvp"] == 0)]
    logger.info(f"[scope] FIIs after P/VP filter: {len(df)}")
    df = df[(df["liquidezmediadiaria"] >= FII_MIN_LIQ) | (df["liquidezmediadiaria"] == 0)]
    logger.info(f"[scope] FIIs after ALL filters: {len(df)}")

    if df.empty:
        return df

    # --- SCORING ---
    df["safety_score"] = _norm(df["liquidezmediadiaria"]).fillna(0)
    df["income_score"] = _norm(df["dy"].clip(0)).fillna(0)
    df["_pvp_inv"] = (1 / df["pvp"].clip(0.3, 3)).fillna(0)
    df["value_score"] = _norm(df["_pvp_inv"]).fillna(0)

    df["score"] = (
        FII_W["safety"] * df["safety_score"] +
        FII_W["income"] * df["income_score"] +
        FII_W["value"]  * df["value_score"]
    ).fillna(0)

    df["asset_type"] = "FII"
    # Fill columns that stocks have but FIIs don't
    for col in ["margem", "roic", "liq_corrente", "div_liq_ebitda", "margem_liquida", "roe", "pl"]:
        df[col] = 0
    return df


# ---------------------------------------------------------------------------
# YOLO MODE — "Faca na Caveira": no safety filters, pure DY ranking
# ---------------------------------------------------------------------------

def _yolo_score_stocks(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    df = df.copy()
    for col in ["price", "dy", "pl", "pvp", "roic", "liquidezmediadiaria",
                 "margem", "liq_corrente", "div_liq_ebitda", "roe", "margem_liquida"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    # Only basic filters: price > 0, within budget, has some DY
    df = df[(df["price"] > 0) & (df["price"] <= budget) & (df["dy"] > 0)]
    if df.empty:
        return df

    # Score = pure DY ranking (highest DY wins)
    df["score"] = _norm(df["dy"]).fillna(0)
    df["asset_type"] = "Acao"
    return df


def _yolo_score_fiis(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    df = df.copy()
    for col in ["price", "dy", "pvp", "liquidezmediadiaria"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    df = df[(df["price"] > 0) & (df["price"] <= budget) & (df["dy"] > 0)]
    if df.empty:
        return df

    df["score"] = _norm(df["dy"]).fillna(0)
    df["asset_type"] = "FII"
    for col in ["margem", "roic", "liq_corrente", "div_liq_ebitda", "margem_liquida", "roe", "pl"]:
        df[col] = 0
    return df


# ---------------------------------------------------------------------------
# Justification builder
# ---------------------------------------------------------------------------

def _build_justification(row: dict, budget: float) -> dict:
    atype  = row.get("asset_type", "Ativo")
    ticker = row.get("ticker", "")
    empresa= row.get("empresa", ticker)
    dy     = _clean(row.get("dy"))             or 0
    price  = _clean(row.get("price"))          or 0
    pvp    = _clean(row.get("pvp"))            or 0
    roic   = _clean(row.get("roic"))           or 0
    margem = _clean(row.get("margem"))         or 0
    pl     = _clean(row.get("pl"))             or 0
    liq_c  = _clean(row.get("liq_corrente"))   or 0
    debt   = _clean(row.get("div_liq_ebitda")) or 0
    m_liq  = _clean(row.get("margem_liquida")) or 0
    roe    = _clean(row.get("roe"))            or 0

    reasons = []

    # --- SAFETY reasons first ---
    if atype == "Acao":
        safety_pts = []
        if liq_c >= 1.5:
            safety_pts.append(f"Liquidez corrente de {liq_c:.1f} (boa capacidade de pagar dividas de curto prazo)")
        if 0 < debt <= 2.0:
            safety_pts.append(f"Div.Liq/EBITDA de {debt:.1f}x (endividamento controlado)")
        elif debt == 0:
            safety_pts.append("Sem endividamento liquido relevante")
        if m_liq > 0.05:
            safety_pts.append(f"Margem liquida de {m_liq*100:.0f}% (empresa lucrativa)")
        if roe > 0.10:
            safety_pts.append(f"ROE de {roe*100:.0f}% (bom retorno sobre o patrimonio)")
        if 5 <= pl <= 15:
            safety_pts.append(f"P/L de {pl:.1f} (preco justo em relacao ao lucro)")

        if safety_pts:
            reasons.append("SAUDE: " + safety_pts[0])
            for sp in safety_pts[1:2]:
                reasons.append(sp[0].upper() + sp[1:])

    elif atype == "FII":
        if 0.7 <= pvp < 1.0:
            reasons.append(f"P/VP de {pvp:.2f} — patrimonio vale mais que o preco (desconto)")
        elif pvp >= 1.0:
            reasons.append(f"P/VP de {pvp:.2f} — preco alinhado ao valor patrimonial")

    # --- INCOME ---
    if dy > 0:
        reasons.append(f"Dividend Yield de {dy:.1f}% a.a. — gera renda passiva recorrente")

    # --- VALUE ---
    if atype == "Acao":
        if margem > 0.1:
            reasons.append(f"Margem Graham de {margem*100:.0f}% — negociado abaixo do valor justo")
        if roic > 0.12:
            reasons.append(f"ROIC de {roic*100:.0f}% — empresa eficiente no uso do capital")

    if not reasons:
        reasons.append("Melhor relacao risco-retorno disponivel dentro do seu orcamento hoje")

    shares = math.floor(budget / price) if price > 0 else 0
    proj_monthly = round((dy / 100) * price / 12, 4) if price > 0 else 0

    return {
        "ticker": ticker,
        "empresa": empresa,
        "asset_type": atype,
        "price": _clean(price),
        "dy": _clean(dy),
        "pvp": _clean(pvp) or None,
        "pl": _clean(pl) or None,
        "roic": _clean(roic) or None,
        "margem": _clean(margem) or None,
        "liq_corrente": _clean(liq_c) or None,
        "div_liq_ebitda": _clean(debt) or None,
        "margem_liquida": _clean(m_liq) or None,
        "roe": _clean(roe) or None,
        "score": _clean(round(row.get("score") or 0, 4)),
        "shares_buyable": shares,
        "proj_monthly_per_share": _clean(proj_monthly) or 0,
        "proj_monthly_total": _clean(round(proj_monthly * shares, 4)) or 0,
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
async def recommend(
    budget: float = 50.0,
    yolo: bool = False,
    user: dict = Depends(get_optional_user),
):
    """
    Daily investment recommendations.
    yolo=false (default) → conservative, safety-first filters.
    yolo=true  → "Faca na Caveira" — raw DY ranking, no safety filters.
    """
    try:
        if budget <= 0:
            return _json_response({"status": "error", "message": "Informe um valor positivo."})

        candidates = []

        # Stocks (BR)
        stocks_raw = db.get_stocks(market="BR") or []
        if stocks_raw:
            df_raw = pd.DataFrame(stocks_raw)
            if yolo:
                df_s = _yolo_score_stocks(df_raw, budget)
            else:
                df_s = _filter_and_score_stocks(df_raw, budget)
            if not df_s.empty:
                candidates.append(df_s)

        # FIIs
        fiis_raw = db.get_fiis() or []
        if fiis_raw:
            df_raw = pd.DataFrame(fiis_raw)
            if yolo:
                df_f = _yolo_score_fiis(df_raw, budget)
            else:
                df_f = _filter_and_score_fiis(df_raw, budget)
            if not df_f.empty:
                candidates.append(df_f)

        if not candidates:
            msg = (
                f"Nenhum ativo com dividendos encontrado abaixo de R$ {budget:.2f}."
                if yolo else
                f"Nenhum ativo saudavel com dividendos encontrado abaixo de R$ {budget:.2f}. "
                f"Tente aumentar o valor — muitos ativos seguros custam acima de R$ 10."
            )
            return _json_response({"status": "empty", "message": msg})

        combined = pd.concat(candidates, ignore_index=True)
        combined = combined.replace([np.inf, -np.inf], np.nan).fillna(0)
        combined = combined.sort_values("score", ascending=False).head(5)

        results = []
        for _, row in combined.iterrows():
            info = _build_justification(row.to_dict(), budget)
            info = _safe_dict(info)
            results.append(info)

        return _json_response({
            "status": "success",
            "budget": float(budget),
            "mode": "yolo" if yolo else "safe",
            "count": len(results),
            "recommendations": results,
        })

    except Exception as e:
        logger.error(f"[scope] recommend error: {e}", exc_info=True)
        return _json_response({"status": "error", "message": str(e)})


@router.post("/api/add-to-wallet")
async def add_to_wallet(request: Request, user: dict = Depends(get_optional_user)):
    """Add a recommended asset to the user's wallet (or create new wallet)."""
    if not user:
        return JSONResponse(
            {"status": "error", "message": "Faca login para adicionar a carteira."},
            status_code=401
        )

    try:
        body = await request.json()
        ticker     = body.get("ticker", "").upper()
        asset_type = body.get("asset_type", "Acao")
        quantity   = int(body.get("quantity", 1))
        price      = float(body.get("price", 0))
        wallet_id  = body.get("wallet_id")

        if not ticker or quantity <= 0 or price <= 0:
            return JSONResponse({"status": "error", "message": "Dados invalidos."})

        type_map = {"Acao": "stock", "FII": "fii"}
        db_type = type_map.get(asset_type, "stock")

        if not wallet_id:
            new_wallet = WalletQueries.create_wallet(
                user_id=user["id"],
                name="Scope — Habito Diario",
                description="Carteira criada automaticamente pelo modulo Scope"
            )
            wallet_id = new_wallet["id"] if new_wallet else None

        if not wallet_id:
            return JSONResponse({"status": "error", "message": "Nao foi possivel criar/encontrar a carteira."})

        AssetQueries.add_asset(
            wallet_id=wallet_id,
            ticker=ticker,
            asset_type=db_type,
            quantity=quantity,
            avg_price=price,
        )

        return JSONResponse({
            "status": "success",
            "message": f"{ticker} adicionado a carteira com sucesso!",
            "wallet_id": wallet_id,
        })

    except Exception as e:
        logger.error(f"[scope] add-to-wallet error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})
