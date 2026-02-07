"""
Módulo de Cálculos Financeiros
"""
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from .config import KNOWN_ETFS, RISKY_TICKERS

def is_likely_etf(ticker):
    """Verifica se é ETF baseado na lista conhecida"""
    t = ticker.strip().upper()
    # Verifica ticker puro ou com .SA
    clean_t = t.replace('.SA', '')
    return clean_t in KNOWN_ETFS or t in KNOWN_ETFS

def check_risk(row):
    """
    Retorna (True, Message) se arriscado, (False, None) se seguro.
    Critérios: Blacklist ou Dívida Alta.
    """
    ticker = row.get('ticker', '').strip().upper().replace('.SA', '')
    if ticker in RISKY_TICKERS:
        return True, "ALERTA: Ativo em Lista de Risco (RJ/Recuperação)."
    
    # Check dívida se existir
    # div_pat = Dívida Líquida / Patrimônio ou similar.
    # No yf_extractor usamos 'div_pat' como debtToEquity (percentual ou ratio? yf retorna %, dividimos por 100)
    # yfinance debtToEquity is usually %, so 500% = 5.
    # Se 'div_pat' > 5 (500% debt/equity), é muito alto.
    try:
        if row.get('div_pat', 0) > 5.0:
            return True, "ALERTA: Endividamento Excessivo (>5x PL)."
    except: pass
    
    return False, None

def filter_risky_stocks(df):
    """
    Remove ativos arriscados do DataFrame.
    Retorna DF filtrado.
    """
    if df.empty: return df
    
    # 1. Ticker Blacklist
    # Remove se estiver na lista de risco (strip .SA for check)
    def is_risky(t):
        tn = t.strip().upper().replace('.SA', '')
        return tn in RISKY_TICKERS

    df_safe = df[~df['ticker'].apply(is_risky)].copy()
    
    # 2. Financial Filters (Optional - e.g. Debt)
    # Se tiver coluna div_pat, filtra > 5
    if 'div_pat' in df_safe.columns:
        df_safe = df_safe[df_safe['div_pat'] <= 5.0]
        
    return df_safe


def calcular_margem_graham(price, lpa, vpa):
    """
    Fórmula de Benjamin Graham para valor intrínseco
    
    Valor Intrínseco = √(22.5 × LPA × VPA)
    Margem = (Valor Intrínseco / Preço Atual) - 1
    
    RETORNA: float (percentual, ex: 0.35 = 35%)
    """
    try:
        # Garantir que entradas são numéricas
        price = float(price) if price else 0.0
        lpa = float(lpa) if lpa else 0.0
        vpa = float(vpa) if vpa else 0.0

        if not all([price > 0, lpa > 0, vpa > 0]):
            return 0.0
        
        graham_number = 22.5 * lpa * vpa
        if graham_number < 0:
            return 0.0
            
        valor_intrinseco = graham_number ** 0.5
        margem = (valor_intrinseco / price) - 1
        return max(margem, -0.99)  # Limita em -99%
    except:
        return 0.0

def calcular_dy_anualizado(ticker_obj):
    """
    Busca histórico de dividendos dos últimos 12 meses
    DY = (Soma Dividendos 12M / Preço Atual)
    
    FONTE: ticker_obj.dividends (pandas Series)
    """
    try:
        dividends = ticker_obj.dividends
        if dividends.empty:
            return 0.0
        
        # Últimos 12 meses
        cutoff_date = datetime.now() - timedelta(days=365)
        
        # Filtra dividendos (index é datetime)
        # Convert index to timezone-unaware if needed to match datetime.now() or handle comparison safely
        recent_divs = dividends[dividends.index >= pd.Timestamp(cutoff_date).tz_localize(dividends.index.tz)]

        total_divs = recent_divs.sum()
        current_price = ticker_obj.info.get('currentPrice') or ticker_obj.info.get('regularMarketPrice', 0)
        
        if current_price <= 0:
            return 0.0
        
        return total_divs / current_price
    except:
        return 0.0
