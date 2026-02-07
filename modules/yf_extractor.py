"""
Módulo de Extração YFinance - Wrapper para tratamento de erros e normalização
"""
import yfinance as yf

def extrair_dados_yfinance(ticker_symbol):
    """
    Extrai todos os dados fundamentais via yfinance com tratamento de erros.
    
    Retorna um dicionário com chaves padronizadas ou None em caso de falha crítica.
    """
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info
        
        # Validação básica
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            # Tenta fallback para fast_info ou history se necessário, mas por enquanto retorna None
            # para respeitar o fluxo solicitado de "pula para próximo ticker"
            return None

        price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        
        dados = {
            'ticker': ticker_symbol,
            'price': price,
            'pl': info.get('trailingPE', 0),
            'pvp': info.get('priceToBook', 0),
            'roic': info.get('returnOnEquity', 0),
            'setor': info.get('sector', 'N/A'),
            'liquidezmediadiaria': info.get('averageVolume', 0) * price,
            'lpa': info.get('trailingEps', 0),
            'vpa': info.get('bookValue', 0),
            'dy': info.get('dividendYield', 0), # Pode ser None
            'margem_liquida': info.get('profitMargins', 0),
            'div_pat': info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0,
        }
        
        # Cálculo de EV/EBIT
        ev = info.get('enterpriseValue', 0)
        ebit = info.get('ebit', 0)
        dados['ev_ebit'] = ev / ebit if ebit and ebit != 0 else 0
        
        return dados
    
    except Exception as e:
        # Logs podem ser adicionados aqui se houver um sistema de log configurado
        print(f"Erro ao extrair {ticker_symbol}: {str(e)}")
        return None
