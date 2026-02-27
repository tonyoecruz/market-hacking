"""
Renda Fixa Router — Strategy Screener
=======================================
Two modes:
  GET /renda-fixa/api/top-opportunities  → Legacy scored list
  GET /renda-fixa/api/data-estrategia    → Strategy-based engine (4 models)

Risk filtering:
  - Liquidated issuers are ALWAYS removed (BCB public data + local blacklist)
  - High-risk issuers are hidden by default (toggle: show_high_risk=true)
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_optional_user
from modules.fixed_income import FixedIncomeManager
from modules.risk_checker import filter_opportunities
from routes.engines.rendafixa_engine import apply_rendafixa_strategy
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["renda-fixa"])
templates = Jinja2Templates(directory="templates")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTE
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
async def renda_fixa_page(
    request: Request,
    user: dict = Depends(get_optional_user)
):
    """Render Fixed Income page"""
    return templates.TemplateResponse(
        "pages/renda_fixa.html",
        {
            "request": request,
            "user": user,
            "page_title": "Renda Fixa"
        }
    )


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT — STRATEGY ENGINE (with risk filtering)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/data-estrategia")
async def get_rendafixa_data_estrategia(
    strategy: str = 'reserva_emergencia',
    show_high_risk: bool = False,
):
    """
    Strategy-based Fixed Income screener.
    Available strategies: reserva_emergencia, ganho_real, trava_preco, duelo_tributario

    Risk filtering:
      - Liquidated institutions are ALWAYS filtered out (BCB + local blacklist)
      - High-risk institutions are hidden by default (toggle: show_high_risk=true)
    """
    try:
        # 1. Get base data
        all_opportunities = FixedIncomeManager.get_top_opportunities()

        if not all_opportunities:
            return JSONResponse({
                'status': 'success', 'total_count': 0,
                'ranking': [], 'strategy': strategy,
                'caveats': [], 'score_col': {},
                'risk_filtered': 0,
            })

        # 2. Risk filter BEFORE strategy (remove liquidated always, high-risk by toggle)
        total_before = len(all_opportunities)
        safe_opportunities = filter_opportunities(all_opportunities, show_high_risk=show_high_risk)
        risk_filtered = total_before - len(safe_opportunities)

        # 3. Apply strategy engine on safe list
        ranked, score_col, caveats = apply_rendafixa_strategy(safe_opportunities, strategy)

        # Add risk caveats
        if risk_filtered > 0 and not show_high_risk:
            caveats.append(
                f"{risk_filtered} produto(s) de alto risco ocultado(s). "
                "Ative 'Mostrar alto risco' para visualizar."
            )

        return JSONResponse({
            'status': 'success',
            'total_count': total_before,
            'ranking': ranked,
            'strategy': strategy,
            'caveats': caveats,
            'score_col': score_col,
            'risk_filtered': risk_filtered,
        })

    except Exception as e:
        logger.error(f"[renda-fixa/api/data-estrategia] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY API ENDPOINTS (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/top-opportunities")
async def get_top_opportunities():
    """Get Top Fixed Income opportunities ranked by score"""
    opportunities = FixedIncomeManager.get_top_opportunities()
    return {"opportunities": opportunities}


@router.post("/api/analyze")
async def analyze_fixed_income(
    request: Request,
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

    return {"analysis": analysis}
