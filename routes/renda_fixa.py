"""
Fixed Income (Renda Fixa) Routes
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user_from_cookie
from database.queries import WalletQueries, AssetQueries
from modules.fixed_income import FixedIncomeManager
import logging

logger = logging.getLogger(__name__)

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
    """Get Top Fixed Income opportunities ranked by score"""
    opportunities = FixedIncomeManager.get_top_opportunities()
    return {"opportunities": opportunities}


@router.post("/api/analyze")
async def analyze_fixed_income(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Generate AI analysis for a Fixed Income product"""
    body = await request.json()
    product_type = body.get("type", "CDB")
    issuer = body.get("issuer", "")
    rate_val = body.get("rate_val", 0)
    rate_type = body.get("rate_type", "Pos-fixado")
    maturity = body.get("maturity", "")
    liquidity = body.get("liquidity", "")
    safety_rating = body.get("safety_rating", "FGC Garantido")
    score = body.get("score", 0)

    # Build analysis text based on product details
    rate_text = ""
    if rate_type == "Pré-fixado":
        rate_text = f"{rate_val}% a.a. pré-fixado"
    elif rate_type == "Isento":
        rate_text = f"{rate_val}% do CDI (isento de IR)"
    else:
        rate_text = f"{rate_val}% do CDI"

    risk_level = "baixo" if score > 150 else ("médio" if score > 100 else "alto")

    analysis = f"""📊 Análise: {product_type} do {issuer}

💰 Rentabilidade: {rate_text}

Este produto oferece uma rentabilidade {{rate_analysis}}.

📅 Vencimento: {maturity}
⚡ Liquidez: {liquidity}
🛡️ Garantia: {safety_rating}
⭐ Score SCOPE3: {score}

🔑 Pontos Principais:
• {"Produto isento de Imposto de Renda — ideal para prazo de até 2-3 anos" if rate_type == "Isento" else "Incide tabela regressiva de IR (de 22,5% até 15% ao ano)"}
• {"Liquidez diária permite resgatar a qualquer momento" if liquidity == "Diária" else f"Prazo de carência de {liquidity} antes do resgate"}
• {safety_rating} protege até R$ 250.000 por CPF/instituição
• {"Alta rentabilidade — acima de 110% CDI é considerado excelente" if isinstance(rate_val, (int, float)) and rate_val >= 110 else "Rentabilidade competitiva para o perfil de risco"}

⚠️ Observações:
• Compare sempre com o CDI atual (≈ 13,75% a.a.) para avaliar o retorno real
• Renda Fixa não elimina o risco de liquidez antes do vencimento
• Diversifique entre instituições para manter a cobertura do FGC
""".replace(
        "{rate_analysis}",
        "muito acima da média do mercado" if isinstance(rate_val, (int, float)) and rate_val >= 120 else
        "acima da média do mercado" if isinstance(rate_val, (int, float)) and rate_val >= 110 else
        "dentro da média de mercado"
    )

    try:
        # Try AI analysis if available
        from modules.ai_analyzer import AIAnalyzer
        investor = body.get("investor", "")
        ai_text = await AIAnalyzer.analyze_text(
            f"Analise este produto de Renda Fixa: {product_type} do {issuer}, "
            f"rentabilidade {rate_text}, vencimento {maturity}, liquidez {liquidity}, "
            f"garantia {safety_rating}. Score interno: {score}. "
            f"Perfil investidor: {investor}.",
            investor
        )
        if ai_text:
            analysis = ai_text
    except Exception as e:
        logger.debug(f"AI analysis not available, using template: {e}")
        # The template analysis above will be returned

    return {"analysis": analysis}


@router.post("/api/add")
async def add_fixed_income_asset(
    request: Request,
    user: dict = Depends(get_current_user_from_cookie)
):
    """Add Fixed Income asset to wallet with specific yield metadata"""
    body = await request.json()

    # Extract fields
    product_type = body.get("type", "CDB")
    issuer = body.get("issuer", "Banco")

    # Construct a "Ticker" for internal tracking
    ticker = body.get("ticker")
    if not ticker:
        ticker = f"{product_type}-{issuer[:10].upper().replace(' ', '')}"

    quantity = float(body.get("quantity", 1))
    invested_value = float(body.get("value", 0))

    # For Renda Fixa: price is unit value, quantity is number of titles
    if quantity == 1 and invested_value > 0:
        price = invested_value
    else:
        price = invested_value / quantity if quantity > 0 else 0

    wallet_id = int(body.get("wallet_id", 1))

    # Yield Data
    pct_cdi = float(body.get("pct_cdi", 0))
    pct_pre = float(body.get("pct_pre", 0))

    # Default: if both zero → 100% CDI
    if pct_cdi == 0 and pct_pre == 0:
        pct_cdi = 100.0

    metadata = {
        "yield_type": "hybrid" if (pct_cdi > 0 and pct_pre > 0) else ("CDI" if pct_cdi > 0 else "PRE"),
        "pct_cdi": pct_cdi,
        "pct_pre": pct_pre,
        "issuer": issuer,
        "product_type": product_type,
        "maturity_date": body.get("maturity_date"),
        "asset_class": "renda_fixa"
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
