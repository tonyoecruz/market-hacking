"""
Módulo Data Fetcher - Pipelines de Carga de Dados
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import time
from .config import ACOES_BR_BASE, ACOES_US_BASE, FIIS_BR_BASE, KNOWN_ETFS
from .market_calculators import calcular_margem_graham, calcular_dy_anualizado, is_likely_etf
from .yf_extractor import extrair_dados_yfinance

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_acoes_pipeline():
    """
    Pipeline completo de coleta de dados de AÇÕES (BR + US)
    """
    all_tickers = []
    
    selected_markets = st.session_state.get('selected_markets', ['BR']) # Check key match with app.py (selected_markets or selected_markets_acoes?)
    # App.py uses 'selected_markets' for Ações (line 2086)
    
    if not isinstance(selected_markets, list):
        selected_markets = ['BR']

    # Logic to map "🇧🇷 Brasil (B3)" to "BR" etc if needed
    # App.py uses: if any("Brasil" in s for s in selected)
    use_br = any("Brasil" in s for s in selected_markets) or 'BR' in selected_markets
    use_us = any("Estados Unidos" in s for s in selected_markets) or 'US' in selected_markets

    if use_br:
        all_tickers.extend(ACOES_BR_BASE)
    if use_us:
        all_tickers.extend(ACOES_US_BASE)
    
    dados_finais = []
    total_tickers = len(all_tickers)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(all_tickers):
        # Filter ETFs from Stock Pipeline
        if is_likely_etf(ticker): 
            continue

        status_text.text(f"Processando {ticker} ({i+1}/{total_tickers})...")
        progress_bar.progress((i + 1) / total_tickers)
        
        try:
            dados = extrair_dados_yfinance(ticker)
            
            if dados:
                dados['Region'] = 'BR' if '.SA' in ticker else 'US'
                dados['Margem'] = calcular_margem_graham(dados['price'], dados['lpa'], dados['vpa'])
                
                # Magic Formula pre-calc fields already in extractor?
                # Extractor has: ev_ebit, roic.
                # We need to calculate MagicRank later on the full DF.
                
                # App.py calculates 'graham_term' and 'ValorJusto' explicitly.
                # Extractor returns 'margem_liquida' but not 'ValorJusto' directly, just inputs.
                # calculate_margem_graham returns final margin.
                # App.py uses:
                # df_acoes['graham_term'] = (22.5 * df_acoes['lpa'] * df_acoes['vpa']).apply(...)
                # df_acoes['ValorJusto'] = np.sqrt(df_acoes['graham_term'])
                
                # We should add ValorJusto to the dict for compatibility
                lpa = dados.get('lpa', 0)
                vpa = dados.get('vpa', 0)
                if lpa > 0 and vpa > 0:
                     dados['ValorJusto'] = (22.5 * lpa * vpa) ** 0.5
                else:
                     dados['ValorJusto'] = 0.0

                dados_finais.append(dados)
            
            time.sleep(0.5) 
            
        except Exception as e:
            # print(f"Erro pipeline {ticker}: {e}")
            continue
            
    progress_bar.empty()
    status_text.empty()
    
    if not dados_finais:
        return False

    df = pd.DataFrame(dados_finais)
    
    # MAGIC FORMULA CALCULATION (In-Memory)
    try:
        df_magic = df[(df['ev_ebit'] > 0) & (df['roic'] > 0)].copy()
        
        if not df_magic.empty:
            df_magic['R_EV'] = df_magic['ev_ebit'].rank(ascending=True)
            df_magic['R_ROIC'] = df_magic['roic'].rank(ascending=False)
            df_magic['Score'] = df_magic['R_EV'] + df_magic['R_ROIC']
            df_magic['MagicRank'] = df_magic['Score'].rank(ascending=True)
            
            df = df.merge(df_magic[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
    except Exception as e:
        print(f"Erro ao calcular Magic Formula: {e}")

    st.session_state['market_data'] = df
    return True # Return Generic Success boolean as per app.py expectation

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_fiis_pipeline():
    """
    Pipeline de FIIs brasileiros e REITs americanos
    """
    all_tickers = []
    selected_markets = st.session_state.get('selected_markets_fiis', ['BR']) # App uses specific key
    
    if not isinstance(selected_markets, list):
        selected_markets = ['BR']

    use_br = any("Brasil" in s for s in selected_markets) or 'BR' in selected_markets
    use_us = any("Estados Unidos" in s for s in selected_markets) or 'US' in selected_markets

    if use_br:
        all_tickers.extend(FIIS_BR_BASE)
    
    # REITs logic... placeholder if needed
    
    dados_finais = []
    total_tickers = len(all_tickers)
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(all_tickers):
        status_text.text(f"Processando FII {ticker} ({i+1}/{total_tickers})...")
        progress_bar.progress((i + 1) / total_tickers)
        
        try:
            tk_obj = yf.Ticker(ticker)
            info = tk_obj.info
            
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            if not price:
                continue
                
            dy = calcular_dy_anualizado(tk_obj)
            pvp = info.get('priceToBook', 0)
            
            dados_finais.append({
                'ticker': ticker,
                'price': price,
                'dy': dy,
                'pvp': pvp,
                'liquidezmediadiaria': info.get('averageVolume', 0) * price,
                'segmento': info.get('sector', 'FII/REIT'), 
                'Region': 'BR' if '.SA' in ticker else 'US'
            })
            
            time.sleep(0.5)
            
        except Exception as e:
            # print(f"Erro FII {ticker}: {e}")
            continue
            
    progress_bar.empty()
    status_text.empty()
    
    if not dados_finais:
        return False

    df = pd.DataFrame(dados_finais)
    st.session_state['fiis_data'] = df
    return True

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_etfs_pipeline():
    """
    Pipeline de ETFs (B3 + US)
    """
    selected_markets = st.session_state.get('selected_markets_etfs', ['BR'])
    
    df_final = pd.DataFrame()
    etf_data = []

    use_br = any("Brasil" in s for s in selected_markets) or 'BR' in selected_markets
    # use_us ...
    
    if use_br:
         # Batch download for performance
         tickers_sa = [f"{t}.SA" for t in KNOWN_ETFS if not t.endswith('.SA')]
         # Handle ones that might already have .SA
         
         # Normalized list
         clean_list = []
         for t in KNOWN_ETFS:
             if not t.endswith('.SA'): clean_list.append(f"{t}.SA")
             else: clean_list.append(t)
             
         try:
            # YF Download
            # Pega 1 mês para garantir volume
            batch = yf.download(clean_list, period="5d", interval="1d", group_by='ticker', progress=False)
            
            for t_sa in clean_list:
                t_raw = t_sa.replace('.SA', '')
                try:
                    if len(clean_list) > 1: df_t = batch[t_sa]
                    else: df_t = batch
                    
                    if not df_t.empty:
                        last_row = df_t.iloc[-1]
                        price = float(last_row['Close'])
                        vol = float(last_row['Volume']) * price
                        if price > 0:
                            etf_data.append({'ticker': t_raw, 'price': price, 'liquidezmediadiaria': vol, 'pvp': 0, 'dy': 0, 'Region': 'BR'})
                except: pass
         except Exception as e:
             print(f"Erro Batch ETFs: {e}")

    if etf_data:
        df_final = pd.DataFrame(etf_data)
        st.session_state['market_data_etfs'] = df_final
        return True
        
    return False

@st.cache_data(ttl=1800, show_spinner=False)
def get_candle_chart(ticker):
    """
    Gera gráfico de candlestick usando Plotly
    """
    import plotly.graph_objects as go
    
    try:
        # Tenta ticker direto e com .SA se falhar logic might be needed, but assume input is correct
        df = yf.download(ticker, period='6mo', interval='1d', progress=False)
        
        if df.empty:
            if not ticker.endswith('.SA'):
                 df = yf.download(f"{ticker}.SA", period='6mo', interval='1d', progress=False)
            if df.empty: return None
            
        # Tratamento para MultiIndex nas colunas (yfinance v0.2+)
        if isinstance(df.columns, pd.MultiIndex):
            try:
                # Try to access 'Close' directly if it's the second level?
                # yfinance usually: (Price, Ticker)
                # If we downloaded single ticker, structure might be flat or (Price, Ticker)
                # If flat: columns are Open, High...
                # If multi: (Open, Ticker)...
                pass
            except: pass
            
        # Flatten logic helper
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)

        # Check required columns
        req = ['Open', 'High', 'Low', 'Close']
        if not all(c in df.columns for c in req):
            return None

        fig = go.Figure(data=[go.Candlestick(x=df.index,
                        open=df['Open'],
                        high=df['High'],
                        low=df['Low'],
                        close=df['Close'])])
                        
        fig.update_layout(
            title=f'Gráfico Diário - {ticker}',
            yaxis_title='Preço (R$)',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig
    except Exception as e:
        print(f"Erro gráfico {ticker}: {e}")
        return None

