from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user_from_cookie
import yfinance as yf
import math

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def calcular_graham(ticker):
    """Calcula o Valor Intrínseco de Graham: sqrt(22.5 * VPA * LPA)"""
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        lpa = info.get('trailingEps', 0)
        vpa = info.get('bookValue', 0)
        
        if lpa > 0 and vpa > 0:
            valor_intrinseco = math.sqrt(22.5 * lpa * vpa)
            return round(valor_intrinseco, 2)
        return "N/A"
    except:
        return "Erro"

@router.get("/", response_class=HTMLResponse)
async def pagina_acoes(request: Request, user: dict = Depends(get_current_user_from_cookie)):
    """Render stock analysis page"""
    return templates.TemplateResponse("pages/acoes.html", {
        "request": request,
        "user": user
    })

@router.get("/api/analise/{ticker}")
async def analisar_acao(ticker: str):
    vi_graham = calcular_graham(ticker)
    return {
        "ticker": ticker.upper(),
        "graham": vi_graham,
        "recomendacao_ia": "Integrar com Gemini aqui..."
    }