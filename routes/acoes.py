from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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

@router.get("/acoes", response_class=HTMLResponse)
async def pagina_acoes(request: Request):
    # Aqui você pode adicionar a lógica da Magic Formula depois
    return templates.TemplateResponse("pages/acoes.html", {"request": request})

@router.get("/api/analise/{ticker}")
async def analisar_acao(ticker: str):
    vi_graham = calcular_graham(ticker)
    return {
        "ticker": ticker.upper(),
        "graham": vi_graham,
        "recomendacao_ia": "Integrar com Gemini aqui..."
    }