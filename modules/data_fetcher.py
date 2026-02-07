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
from .statusinvest_extractor import get_br_stocks_statusinvest, get_br_fiis_statusinvest

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_acoes_pipeline():
    """
    Pipeline completo de coleta de dados de AÇÕES (BR + US)
    """
    selected_markets = st.session_state.get('selected_markets', ['BR']) 
    if not isinstance(selected_markets, list): selected_markets = ['BR']

    use_br = any("Brasil" in s for s in selected_markets) or 'BR' in selected_markets
    use_us = any("Estados Unidos" in s for s in selected_markets) or 'US' in selected_markets

    df_list = []
    
    # --- BRASIL: STATUS INVEST BULK ---
    if use_br:
        status_text = st.empty()
        status_text.text("Baixando Ações BR (Status Invest)...")
        time.sleep(0.5)
        
        try:
            df_br = get_br_stocks_statusinvest()
            if not df_br.empty:
                df_br['Region'] = 'BR'
                
                # Filter ETFs (if any slipped through)
                if 'ticker' in df_br.columns:
                     mask_etf = df_br['ticker'].apply(is_likely_etf)
                     df_br = df_br[~mask_etf].copy()
                
                # Calculate Indicators
                # Graham Margin
                df_br['Margem'] = calcular_margem_graham(df_br['price'], df_br['lpa'], df_br['vpa'])
                
                # Fair Value
                # Ensure non-negative for sqrt
                graham_term = (22.5 * df_br['lpa'] * df_br['vpa'])
                # Handle Series apply
                def safe_sqrt(x):
                    return x**0.5 if x > 0 else 0
                
                df_br['ValorJusto'] = graham_term.apply(safe_sqrt)
                
                # Ensure other cols exist
                if 'ev_ebit' not in df_br.columns: df_br['ev_ebit'] = 0
                if 'roic' not in df_br.columns: df_br['roic'] = 0
                
                df_list.append(df_br)
                status_text.success(f"Sucesso BR (Status Invest): {len(df_br)} ativos baixados.")
                time.sleep(1)
            else:
                status_text.error("Status Invest retornou dados vazios.")
                time.sleep(2)
        except Exception as e:
            print(f"Erro BR Pipeline: {e}")
            status_text.error(f"Erro ao conectar com Status Invest: {e}")
            time.sleep(2)

    # --- USA: YFINANCE LOOP (Targeted List) ---
    if use_us:
        us_tickers = ACOES_US_BASE
        us_data = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_us = len(us_tickers)
        
        for i, ticker in enumerate(us_tickers):
            status_text.text(f"US: Processando {ticker}...")
            progress_bar.progress((i+1)/total_us)
            
            try:
                d = extrair_dados_yfinance(ticker)
                if d:
                    d['Region'] = 'US'
                    d['Margem'] = calcular_margem_graham(d['price'], d['lpa'], d['vpa'])
                    lpa = d.get('lpa', 0)
                    vpa = d.get('vpa', 0)
                    d['ValorJusto'] = (22.5 * lpa * vpa)**0.5 if (lpa>0 and vpa>0) else 0
                    us_data.append(d)
                time.sleep(0.2)
            except: pass
            
        progress_bar.empty()
        status_text.empty()
        
        if us_data:
            df_list.append(pd.DataFrame(us_data))

    if not df_list:
        return False

    df = pd.concat(df_list, ignore_index=True)
    
    # MAGIC FORMULA CALCULATION (Global)
    try:
        # Pre-filter for ranking
        df_magic = df[(df['ev_ebit'] > 0) & (df['roic'] > 0)].copy()
        
        if not df_magic.empty:
            df_magic['R_EV'] = df_magic['ev_ebit'].rank(ascending=True)
            df_magic['R_ROIC'] = df_magic['roic'].rank(ascending=False)
            df_magic['Score'] = df_magic['R_EV'] + df_magic['R_ROIC']
            df_magic['MagicRank'] = df_magic['Score'].rank(ascending=True)
            
            # Merge logic - drop old columns if exist to avoid suffix
            cols = ['Score', 'MagicRank', 'R_EV', 'R_ROIC']
            df = df.drop(columns=[c for c in cols if c in df.columns], errors='ignore')
            
            df = df.merge(df_magic[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
    except Exception as e:
        print(f"Erro Magic Formula: {e}")

    st.session_state['market_data'] = df
    return True # Return Generic Success boolean as per app.py expectation

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_fiis_pipeline():
    """
    Pipeline de FIIs brasileiros e REITs americanos
    """
    selected_markets = st.session_state.get('selected_markets_fiis', ['BR']) # App uses specific key
    if not isinstance(selected_markets, list): selected_markets = ['BR']

    use_br = any("Brasil" in s for s in selected_markets) or 'BR' in selected_markets
    use_us = any("Estados Unidos" in s for s in selected_markets) or 'US' in selected_markets

    df_list = []
    
    # --- FIIs BRASIL: STATUS INVEST BULK ---
    if use_br:
        status_text = st.empty()
        status_text.text("Baixando FIIs BR (Status Invest)...")
        time.sleep(0.5)
        
        try:
            df_br = get_br_fiis_statusinvest()
            if not df_br.empty:
                df_br['Region'] = 'BR'
                # Ensure minimal columns
                if 'segmento' not in df_br.columns: df_br['segmento'] = 'FII'
                
                df_list.append(df_br)
                status_text.success(f"Sucesso FIIs (Status Invest): {len(df_br)} fundos baixados.")
                time.sleep(1)
            else:
                status_text.error("Falha ao buscar FIIs BR (Dados Vazios).")
                time.sleep(2)
        except Exception as e:
            print(f"Erro FII Pipeline: {e}")
            status_text.error(f"Erro FII ao conectar com Status Invest: {e}")
            time.sleep(2)

    # --- REITS USA (Placeholder/Future) ---
    # Currently no list provided in config for bulk REITs, 
    # and previous logic was empty or relied on dynamic fetching.
    # If a list existed, we would iterate here like Ações US.
    
    if not df_list:
        return False

    df = pd.concat(df_list, ignore_index=True)
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

