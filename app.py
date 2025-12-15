import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random
from datetime import datetime
import google.generativeai as genai

# ==============================================================================
# 🔑 CONFIGURAÇÃO DA INTELIGÊNCIA ARTIFICIAL (GEMINI)
# ==============================================================================
API_KEY = "AIzaSyB--UCOCA6vZg8VTknqJkbQapZ7yFa4agU"

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    IA_AVAILABLE = True
except Exception as e:
    IA_AVAILABLE = False
    print(f"Erro IA: {e}")

# ==============================================================================
# 🛠️ CONFIGURAÇÃO DO APP E ÍCONE (IPHONE FIX)
# ==============================================================================
# Link Proxy para garantir que o ícone carregue no iPhone (Drible no Cache)
URL_DO_ICONE = "https://wsrv.nl/?url=raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"

st.set_page_config(
    page_title="SCOPE3 v3.1 AI", 
    page_icon=URL_DO_ICONE, 
    layout="wide"
)

# ==============================================================================
# 🎨 ESTILOS CSS (DARK MODE & ALERTS)
# ==============================================================================
st.markdown(f"""
<head>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SCOPE3">
    <link rel="apple-touch-icon" href="{URL_DO_ICONE}">
</head>
<style>
    /* BASE DARK */
    .stApp {{ background-color: #000; color: #e0e0e0; font-family: 'Consolas', monospace; }}
    h1, h2, h3 {{ color: #00ff41 !important; text-transform: uppercase; }}
    
    /* BOTÕES HACKER */
    .stButton>button {{ 
        border: 2px solid #00ff41; 
        color: #00ff41; 
        background: #000; 
        font-weight: bold; 
        height: 50px; 
        width: 100%;
        text-transform: uppercase; 
        border-radius: 0px;
        transition: 0.3s;
    }}
    .stButton>button:hover {{ 
        background: #00ff41; 
        color: #000; 
        box-shadow: 0 0 20px #00ff41; 
    }}
    
    /* INPUTS */
    div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] > div > div {{ 
        color: #fff !important; 
        background-color: #111 !important; 
        border: 1px solid #00ff41 !important; 
    }}

    /* CAIXA DE ANÁLISE (IA) */
    .ai-box {{ 
        border: 1px solid #9933ff; 
        background-color: #1a0526; 
        padding: 20px; 
        border-radius: 4px; 
        margin-top: 15px; 
        border-left: 5px solid #9933ff; 
    }}
    .ai-title {{ 
        color: #c299ff; 
        font-weight: bold; 
        font-size: 18px; 
        display: flex; 
        align-items: center; 
        gap: 10px; 
        margin-bottom: 10px; 
    }}
    
    /* ALERTA DE RISCO (SNIPER) */
    .risk-alert {{ 
        background-color: #1a0000; 
        color: #ffcccc; 
        border: 2px solid #ff0000; 
        padding: 20px; 
        border-radius: 4px; 
        margin-top: 15px; 
        animation: pulse 2s infinite; 
    }}
    .risk-title {{ 
        color: #ff0000; 
        font-weight: 900; 
        font-size: 20px; 
        margin-bottom: 10px; 
        display: flex; 
        align-items: center; 
        gap: 10px; 
    }}
    
    @keyframes pulse {{ 
        0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }} 
        70% {{ box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }} 
        100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }} 
    }}

    /* CARDS DE INFO */
    .info-card {{ 
        background: #0a0a0a; 
        padding: 10px; 
        border-left: 3px solid #00ff41; 
        margin-bottom: 5px; 
    }}
    .info-label {{ font-size: 10px; color: #888; text-transform: uppercase; }}
    .info-val {{ font-size: 14px; font-weight: bold; color: #fff; }}
    
    /* Esconder elementos padrão */
    #MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🧠 CÉREBRO DA IA (MODO SNIPER)
# ==============================================================================
def get_ai_analysis(ticker, price, fair_value, details):
    if not IA_AVAILABLE:
        return "⚠️ ERRO: Biblioteca de IA não instalada ou chave inválida."
    
    # O Prompt que define a personalidade do robô
    prompt = f"""
    Você é o SCOPE3, uma Inteligência Artificial SNIPER focada no mercado financeiro brasileiro (B3).
    Sua personalidade é: Direta, Ácida, Técnica e Extremamente Crítica. Não use rodeios.

    ALVO: {ticker} ({details.get('Empresa', 'N/A')})
    DADOS:
    - Preço Atual: R$ {price}
    - Valor Justo (Graham): R$ {fair_value}
    - Setor: {details.get('Setor', 'N/A')}
    - Segmento: {details.get('Segmento', 'N/A')}

    MISSÃO:
    1. Verifique na sua base de conhecimento se essa empresa está em RECUPERAÇÃO JUDICIAL, FALÊNCIA ou reestruturação grave (Ex: Americanas, Oi, Light, Gol, Paranapanema).
    2. SE ESTIVER EM RISCO: Comece o texto OBRIGATORIAMENTE com "ALERTA DE SNIPER 💀" e explique a gravidade (dívidas, risco de calote, "virar pó"). Seja duro.
    3. SE FOR SÓLIDA: Analise a margem de segurança de Graham. Se estiver barata, diga "Oportunidade". Se estiver cara, diga "Inflada".
    4. Formatação: Use quebras de linha e emojis táticos. Máximo de 6 linhas.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro de Conexão com a IA: {str(e)}"

# ==============================================================================
# 📡 CRAWLERS DE DADOS (FUNDAMENTUS)
# ==============================================================================

# 1. Pega detalhes (Setor/Segmento) de um ativo específico
@st.cache_data(ttl=3600)
def get_stock_details(ticker):
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        df_list = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')
        info = {}
        # Varre as tabelas buscando chaves específicas
        for df in df_list:
            for i in range(len(df)):
                row = df.iloc[i].astype(str).values
                for j in range(0, len(row), 2):
                    key = row[j].replace('?', '').strip()
                    val = row[j+1].strip()
                    if "Empresa" in key: info['Empresa'] = val
                    if "Setor" in key: info['Setor'] = val
                    if "Subsetor" in key: info['Segmento'] = val
        return info
    except: return {'Empresa': ticker}

# 2. Pega a tabela geral de todos os ativos
@st.cache_data(show_spinner=False)
def get_data_direct():
    url = 'https://www.fundamentus.com.br/resultado.php'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        
        # Renomeia e limpa colunas
        rename_map = {'Papel': 'ticker', 'Cotação': 'price', 'P/L': 'pl', 'P/VP': 'pvp', 'EV/EBIT': 'ev_ebit', 'ROIC': 'roic', 'Liq.2meses': 'liquidezmediadiaria'}
        df.rename(columns=rename_map, inplace=True)
        
        for col in df.columns:
            if df[col].dtype == object and col != 'ticker':
                df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Ajustes de porcentagem
        df['roic'] = df['roic'] / 100
        
        # Cálculos de LPA e VPA
        df['lpa'] = df.apply(lambda x: x['price'] / x['pl'] if x['pl'] != 0 else 0, axis=1)
        df['vpa'] = df.apply(lambda x: x['price'] / x['pvp'] if x['pvp'] != 0 else 0, axis=1)
        
        return df
    except: return pd.DataFrame()

# ==============================================================================
# 📺 INTERFACE (UI)
# ==============================================================================

# --- HEADER ---
c_logo, c_title = st.columns([1, 8])
with c_logo: 
    st.image(URL_DO_ICONE, width=70) # Usa o logo do GitHub via Proxy
with c_title: 
    st.markdown("<h2 style='margin-top:10px'>SCOPE3 v3.1 <span style='font-size:14px;color:#9933ff'>| AI POWERED</span></h2>", unsafe_allow_html=True)

st.divider()

# --- MODAL (POP-UP) DA INTELIGÊNCIA ---
@st.dialog("🧠 DECODE INTELLIGENCE", width="large")
def show_ai_decode(ticker, row, details):
    st.markdown(f"### 🎯 ALVO: {ticker}")
    
    # Bloco de Informações Básicas
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='info-card'><div class='info-label'>EMPRESA</div><div class='info-val'>{details.get('Empresa', 'N/A')}</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='info-card'><div class='info-label'>SETOR</div><div class='info-val'>{details.get('Setor', 'N/A')}</div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='info-card'><div class='info-label'>SEGMENTO</div><div class='info-val'>{details.get('Segmento', 'N/A')}</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # Chama a IA ao vivo
    with st.spinner("🛰️ SATÉLITE SCOPE3: ANALISANDO RISCOS E FUNDAMENTOS..."):
        analise = get_ai_analysis(ticker, row['price'], row['ValorJusto'], details)
    
    # Exibe o resultado da IA (Com cor especial se for Alerta)
    if "ALERTA" in analise.upper() or "RISCO" in analise.upper() or "CAVEIRA" in analise.upper():
        st.markdown(f"""
        <div class='risk-alert'>
            <div class='risk-title'>⚠️ ALERTA DE RISCO DETECTADO</div>
            {analise.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class='ai-box'>
            <div class='ai-title'>🧠 ANÁLISE TÁTICA (GEMINI)</div>
            {analise.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)

# --- LÓGICA DE CARREGAMENTO ---
if 'market_data' not in st.session_state:
    if st.button("⚡ INICIAR SISTEMA (CARREGAR BASE)"):
        with st.spinner("Baixando dados da B3..."):
            df = get_data_direct()
            
            # Filtra "Zumbis" (Sem liquidez ou preço zero)
            mask_zombie = (df['liquidezmediadiaria'] > 0) & (df['price'] > 0)
            df = df[mask_zombie].copy()
            
            # Cálculos Graham
            # Proteção contra raiz quadrada negativa (Prejuízo) -> Vira Zero
            df['graham_term'] = 22.5 * df['lpa'] * df['vpa']
            df['graham_term'] = df['graham_term'].apply(lambda x: x if x > 0 else 0)
            df['ValorJusto'] = np.sqrt(df['graham_term'])
            
            df['Margem'] = (df['ValorJusto'] / df['price']) - 1
            
            st.session_state['market_data'] = df
            st.rerun()
else:
    # --- TELA PRINCIPAL (DASHBOARD) ---
    df = st.session_state['market_data']
    st.success(f"BASE OPERACIONAL: {len(df)} ATIVOS RASTREADOS.")
    
    # Seletor de Ativo
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        target = st.selectbox("SELECIONE O ALVO:", options=sorted(df['ticker'].unique()), placeholder="Ex: LIGT3, OIBR3, PETR4...")
    
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        # Botão que aciona a IA
        if st.button("🧠 DECODE"):
            if target:
                row = df[df['ticker'] == target].iloc[0]
                # Busca detalhes extras (Setor) antes de chamar o modal
                with st.spinner("BUSCANDO DADOS CONFIDENCIAIS..."):
                    details = get_stock_details(target)
                show_ai_decode(target, row, details)
            else:
                st.warning("Selecione um ativo primeiro.")

    # Tabela Completa (Opcional)
    st.markdown("---")
    if st.checkbox("MOSTRAR BASE DE DADOS COMPLETA (SCANNER)"):
        st.dataframe(df)

# Footer discreto
st.markdown("<div style='text-align:center;color:#333;font-size:10px;margin-top:50px'>SCOPE3 AI SYSTEM - GEMINI INSIDE v3.1</div>", unsafe_allow_html=True)
