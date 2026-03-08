"""
Scope Router — Habit-Based Daily Investment Analysis
=====================================================
Conservative, safety-first daily asset screening tool.

Philosophy:
  SAFETY FIRST — only healthy, well-established assets pass the filters.
  Then among those, rank the best dividend payers within a given budget.

Pipeline:
  1. Load stocks (BR) + FIIs from database
  2. HARD FILTERS — eliminate risky/unhealthy assets
  3. Score survivors on a balanced mix of safety + income
  4. Return top 5 with full technical justification

Note: This is an educational screening tool, not investment advice.
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
# SCORING-BASED APPROACH — soft penalties instead of hard elimination
# ---------------------------------------------------------------------------
# Only 3 hard filters: price within budget, DY > 0, not in blacklist.
# Everything else is scored: good values earn points, bad values lose points.
# This guarantees results while still ranking safe assets at the top.
# ---------------------------------------------------------------------------

# Scoring weights — income must be meaningful, not just safe & cheap
STOCK_W = {"safety": 0.30, "income": 0.40, "value": 0.30}
FII_W   = {"safety": 0.25, "income": 0.50, "value": 0.25}


def _norm(s: pd.Series) -> pd.Series:
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.5, index=s.index)


def _penalty(val: float, ideal_min: float, ideal_max: float) -> float:
    """Return 0.0-1.0 score: 1.0 if within ideal range, tapering off outside."""
    if val == 0:
        return 0.5  # unknown data = neutral
    if ideal_min <= val <= ideal_max:
        return 1.0
    if val < ideal_min:
        return max(0.0, 1.0 - (ideal_min - val) / max(ideal_min, 1))
    # val > ideal_max
    return max(0.0, 1.0 - (val - ideal_max) / max(ideal_max, 1))


def _filter_and_score_stocks(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    """
    Conservative stock filter + scoring using Greenblatt (Magic Formula) +
    Graham (Valor Intrínseco) + Dividendos strategies.
    """
    df = df.copy()

    num_cols = [
        "price", "dy", "pl", "pvp", "roic", "ev_ebit",
        "liquidezmediadiaria", "margem", "liq_corrente",
        "div_liq_ebitda", "roe", "margem_liquida", "payout", "lpa", "vpa",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    # --- HARD FILTERS (only truly broken data) ---
    if "ticker" in df.columns:
        df = df[~df["ticker"].str.replace(".SA", "", regex=False).str.upper().isin(_RISKY_SET)]

    df = df[(df["price"] > 0) & (df["price"] <= budget)]
    df = df[df["dy"] > 0]                            # must pay some dividend
    df = df[df["dy"] <= 30]                           # DY > 30% = data error
    df = df[df["liquidezmediadiaria"] >= 50_000]      # min R$50k daily volume
    df = df[df["pl"] > 0]                             # must be profitable
    logger.info(f"[scope] Stocks after hard filters (price<={budget}): {len(df)}")

    if df.empty:
        return df

    # ── GREENBLATT / MAGIC FORMULA sub-score ──
    # Earnings Yield = 1/EV_EBIT (higher = better) + ROIC rank (higher = better)
    ey = (1.0 / df["ev_ebit"].clip(1, 999)).fillna(0)
    df["_greenblatt"] = (
        0.5 * _norm(ey) +
        0.5 * _norm(df["roic"].clip(0, 1))
    ).fillna(0)

    # ── GRAHAM sub-score ──
    # Margin of safety: VI = sqrt(22.5 * LPA * VPA), upside = VI/price - 1
    graham_t = 22.5 * df["lpa"].clip(0) * df["vpa"].clip(0)
    df["_vi"] = graham_t.apply(lambda x: math.sqrt(x) if x > 0 else 0)
    df["_graham_upside"] = ((df["_vi"] / df["price"]) - 1).clip(-1, 5)
    df["_graham"] = _norm(df["_graham_upside"]).fillna(0)

    # ── INCOME sub-score ── (Bazin-inspired: DY 6%+ is great, 10%+ outstanding)
    df["_income"] = df["dy"].apply(
        lambda v: min(1.0, v / 10.0)  # 10% DY = perfect
    ).fillna(0)

    # ── SAFETY sub-score ──
    df["_safety_pl"] = df["pl"].apply(lambda v: _penalty(v, 3.0, 15.0))
    df["_safety_debt"] = df["div_liq_ebitda"].apply(lambda v: _penalty(v, 0, 3.0))
    df["_safety_liq"] = df["liq_corrente"].apply(
        lambda v: 0.5 if v == 0 else min(1.0, v / 2.0)
    )
    df["_safety_ml"] = df["margem_liquida"].apply(
        lambda v: 0.5 if v == 0 else (1.0 if v > 0.05 else max(0.0, 0.5 + v * 5))
    )
    df["_safety_dy_ceil"] = df["dy"].apply(
        lambda v: 1.0 if v <= 12 else max(0.0, 1.0 - (v - 12) / 10)
    )

    df["safety_score"] = (
        0.25 * df["_safety_pl"] +
        0.25 * df["_safety_debt"] +
        0.20 * df["_safety_liq"] +
        0.15 * df["_safety_ml"] +
        0.15 * df["_safety_dy_ceil"]
    ).fillna(0)

    # ── COMBINED SCORE ──
    # 25% safety + 30% income + 25% Greenblatt + 20% Graham
    df["score"] = (
        0.25 * df["safety_score"] +
        0.30 * df["_income"] +
        0.25 * df["_greenblatt"] +
        0.20 * df["_graham"]
    ).fillna(0)

    df["asset_type"] = "Acao"
    logger.info(f"[scope] Stocks scored: {len(df)} candidates")
    return df


def _filter_and_score_fiis(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    """
    FII filter + scoring using Bazin (Preco Teto) + Renda Constante strategies.
    DY is normalized: values < 1 are treated as decimal (0.08 → 8%).
    """
    df = df.copy()

    for col in ["price", "dy", "pvp", "liquidezmediadiaria"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    # ── DY NORMALIZATION ──
    # FII DY may be stored as decimal (0.08 = 8%) — normalize to percentage
    df["dy"] = df["dy"].apply(lambda x: x * 100 if 0 < x < 1 else x)

    # --- HARD FILTERS (only truly broken data) ---
    if "ticker" in df.columns:
        df = df[~df["ticker"].str.replace(".SA", "", regex=False).str.upper().isin(_RISKY_SET)]

    df = df[(df["price"] > 0) & (df["price"] <= budget)]
    df = df[df["dy"] > 0]                            # must pay some dividend
    df = df[df["dy"] <= 25]                           # DY > 25% = data error or inactive fund
    df = df[df["liquidezmediadiaria"] >= 50_000]      # min R$50k daily volume
    df = df[df["pvp"] >= 0.40]                        # P/VP < 0.40 = something very wrong
    df = df[df["pvp"] <= 2.0]                         # P/VP > 2.0 = overpriced
    logger.info(f"[scope] FIIs after hard filters (price<={budget}): {len(df)}")

    if df.empty:
        return df

    # ── BAZIN sub-score (Preco Teto FII) ──
    # Uses 6% target (more standard for FIIs) instead of 8%
    # PrecoTeto = DivAnual / 0.06, margin = (PrecoTeto/Price - 1)
    dy_dec = df["dy"] / 100  # back to decimal for dividend calc
    div_anual = dy_dec * df["price"]
    df["_preco_teto"] = div_anual / 0.06
    df["_bazin_margem"] = ((df["_preco_teto"] / df["price"]) - 1).clip(-1, 5)
    df["_bazin"] = _norm(df["_bazin_margem"]).fillna(0)

    # ── RENDA CONSTANTE sub-score ──
    # Favors: P/VP 0.80-1.10 (sweet spot) + good DY (8% is already great for FII)
    df["_rc_pvp"] = df["pvp"].apply(lambda v: 1.0 if 0.80 <= v <= 1.10 else _penalty(v, 0.80, 1.10))
    df["_rc_dy"] = df["dy"].apply(lambda v: min(1.0, v / 8.0)).fillna(0)  # 8% = perfect for FII
    df["_renda_constante"] = (0.4 * df["_rc_pvp"] + 0.6 * df["_rc_dy"]).fillna(0)

    # ── QUALITY sub-score (institutional proxy) ──
    # High liquidity = institutional interest = quality signal
    # Use log scale so R$50k vs R$10M is properly distinguished
    log_liq = np.log10(df["liquidezmediadiaria"].clip(1))
    df["_quality"] = ((log_liq - 4.7) / (7.5 - 4.7)).clip(0, 1)  # 50k=0, ~30M=1

    # ── SAFETY sub-score ──
    df["_dy_ceil_score"] = df["dy"].apply(
        lambda v: 1.0 if v <= 12.0 else max(0.0, 1.0 - (v - 12.0) / 10.0)
    )
    df["_pvp_score"] = df["pvp"].apply(
        lambda v: 0.5 if v == 0 else _penalty(v, 0.70, 1.30)
    )
    df["safety_score"] = (
        0.35 * df["_quality"] +
        0.35 * df["_dy_ceil_score"] +
        0.30 * df["_pvp_score"]
    ).fillna(0)

    # ── COMBINED SCORE ──
    # 25% safety + 30% Renda Constante + 20% Bazin + 25% quality
    df["score"] = (
        0.25 * df["safety_score"] +
        0.30 * df["_renda_constante"] +
        0.20 * df["_bazin"] +
        0.25 * df["_quality"]
    ).fillna(0)

    df["asset_type"] = "FII"
    # Fill columns that stocks have but FIIs don't
    for col in ["margem", "roic", "liq_corrente", "div_liq_ebitda", "margem_liquida", "roe", "pl"]:
        df[col] = 0
    # Ensure setor column exists for diversification (use segmento or tipo if available)
    if "setor" not in df.columns:
        if "segmento" in df.columns:
            df["setor"] = df["segmento"]
        elif "tipo" in df.columns:
            df["setor"] = df["tipo"]
        else:
            df["setor"] = "FII"
    logger.info(f"[scope] FIIs scored: {len(df)} candidates")
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

    # DY normalization: decimal (0.08) → percentage (8.0)
    df["dy"] = df["dy"].apply(lambda x: x * 100 if 0 < x < 1 else x)

    df = df[(df["price"] > 0) & (df["price"] <= budget) & (df["dy"] > 0)]
    if df.empty:
        return df

    df["score"] = _norm(df["dy"]).fillna(0)
    df["asset_type"] = "FII"
    for col in ["margem", "roic", "liq_corrente", "div_liq_ebitda", "margem_liquida", "roe", "pl"]:
        df[col] = 0
    if "setor" not in df.columns:
        df["setor"] = df.get("segmento", df.get("tipo", "FII"))
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
    if dy > 20:
        reasons.append(f"Dividend Yield de {dy:.1f}% a.a. — ATENCAO: valor atipico, verifique os dados")
    elif dy > 0:
        reasons.append(f"Dividend Yield de {dy:.1f}% a.a. — gera renda passiva recorrente")

    # --- VALUE ---
    if atype == "Acao":
        if margem > 0.1:
            reasons.append(f"Margem Graham de {margem*100:.0f}% — negociado abaixo do valor justo")
        if roic > 0.12:
            reasons.append(f"ROIC de {roic*100:.0f}% — empresa eficiente no uso do capital")

    if not reasons:
        reasons.append("Melhor relacao risco-retorno identificada nos indicadores analisados")

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
        "safety_score": _clean(round(row.get("safety_score") or 0, 4)),
        "shares_buyable": shares,
        "proj_monthly_per_share": _clean(proj_monthly) or 0,
        "proj_monthly_total": _clean(round(proj_monthly * shares, 4)) or 0,
        "reasons": reasons,
        "health_grade": _health_grade(row.get("safety_score") or 0),
    }


def _health_grade(safety_score: float) -> str:
    """Convert safety_score (0-1) to a letter grade."""
    if safety_score >= 0.75:
        return "A"
    if safety_score >= 0.55:
        return "B"
    if safety_score >= 0.35:
        return "C"
    return "D"


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


@router.get("/api/debug")
async def debug_data():
    """Diagnostic endpoint — shows raw DB data stats to help debug empty results."""
    try:
        stocks_raw = db.get_stocks(market="BR") or []
        fiis_raw = db.get_fiis() or []

        def col_stats(data, col):
            vals = [r.get(col) for r in data]
            non_none = [v for v in vals if v is not None]
            positives = [v for v in non_none if v > 0]
            return {
                "total": len(vals),
                "non_none": len(non_none),
                "positives": len(positives),
                "samples": [round(v, 2) if isinstance(v, float) else v for v in non_none[:8]],
            }

        return _json_response({
            "stocks_total": len(stocks_raw),
            "fiis_total": len(fiis_raw),
            "stocks": {
                "price": col_stats(stocks_raw, "price"),
                "dy": col_stats(stocks_raw, "dy"),
                "pl": col_stats(stocks_raw, "pl"),
                "pvp": col_stats(stocks_raw, "pvp"),
                "liquidezmediadiaria": col_stats(stocks_raw, "liquidezmediadiaria"),
                "liq_corrente": col_stats(stocks_raw, "liq_corrente"),
                "div_liq_ebitda": col_stats(stocks_raw, "div_liq_ebitda"),
                "roe": col_stats(stocks_raw, "roe"),
                "margem_liquida": col_stats(stocks_raw, "margem_liquida"),
            },
            "fiis": {
                "price": col_stats(fiis_raw, "price"),
                "dy": col_stats(fiis_raw, "dy"),
                "pvp": col_stats(fiis_raw, "pvp"),
                "liquidezmediadiaria": col_stats(fiis_raw, "liquidezmediadiaria"),
            },
        })
    except Exception as e:
        return _json_response({"error": str(e)})


def _build_mix_portfolio(combined: pd.DataFrame, budget: float) -> list:
    """
    Build a diversified portfolio from scored candidates.
    Rules:
      - 1 asset if budget < 30, up to 10 if budget >= 500
      - Max 2 assets per sector to ensure diversification
      - Allocation weighted by score (better assets get more)
      - Exact share counts that fit within budget
    """
    if combined.empty:
        return []

    # Determine target asset count based on budget
    if budget < 30:
        max_assets = 1
    elif budget < 100:
        max_assets = 3
    elif budget < 300:
        max_assets = 5
    elif budget < 500:
        max_assets = 7
    else:
        max_assets = 10

    # Diversification: pick top assets but limit per sector/type
    selected = []
    sector_count = {}
    type_count = {}

    for _, row in combined.iterrows():
        if len(selected) >= max_assets:
            break

        sector = str(row.get("setor", "Outro")).strip() or "Outro"
        atype = str(row.get("asset_type", "Acao"))

        # Max 2 per sector, max ceil(max_assets*0.6) per asset type
        max_per_type = max(2, math.ceil(max_assets * 0.6))
        if sector_count.get(sector, 0) >= 2:
            continue
        if type_count.get(atype, 0) >= max_per_type:
            continue

        selected.append(row.to_dict())
        sector_count[sector] = sector_count.get(sector, 0) + 1
        type_count[atype] = type_count.get(atype, 0) + 1

    if not selected:
        return []

    # Calculate weighted allocation based on score
    total_score = sum(max(s.get("score", 0), 0.01) for s in selected)
    remaining_budget = budget

    portfolio = []
    for s in selected:
        weight = max(s.get("score", 0), 0.01) / total_score
        target_alloc = budget * weight
        price = s.get("price", 0) or 1
        shares = max(1, math.floor(target_alloc / price))
        cost = shares * price

        # Don't exceed remaining budget
        while shares > 0 and cost > remaining_budget:
            shares -= 1
            cost = shares * price

        if shares <= 0:
            continue

        remaining_budget -= cost

        portfolio.append(_safe_dict({
            "ticker": s.get("ticker", ""),
            "empresa": s.get("empresa", ""),
            "asset_type": s.get("asset_type", "Acao"),
            "setor": s.get("setor", ""),
            "price": _clean(price),
            "dy": _clean(s.get("dy", 0)),
            "pvp": _clean(s.get("pvp")) or None,
            "pl": _clean(s.get("pl")) or None,
            "score": _clean(round(s.get("score", 0), 4)),
            "health_grade": _health_grade(s.get("safety_score", 0)),
            "shares": shares,
            "allocated": round(cost, 2),
        }))

    # Try to use remaining budget — give extra shares to top assets
    for p in portfolio:
        price = p["price"] or 1
        extra = math.floor(remaining_budget / price)
        if extra > 0:
            p["shares"] += extra
            added = extra * price
            p["allocated"] = round(p["allocated"] + added, 2)
            remaining_budget -= added

    logger.info(f"[scope] Mix portfolio: {len(portfolio)} assets, "
                f"allocated R${sum(p['allocated'] for p in portfolio):.2f} of R${budget:.2f}")
    return portfolio


@router.get("/api/recommend")
async def recommend(
    budget: float = 50.0,
    yolo: bool = False,
    mode: str = "unico",
    user: dict = Depends(get_optional_user),
):
    """
    Daily asset screening based on financial indicators.
    yolo=false (default) → conservative, safety-first filters.
    yolo=true  → "Faca na Caveira" — raw DY ranking, no safety filters.
    mode='unico' → single best asset ranking (default).
    mode='mix'   → diversified portfolio builder.
    """
    try:
        if budget <= 0:
            return _json_response({"status": "error", "message": "Informe um valor positivo."})

        candidates = []

        # For mix mode, use full budget for filtering (not per-asset budget)
        filter_budget = budget

        # Stocks (BR)
        stocks_raw = db.get_stocks(market="BR") or []
        logger.info(f"[scope] Raw stocks from DB: {len(stocks_raw)}")
        if stocks_raw:
            df_raw = pd.DataFrame(stocks_raw)
            if yolo:
                df_s = _yolo_score_stocks(df_raw, filter_budget)
            else:
                df_s = _filter_and_score_stocks(df_raw, filter_budget)
            if not df_s.empty:
                candidates.append(df_s)

        # FIIs
        fiis_raw = db.get_fiis() or []
        logger.info(f"[scope] Raw FIIs from DB: {len(fiis_raw)}")
        if fiis_raw:
            df_raw = pd.DataFrame(fiis_raw)
            if yolo:
                df_f = _yolo_score_fiis(df_raw, filter_budget)
            else:
                df_f = _filter_and_score_fiis(df_raw, filter_budget)
            if not df_f.empty:
                candidates.append(df_f)

        if not candidates:
            msg = (
                f"Nenhum ativo com dividendos encontrado abaixo de R$ {budget:.2f}."
                if yolo else
                f"Nenhum ativo saudavel com dividendos encontrado abaixo de R$ {budget:.2f}. "
                f"Tente aumentar o valor — muitos ativos com bons indicadores custam acima de R$ 10."
            )
            return _json_response({"status": "empty", "message": msg})

        combined = pd.concat(candidates, ignore_index=True)
        combined = combined.replace([np.inf, -np.inf], np.nan).fillna(0)
        combined = combined.sort_values("score", ascending=False)

        # Conservative mode: final safety gate — remove grade D assets
        if not yolo:
            combined = combined[combined.get("safety_score", pd.Series(0, index=combined.index)).fillna(0) >= 0.35]
            logger.info(f"[scope] After safety gate (>=0.35): {len(combined)} candidates")

        # ── MIX MODE: build diversified portfolio ──
        if mode == "mix":
            # Take more candidates for diversification picking
            pool = combined.head(30)
            portfolio = _build_mix_portfolio(pool, budget)

            if not portfolio:
                return _json_response({"status": "empty", "message": f"Nao foi possivel montar um mix com R$ {budget:.2f}."})

            # Also return top 5 as regular results for reference
            top5 = combined.head(5)
            results = []
            for _, row in top5.iterrows():
                info = _build_justification(row.to_dict(), budget)
                info = _safe_dict(info)
                results.append(info)

            return _json_response({
                "status": "success",
                "budget": float(budget),
                "mode": "mix",
                "count": len(portfolio),
                "portfolio": portfolio,
                "results": results,
            })

        # ── SINGLE MODE: top 5 ranked assets ──
        combined = combined.head(5)

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
            "results": results,
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
        ticker      = body.get("ticker", "").upper()
        asset_type  = body.get("asset_type", "Acao")
        quantity    = int(body.get("quantity", 1))
        price       = float(body.get("price", 0))
        wallet_id   = body.get("wallet_id")
        wallet_name = body.get("wallet_name") or "Scope — Habito Diario"

        if not ticker or quantity <= 0 or price <= 0:
            return JSONResponse({"status": "error", "message": "Dados invalidos."})

        user_id = user["id"]

        # Create new wallet if needed
        if not wallet_id:
            success, msg = WalletQueries.create_wallet(user_id=user_id, name=wallet_name)
            if not success:
                return JSONResponse({"status": "error", "message": msg})

            # Find the newly created wallet by name
            wallets = WalletQueries.get_wallets(user_id) or []
            for w in wallets:
                if w.get("name") == wallet_name:
                    wallet_id = w.get("id")
                    break

            if not wallet_id:
                return JSONResponse({"status": "error", "message": "Carteira criada mas nao encontrada. Tente novamente."})

        # Add asset to wallet
        success, msg = AssetQueries.add_to_wallet(
            user_id=user_id,
            ticker=ticker,
            quantity=quantity,
            price=price,
            wallet_id=wallet_id,
        )

        if not success:
            return JSONResponse({"status": "error", "message": msg})

        return JSONResponse({
            "status": "success",
            "message": f"{ticker} adicionado a carteira '{wallet_name}' com sucesso!",
            "wallet_id": wallet_id,
        })

    except Exception as e:
        logger.error(f"[scope] add-to-wallet error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})
