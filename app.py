import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import google.generativeai as genai
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime, timedelta
import db
import time
import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
import extra_streamlit_components as stx
import edge_tts
import asyncio
import nest_asyncio
nest_asyncio.apply() # Fix for Streamlit's event loop

load_dotenv()

# LOCAL DEV ONLY: Allow OAuth over HTTP (fixes "InsecureTransportError")
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ==============================================================================
# 🛠️ CONFIG DO APP
# ==============================================================================
URL_DO_ICONE = "https://wsrv.nl/?url=raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"
st.set_page_config(page_title="SCOPE3 ULTIMATE", page_icon=URL_DO_ICONE, layout="wide", initial_sidebar_state="collapsed")

# 🍪 COOKIE MANAGER
cookie_manager = stx.CookieManager(key="scope3_auth")

# ==============================================================================
# 🧠 INTELIGÊNCIA ARTIFICIAL (MOTOR V7.1)
# ==============================================================================
if os.getenv("GEMINI_KEY"):
    API_KEY = os.getenv("GEMINI_KEY")
else:
    # Tenta usar st.secrets como fallback
    try:
        if "GEMINI_KEY" in st.secrets: API_KEY = st.secrets["GEMINI_KEY"]
        else: API_KEY = ""
    except: API_KEY = "" 

ACTIVE_MODEL_NAME = None
IA_AVAILABLE = False
STARTUP_MSG = ""

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as e:
            STARTUP_MSG = f"Erro lista: {str(e)}"

        if available_models:
            if 'models/gemini-1.5-flash' in available_models: ACTIVE_MODEL_NAME = 'gemini-1.5-flash'
            elif 'models/gemini-1.5-pro' in available_models: ACTIVE_MODEL_NAME = 'gemini-1.5-pro'
            elif 'models/gemini-pro' in available_models: ACTIVE_MODEL_NAME = 'gemini-pro'
            else: ACTIVE_MODEL_NAME = available_models[0].replace('models/', '')
            model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
            IA_AVAILABLE = True
        else:
            ACTIVE_MODEL_NAME = 'gemini-1.5-flash'
            model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
            IA_AVAILABLE = True
            STARTUP_MSG = "⚠️ Forçando conexão"
    except Exception as e:
        IA_AVAILABLE = False
        STARTUP_MSG = f"🔴 OFFLINE: {str(e)}"
else:
    IA_AVAILABLE = False
    STARTUP_MSG = "⚠️ CONFIGURAR SECRET"

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# --- FUNÇÕES DE ANÁLISE (IA) ---
@st.cache_data(ttl=24*3600, show_spinner=False)
def get_ai_generic_analysis(prompt):
    if not IA_AVAILABLE: return f"⚠️ IA INDISPONÍVEL: {STARTUP_MSG}"
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e: return f"⚠️ ERRO DE GERAÇÃO: {str(e)}"

def get_graham_analysis(ticker, price, fair_value, lpa, vpa):
    margin = (fair_value/price) - 1 if price > 0 else 0
    safe_margin = margin > 0.5
    
    extra_instruction = "INVESTIGUE O MOTIVO DO DESCONTO (Risco Crônico ou Oportunidade?). Cite DATAS de eventos críticos (Ex: Início RJ, Fraude)." if safe_margin else "Foque na solidez e proteção do capital."
    
    prompt = f"""
    Atue como um Analista Sênior de Value Investing (Estilo Benjamin Graham).
    ALVO: {ticker}
    DADOS: Preço Atual R${price:.2f} | Preço Justo R${fair_value:.2f} | Margem de Segurança: {margin:.1%}.
    
    Seu Trabalho:
    1. Explique O QUE a empresa faz.
    2. {extra_instruction}
    3. Conclusão: O ativo está descontado em relação aos fundamentos?
    4. Se houve RJ ou dívida grave, cite QUANDO começou. Se já saiu, informe a data de saída.
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação", "Compra" ou "Venda".
    - Use termos como "Atrativo", "Descontado", "Arriscado".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Análise de Fundamentos, Fatos Relevantes (CVM) e RI da {ticker}."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_magic_analysis(ticker, ev_ebit, roic, score):
    prompt = f"""
    Atue como um Gestor de Fundo Quantitativo (Estilo Joel Greenblatt).
    ALVO: {ticker}
    DADOS: EV/EBIT {ev_ebit:.2f} (Quanto menor, mais barata) | ROIC {roic:.1%} (Quanto maior, mais qualidade).
    
    Análise Profunda:
    1. Qualidade: O que torna esse negócio tão rentável (ROIC alto)? Tem vantagens competitivas?
    2. Preço: O mercado está penalizando o ativo (EV/EBIT baixo)? Há razão para isso? (Cite datas se houver eventos recentes).
    3. Veredito: A assimetria Valor vs Preço é favorável?
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Dados Financeiros Padronizados e RI da {ticker}."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_mix_analysis(ticker, price, fair_value, ev_ebit, roic):
    margin = (fair_value/price) - 1 if price > 0 else 0
    prompt = f"""
    ANÁLISE DE ELITE (TOP TIER): {ticker}
    Esta empresa passou nos dois filtros mais exigentes do mundo: GRAHAM (Valor) e MAGIC FORMULA (Qualidade).
    
    DADOS: Margem {margin:.1%} | ROIC {roic:.1%} | EV/EBIT {ev_ebit:.2f}.
    
    Escreva um DOSSIÊ DE CONVICÇÃO ALTA:
    - Por que essa é uma oportunidade rara (Assimetria de Risco/Retorno)?
    - Pontos de atenção para o investidor de longo prazo (5 anos+). Cite datas de grandes ciclos se relevante.
    - Parecer racional baseado nos fundamentos.
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação".
    - Use "Alta Convicção nos Fundamentos".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Demonstrações Financeiras e Relatórios de RI."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_sniper_analysis(ticker, price, fair_value, details):
    prompt = f"""
    RELATÓRIO DE INTELIGÊNCIA TÁTICA: {ticker} ({details.get('Empresa', 'N/A')}).
    Setor: {details.get('Setor', 'N/A')}.
    
    1. FUNDAMENTOS: A saúde financeira é robusta? (Dívida, Margens).
    2. POSICIONAMENTO: É líder? Tem diferencial?
    3. ANÁLISE DE RISCOS:
       - Se houver risco REAL de Falência, Fraude Contábil ou RJ Ativa, inicie este parágrafo OBRIGATORIAMENTE com a tag `[CRITICAL]`.
       - CASO CONTRÁRIO (Dívida normal de setor, processinhos trabalhistas, etc), NÃO USE A TAG.
       - IMPORTANTE: Bancos e Elétricas operam alavancados. ISSO É NORMAL. NÃO use `[CRITICAL]` por dívida nesses setores.
       - Se estiver em RJ, cite a DATA DE INÍCIO.
       - Se já saiu da RJ, cite a DATA DE SAÍDA.
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação" ou "Evitar".
    - Use "Situação Crítica", "Alto Risco", "Cautela Necessária".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Fatos Relevantes CVM, Processos Judiciais e RI da Cia."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_fii_analysis(ticker, price, pvp, dy, details):
    prompt = f"""
    ANÁLISE IMOBILIÁRIA: {ticker} ({details.get('Segmento', 'N/A')}).
    DADOS: P/VP {pvp:.2f} | Dividend Yield {dy:.1%}.
    
    Analise a qualidade do portfólio:
    - Se Tijolo: Localização, vacância, qualidade dos imóveis.
    - Se Papel: Qualidade dos CRIs, indexadores e risco de crédito (Calote?).
    - Preço: O P/VP indica desconto ou ágio?
    
    A renda é sustentável? Cite datas de emissões ou inadimplência se houver.
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Relatórios Gerencias e Informes Trimestrais."
    - Max 6 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_battle_analysis(t1, d1, t2, d2):
    prompt = f"""
    COMPARATIVO DE BATALHA:
    1. {t1}: {d1}
    2. {t2}: {d2}
    
    Qual vence nos fundamentos? Analise P/L, ROIC, Dívida e Crescimento se tiver. Seja direto. Quem ganha? Max 5 linhas.
    """
    return get_ai_generic_analysis(prompt)

def generate_audio(text, key_suffix=""):
    # Generate a unique path based on content hash to avoid re-generating
    import hashlib
    h = hashlib.md5(text.encode()).hexdigest()
    fname = f"tts_{h}_{key_suffix}.mp3"
    
    # If file already exists today? For now just overwrite or use if exists.
    # In a real app we'd manage temp files.
    
    async def _gen():
        voice = "pt-BR-AntonioNeural" # Male Voice Requested by User
        comm = edge_tts.Communicate(text.replace("*", ""), voice) 
        await comm.save(fname)
        return fname
        
    try:
        # Patch is already applied globally
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running (Streamlit logic), use task?
            # Creating a task might not return immediately.
            # Edge-TTS is just a wrapper around web socket.
            # We can try running it in a new loop request or just await if we were async.
            # But we are sync here.
            # Streamlit runs in a loop. nesting asyncio applied allows `loop.run_until_complete`.
            loop.run_until_complete(_gen())
        else:
             loop.run_until_complete(_gen())
    except Exception as e:
         pass # fallback
         
    return fname
@st.cache_data(ttl=3600)
def get_stock_details(ticker):
    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        df_list = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')
        info = {}
        for df in df_list:
            for i in range(len(df)):
                row = df.iloc[i].astype(str).values
                for j in range(0, len(row), 2):
                    key = row[j].replace('?', '').strip(); val = row[j+1].strip()
                    if "Empresa" in key: info['Empresa'] = val
                    if "Setor" in key: info['Setor'] = val
                    if "Subsetor" in key: info['Segmento'] = val
        return info
    except: return {'Empresa': ticker}

@st.cache_data(show_spinner=False)
def get_data_acoes():
    try:
        url = 'https://www.fundamentus.com.br/resultado.php'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        # Include Debt/Equity column
        rename = {'Papel': 'ticker', 'Cotação': 'price', 'P/L': 'pl', 'P/VP': 'pvp', 'EV/EBIT': 'ev_ebit', 'ROIC': 'roic', 'Liq.2meses': 'liquidezmediadiaria', 'Dív.Brut/ Patrim.': 'div_pat'}
        df.rename(columns=rename, inplace=True)
        for c in df.columns:
            if df[c].dtype == object and c != 'ticker':
                df[c] = df[c].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df['roic'] /= 100
        df['lpa'] = df.apply(lambda x: x['price']/x['pl'] if x['pl']!=0 else 0, axis=1)
        df['vpa'] = df.apply(lambda x: x['price']/x['pvp'] if x['pvp']!=0 else 0, axis=1)
        return df
    except: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def get_data_fiis():
    try:
        url = 'https://www.fundamentus.com.br/fii_resultado.php'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        rename = {'Papel': 'ticker', 'Cotação': 'price', 'Dividend Yield': 'dy', 'P/VP': 'pvp', 'Liquidez': 'liquidezmediadiaria', 'Segmento': 'segmento'}
        df.rename(columns=rename, inplace=True)
        for c in df.columns:
            if df[c].dtype == object and c not in ['ticker', 'segmento']:
                df[c] = df[c].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df['dy'] /= 100
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_candle_chart(ticker):
    try:
        symbols_to_try = [f"{ticker}.SA", ticker]
        df = pd.DataFrame()
        for sym in symbols_to_try:
            df = yf.download(sym, period="6mo", interval="1d", progress=False)
            if not df.empty and len(df) > 5: break
        if not df.empty and len(df) > 5:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if 'Open' in df.columns and 'Close' in df.columns:
                fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#00ff41', decreasing_line_color='#ff4444')])
                fig.update_layout(xaxis_rangeslider_visible=False, plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'), margin=dict(l=10, r=10, t=30, b=10), height=350, title=dict(text=f"GRÁFICO DIÁRIO: {ticker}", x=0.5, font=dict(size=14, color='#00ff41')))
                return fig
        return None
    except: return None

# ==============================================================================
# 🎨 ESTILOS CSS
# ==============================================================================
st.markdown(f"""
<head>
    <link rel="apple-touch-icon" href="{URL_DO_ICONE}">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap" rel="stylesheet">
</head>
<style>
    /* -------------------------------------------------------------------------
       THEME: FINTECH DARK (Solid, Premium)
       ------------------------------------------------------------------------- */
    .stApp {{
        background-color: #0e1117 !important; /* Solid Dark Background */
        background-image: none !important;
    }}
    
    /* GLOBAL TYPOGRAPHY - SAFETY FIX FOR ICONS */
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    /* Do NOT use * {{ font-family: ... }} as it breaks Material Icons */
    
    h1, h2, h3, h4, h5, h6 {{
        color: #FFFFFF !important; /* White Text */
        font-weight: 700 !important;
    }}
    p, div, span, label, li {{
        color: #EDEDED !important; /* Light Grey Text */
    }}
    
    /* INPUT LABELS - High Visibility */
    .stNumberInput label, .stSelectbox label, .stTextInput label, .stMultiSelect label, .stSlider label {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }}
    
    /* GLASSMORPHISM CARDS */
    .glass-card {{
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        color: white;
        margin-bottom: 20px;
        transition: transform 0.2s ease;
    }}
    .glass-card:hover {{
        transform: translateY(-2px);
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.2);
    }}

    /* HERO SCORE CARD (The "340" style) */
    .score-circle {{
        width: 240px;
        height: 240px;
        border-radius: 50%;
        border: 2px solid rgba(255,255,255,0.1);
        border-top: 2px solid #5DD9C2; /* Teal Accent */
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0) 70%);
        margin: 0 auto;
        box-shadow: 0 0 30px rgba(93, 217, 194, 0.1);
    }}
    .score-val {{ font-size: 28px; font-weight: 800; color: #fff; }}
    .score-label {{ font-size: 12px; font-weight: 500; color: #a0a0a0; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }}
    
    /* NAVIGATION BAR (Styled Tabs) */
    .stTabs {{
        background: rgba(0,0,0,0.3);
        border-radius: 50px;
        padding: 5px 10px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.05);
        display: inline-block;
        margin-bottom: 30px !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        border-bottom: none !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent !important;
        border: none !important;
        color: #CCC !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 8px 16px !important;
        border-radius: 30px !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: rgba(255,255,255,0.1) !important;
        color: #fff !important;
    }}
    
    /* INPUTS & BUTTONS */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div {{
        background: rgba(0, 0, 0, 0.3) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border-radius: 12px !important;
        font-weight: 500 !important;
    }}
    /* Dropdown Options - ULTIMATE FIX FOR VISIBILITY */
    /* Container Background */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"], div[role="listbox"] {{
        background-color: #ffffff !important;
    }}
    
    /* Force BLACK text on EVERYTHING inside the popover */
    div[data-baseweb="popover"] * {{
        color: #000000 !important;
    }}

    /* Option Containers */
    li[data-baseweb="option"], div[role="option"] {{
        background-color: #ffffff !important;
        color: #000000 !important;
    }}
    
    /* Highlight Selection (Teal w/ Black Text) */
    li[data-baseweb="option"]:hover, div[role="option"]:hover, li[aria-selected="true"], div[aria-selected="true"] {{
        background-color: #5DD9C2 !important;
        color: #000000 !important;
    }}
    
    /* Virtualized List specific */
    div[data-testid="stSelectboxVirtualDropdown"] {{
        background-color: #ffffff !important;
    }}
    
    /* Text inside options - Specific Target */
    div[data-baseweb="select"] span {{
        color: #000000 !important;
    }}
    /* BUTTONS & POPOVERS */
    .stButton > button {{
        background: #5DD9C2 !important; /* Teal Accent */
        color: #000 !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 10px 24px !important;
        transition: all 0.2s !important;
    }}
    
    /* SPECIFIC POPOVER BUTTON STYLING (The "Arrow" Button) */
    /* Target via data-testid to ensure specificity */
    /* SPECIFIC POPOVER BUTTON STYLING (The "Arrow" Button) */
    /* Target via data-testid to ensure specificity */
    div[data-testid="stPopover"] button {{
        background-color: #5DD9C2 !important;
        color: #000 !important;
        border: none !important;
        border-radius: 8px !important; /* Slightly tighter radius for small button */
        
        /* Compact Square Styling - ADAPTIVE */
        padding: 4px 12px !important; /* More horizontal padding */
        min-height: 32px !important;
        height: 32px !important;
        min-width: 42px !important; /* Min width, not fixed */
        width: auto !important;     /* ALLOW GROWTH */
        line-height: 1 !important;
        
        transition: all 0.2s !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important; /* Prevent line breaks */
    }}

    .stButton > button:hover, div[data-testid="stPopover"] button:hover {{
        background: #fff !important;
        box-shadow: 0 0 15px rgba(255,255,255,0.4) !important;
        transform: scale(1.05) !important;
    }}
    
    /* REMOVE DEFAULT PADDING - OPTIMIZED */
    .block-container {{
        padding-top: 0px !important;
        margin-top: -40px !important;
        padding-bottom: 2rem !important;
        max-width: 95% !important;
    }}
    header {{ visibility: hidden; }}
    #MainMenu, footer {{ visibility: hidden; }}

    /* Custom Header Text */
    .header-logo-text {{ font-size: 24px; font-weight: 800; color: #fff; letter-spacing: 1px; }}
    .header-version {{ font-size: 12px; font-weight: 600; color: #5DD9C2; background: rgba(93, 217, 194, 0.15); padding: 2px 6px; border-radius: 4px; margin-left: 10px; }}
    .header-user {{ font-size: 18px; font-weight: 600; color: #fff; margin-right: 15px; }}

    /* -------------------------------------------------------------------------
       MODAL / DIALOG FIXES (Propriedade CSS corrigida)
       ------------------------------------------------------------------------- */
    /* Darker Modal Background to fix contrast */
    /* Darker Modal Background to fix contrast */
    div[data-testid="stDialog"] div[role="dialog"] {{
        background-color: rgba(14, 17, 23, 0.95) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }}

    /* GLOBAL BACKGROUND (Radical Gradient for Depth) */
    .stApp {{
        background: radial-gradient(circle at 50% 10%, #1e2a3a 0%, #0e1117 80%) !important;
        background-attachment: fixed !important;
    }}

    /* GLOBAL BORDERED CONTAINER STYLE (Glass Effect - Stronger Contrast) */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: rgba(255, 255, 255, 0.08) !important; /* Visible white-ish tint */
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.3) !important; /* Crisp border */
        border-radius: 20px !important;
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.5) !important; /* Strong floating shadow */
        padding: 25px !important;
    }}

    div[data-testid="stDialog"] > div {{
        background-color: transparent !important; /* Let parent transparency show */
        color: #FFFFFF !important;
    }}
    
    /* MODAL TYPOGRAPHY CLASSES */
    .modal-header {{
        font-size: 22px;
        font-weight: 800;
        color: #5DD9C2; /* Teal */
        margin-bottom: 20px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .modal-math {{
        background: rgba(255,255,255,0.05);
        padding: 15px;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 14px;
        color: #CCC;
        border: 1px dashed rgba(255,255,255,0.2);
    }}
    .highlight-val {{
        color: #00ff41;
        font-weight: bold;
        font-size: 16px;
    }}
    .modal-text {{
        margin-top: 15px;
        font-size: 14px;
        color: #DDD;
        line-height: 1.6;
    }}
    
    /* AI ANALYSIS BOX */
    .ai-box {{
        margin-top: 20px;
        background: rgba(93, 217, 194, 0.05);
        border: 1px solid rgba(93, 217, 194, 0.2);
        border-radius: 12px;
        padding: 20px;
    }}
    .ai-header {{
        display: flex;
        align-items: center;
        margin-bottom: 15px;
        border-bottom: 1px solid rgba(93, 217, 194, 0.2);
        padding-bottom: 8px;
    }}
    .ai-title {{
        font-weight: 700;
        color: #5DD9C2;
        margin-left: 8px;
        font-size: 14px;
        letter-spacing: 1px;
    }}
    
    /* INFO GRIDS (Tags & Status) */
    .tag-grid, .status-grid {{
        display: flex;
        gap: 10px;
        margin-bottom: 15px;
        flex-wrap: wrap;
    }}
    .info-tag {{
        background: rgba(255,255,255,0.05);
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        min-width: 80px;
    }}
    .info-label {{
        display: block;
        font-size: 10px;
        color: #888;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 2px;
    }}
    .info-val {{
        font-size: 15px;
        font-weight: 700;
        color: #FFF;
    }}
    .status-box {{
        border: 1px solid #333;
        padding: 12px;
        border-radius: 8px;
        flex: 1;
        background: rgba(0,0,0,0.2);
        text-align: center;
    }}
    .status-title {{ font-size: 11px; font-weight:700; text-transform:uppercase; margin-bottom:5px; }}
    .status-result {{ font-size: 16px; font-weight:800; }}
    
    /* RISK ALERT */
    .risk-alert {{
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid #ff4444;
        border-radius: 12px;
        padding: 20px;
        color: #ffcccc;
    }}
    .risk-title {{ font-weight: 800; color: #ff4444; margin-bottom: 10px; display:flex; align-items:center; gap:10px; }}

    
</style>
""", unsafe_allow_html=True)

# Encode Local Image to Base64 to force it in CSS
import base64
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

try:
    img_b64 = get_base64_of_bin_file("bg_fintech.png")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{img_b64}");
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
except: pass


def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- ETF IDENTIFICATION LOGIC ---
KNOWN_UNITS = [
    'ALUP11', 'BPAC11', 'ENGI11', 'KLBN11', 'SANB11', 'SAPR11', 'TAEE11', 
    'TIET11', 'TRPL11', 'ITUB11', 'BBDC11', 'CXSE11', 'SAMB11', 'TASA11',
    'CPLE11', 'SULA11', 'GGBR11'
]

KNOWN_ETFS = [
    'BOVA11', 'SMAL11', 'IVVB11', 'HASH11', 'NASD11', 'SPXI11', 'XINA11', 
    'EURP11', 'GOLD11', 'BBSD11', 'DIVO11', 'FIND11', 'GOVE11', 'ISUS11', 
    'MATB11', 'PIBB11', 'SMLL11', 'XFIX11', 'BRAX11', 'ECOO11', 'IMAB11', 
    'IRFM11', 'TEVA11', 'USDB11', 'B5P211', 'IB5M11', 'B5MB11', 'IMBB11',
    'WRLD11', 'ACWI11', 'ASIA11', 'EMRG11', 'USTK11', 'TECK11', 'DNAI11',
    'GOUL11', 'CMDB11', 'CRPT11', 'QBTC11', 'QETH11', 'ETHE11'
]

def is_likely_etf(ticker):
    # Rule: Must be in the explicit ETF list
    t = ticker.upper().strip()
    return t in KNOWN_ETFS

# ==============================================================================
# 📂 MODAIS (AÇÕES)
# ==============================================================================
# --- RISK MANAGEMENT LOGIC ---
RISKY_TICKERS = [
    'AMER3', 'OIBR3', 'OIBR4', 'LIGT3', 'GOLL4', 'RCLA3', 'VIIA3', 'BHIA3', 'RCSL3', 'RCSL4', 'TCNO3', 'TCNO4'
]

def check_risk(row):
    """
    Returns (True, Risk_Message) if risky, else (False, None).
    Checks:
    1. Blacklist (RJ/Falência)
    2. Massive Debt (Dív.Brut/Patrim > 5)
    """
    ticker = row['ticker'].upper().strip()
    
    # 1. Blacklist Check
    if ticker in RISKY_TICKERS:
        return True, "RECUPERAÇÃO JUDICIAL / ALTO RISCO"
    
    # 2. Debt Check (Massive Debt)
    # Using 'div_pat' (Dividenda Bruta / Patrimônio Líquido)
    if 'div_pat' in row and row['div_pat'] > 5.0:
        return True, f"DÍVIDA MASSIVA ({row['div_pat']:.1f}x PL)"
        
    return False, None

def filter_risky_stocks(df):
    """Removes risky stocks from the DataFrame"""
    if df.empty: return df
    
    # Apply check_risk to each row
    # We keep only rows where check_risk returns False
    # Using a list comprehension for speed
    safe_indices = [i for i, row in df.iterrows() if not check_risk(row)[0]]
    return df.loc[safe_indices]

# ==============================================================================
# 📂 MODAIS (AÇÕES)
# ==============================================================================
@st.dialog("📂 DOSSIÊ GRAHAM", width="large")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']; margem = row['Margem']
    
    # RISK CHECK
    is_risky, risk_msg = check_risk(row)
    
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div>""", unsafe_allow_html=True)
    with c2:
        if is_risky:
            # RISKY STATUS (Red)
            status_color = "#ff4444"
            status_txt = "ALERTA DE RISCO"
            sub_txt = risk_msg
        else:
            # NORMAL LOGIC
            status_color = "#00ff41" if margem > 0 else "#ff4444"
            status_txt = "DESCONTADA" if margem > 0 else "ACIMA DO VI"
            sub_txt = f"Margem: {margem:.1%}"
            
        st.markdown(f"""<div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px; background:rgba(0,0,0,0.5)"><div style="font-size:12px; color:#aaa">STATUS</div><div style="font-size:20px; font-weight:bold; color:{status_color}">{status_txt}</div><div style="font-size:14px; margin-top:5px; color:#fff">{sub_txt}</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="modal-text"><b>🔍 ENTENDENDO A LÓGICA:</b> Benjamin Graham...</div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: ANALISANDO..."):
        ai_text = get_graham_analysis(ticker, row['price'], vi, lpa, vpa)
        
        # TTS
        if st.button("🔊 Ouvir", key=f"speak_graham_{ticker}"):
            audio_path = generate_audio(ai_text, f"graham_{ticker}")
            st.audio(audio_path, format="audio/mp3", autoplay=True)
            
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="graham", show_title=True)

@st.dialog("📂 DOSSIÊ MAGIC FORMULA", width="large")
def show_magic_details(ticker, row):
    rev = int(row.get('R_EV', 0)); rroic = int(row.get('R_ROIC', 0)); sc = int(row.get('Score', 0))
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-val">{sc} PONTOS</span></div>""", unsafe_allow_html=True)
    with c2:
        is_good = (row['roic'] > 0.15) and (row['ev_ebit'] > 0)
        status_color = "#00ff41" if is_good else "#ffaa00"
        status_txt = "ALTA QUALIDADE" if is_good else "EM OBSERVAÇÃO"
        st.markdown(f"""<div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px; background:#111"><div style="font-size:12px; color:#aaa">QUALIDADE</div><div style="font-size:18px; font-weight:bold; color:{status_color}">{status_txt}</div><div style="font-size:12px; margin-top:5px; color:#fff">ROIC: {row['roic']:.1%}</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="modal-text"><b>🔍 ENTENDENDO A LÓGICA:</b> Joel Greenblatt...</div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: ANALISANDO..."):
        ai_text = get_magic_analysis(ticker, row['ev_ebit'], row['roic'], sc)
        
        # TTS
        if st.button("🔊 Ouvir", key=f"speak_magic_{ticker}"):
            audio_path = generate_audio(ai_text, f"magic_{ticker}")
            st.audio(audio_path, format="audio/mp3", autoplay=True)

        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)

    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="magic", show_title=True)

# NOVO MODAL: ELITE MIX
@st.dialog("🏆 DOSSIÊ ELITE MIX", width="large")
def show_mix_details(ticker, row):
    st.markdown(f'<div class="modal-header">ANÁLISE DE ELITE: {ticker}</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">MARGEM GRAHAM</span><span class="info-val">{row['Margem']:.1%} (Positiva)</span></div><div class="info-tag"><span class="info-label">ROIC</span><span class="info-val">{row['roic']:.1%} (Eficiente)</span></div><div class="info-tag"><span class="info-label">EV/EBIT</span><span class="info-val">{row['ev_ebit']:.2f} (Barata)</span></div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="modal-text" style="color:#00ff41; border:1px solid #00ff41; padding:10px; border-radius:4px; text-align:center; font-weight:bold;">🏆 ESTE ATIVO PASSOU NOS DOIS FILTROS MAIS RÍGIDOS DO MERCADO.</div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: VALIDANDO ELITE..."):
        ai_text = get_mix_analysis(ticker, row['price'], row['ValorJusto'], row['ev_ebit'], row['roic'])
        
        # TTS
        if st.button("🔊 Ouvir", key=f"speak_mix_{ticker}"):
            audio_path = generate_audio(ai_text, f"mix_{ticker}")
            st.audio(audio_path, format="audio/mp3", autoplay=True)

        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)

    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="mix", show_title=True)

@st.dialog("🧠 DECODE INTELLIGENCE", width="large")
def show_ai_decode(ticker, row, details):
    st.markdown(f"### 🎯 ALVO: {ticker}")
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">EMPRESA</span><span class="info-val">{details.get('Empresa', 'N/A')}</span></div><div class="info-tag"><span class="info-label">SETOR</span><span class="info-val">{details.get('Setor', 'N/A')}</span></div><div class="info-tag"><span class="info-label">SEGMENTO</span><span class="info-val">{details.get('Segmento', 'N/A')}</span></div></div>""", unsafe_allow_html=True)
    graham_ok = row['Margem'] > 0; magic_ok = (row['roic'] > 0.10) and (row['ev_ebit'] > 0)
    st.markdown(f"""<div class="status-grid"><div class="status-box" style="border-color: {'#00ff41' if graham_ok else '#ff4444'};"><div class="status-title" style="color:{'#00ff41' if graham_ok else '#ff4444'}">MÉTODO GRAHAM</div><div class="status-result" style="color:{'#00ff41' if graham_ok else '#ff4444'}">{'✅ POSITIVO' if graham_ok else '❌ NEGATIVO'}</div><div style="font-size:10px; color:#aaa; margin-top:2px">{'MARGEM: ' + f"{row['Margem']:.1%}" if graham_ok else 'SEM MARGEM'}</div></div><div class="status-box" style="border-color: {'#00ff41' if magic_ok else '#ffaa00'};"><div class="status-title" style="color:{'#00ff41' if magic_ok else '#ffaa00'}">MAGIC FORMULA</div><div class="status-result" style="color:{'#00ff41' if magic_ok else '#ffaa00'}">{'✅ APROVADA' if magic_ok else '⚠️ ATENÇÃO'}</div><div style="font-size:10px; color:#aaa; margin-top:2px">{'ROIC: ' + f"{row['roic']:.1%}" if magic_ok else 'ROIC BAIXO'}</div></div></div><hr style="border-color: #333; margin: 15px 0;">""", unsafe_allow_html=True)
    with st.spinner("🛰️ SATÉLITE: PROCESSANDO..."):
        analise = get_sniper_analysis(ticker, row['price'], row['ValorJusto'], details)
        
    # LOGIC UPDATE: Triggers only on CRITICAL keywords, avoiding false positives from headers
    # LOGIC UPDATE: Triggers ONLY if the AI explicitly flagged as [CRITICAL]
    # This prevents False Positives for banks or standard sector risks
    is_critical = "[CRITICAL]" in analise
    
    # Remove the tag for display purposes so it looks clean
    display_text = analise.replace("[CRITICAL]", "").strip()
    
    # TTS BUTTON (Universal)
    if st.button("🔊 Ouvir Análise", key=f"speak_decode_{ticker}"):
        audio_path = generate_audio(display_text, f"decode_{ticker}")
        st.audio(audio_path, format="audio/mp3", autoplay=True)
    
    if is_critical:
        st.markdown(f"<div class='risk-alert'><div class='risk-title'>💀 ALERTA DE RISCO DETECTADO</div>{display_text.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    else:
        # Standard Blue/Neutral Box
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{display_text.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="ai", show_title=True)

# ==============================================================================
# 📂 MODAIS (FIIs)
# ==============================================================================
@st.dialog("🏢 FII DECODE", width="large")
def show_fii_decode(ticker, row, details):
    st.markdown(f"### 🏢 ALVO: {ticker}")
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">SEGMENTO</span><span class="info-val">{row['segmento']}</span></div><div class="info-tag"><span class="info-label">Cotação</span><span class="info-val">{format_brl(row['price'])}</span></div><div class="info-tag"><span class="info-label">DY (12M)</span><span class="info-val">{row['dy']:.2%}</span></div></div>""", unsafe_allow_html=True)
    pvp_bom = 0.8 <= row['pvp'] <= 1.10; dy_bom = row['dy'] > 0.08
    st.markdown(f"""<div class="status-grid"><div class="status-box" style="border-color: {'#00ff41' if pvp_bom else '#ffaa00'};"><div class="status-title" style="color:{'#00ff41' if pvp_bom else '#ffaa00'}">P/VP (PREÇO JUSTO)</div><div class="status-result" style="color:{'#00ff41' if pvp_bom else '#ffaa00'}">{'✅ NO PREÇO' if pvp_bom else '⚠️ DESCOLADO'}</div><div style="font-size:10px; color:#aaa; margin-top:2px">{row['pvp']:.2f}</div></div><div class="status-box" style="border-color: {'#00ff41' if dy_bom else '#ffaa00'};"><div class="status-title" style="color:{'#00ff41' if dy_bom else '#ffaa00'}">DIVIDENDOS</div><div class="status-result" style="color:{'#00ff41' if dy_bom else '#ffaa00'}">{'✅ ATRATIVO' if dy_bom else '⚠️ BAIXO'}</div><div style="font-size:10px; color:#aaa; margin-top:2px">{row['dy']:.1%} a.a.</div></div></div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: ANALISANDO FII..."):
        ai_text = get_fii_analysis(ticker, row['price'], row['pvp'], row['dy'], details)
        
        # TTS
        if st.button("🔊 Ouvir", key=f"speak_fii_{ticker}"):
            audio_path = generate_audio(ai_text, f"fii_{ticker}")
            st.audio(audio_path, format="audio/mp3", autoplay=True)

        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>ANÁLISE DE RENDA (IA)</span></div>{ai_text}</div>", unsafe_allow_html=True)

    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="fii_modal", show_title=True)

# ==============================================================================
# 📂 MODAIS (ETFs)
# ==============================================================================
@st.dialog("🌎 ETF DECODE", width="large")
def show_etf_decode(ticker, row):
    st.markdown(f"### 🌎 ALVO: {ticker}")
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">COTAÇÃO</span><span class="info-val">{format_brl(row['price'])}</span></div><div class="info-tag"><span class="info-label">LIQUIDEZ DIÁRIA</span><span class="info-val">{format_brl(row['liquidezmediadiaria'])}</span></div></div>""", unsafe_allow_html=True)
    
    st.markdown("""<div class="modal-text"><b>🔍 SOBRE ETFs:</b> Fundos de Índice buscam replicar a performance de um indicador (como Ibovespa, S&P500). São ótimos para diversificação passiva.</div>""", unsafe_allow_html=True)

    with st.spinner("🤖 IA: ANALISANDO ETF..."):
        prompt = f"Analise o ETF {ticker} (Preço {format_brl(row['price'])}). O que ele segue? É dolarizado? É bom para longo prazo? Max 4 linhas."
        ai_text = get_ai_generic_analysis(prompt)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>ANÁLISE DE FUNDO (IA)</span></div>{ai_text}</div>", unsafe_allow_html=True)

    st.markdown("---")
    with st.popover(f"⬆️ ADICIONAR {ticker} À CARTEIRA", width='stretch'): 
         render_add_wallet_form(ticker, row['price'], key_suffix="etf_modal", show_title=True)

# ==============================================================================
# 📺 UI PRINCIPAL
# ==============================================================================
# ==============================================================================
# 🔐 AUTHENTICATION & SESSION
# ==============================================================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'username' not in st.session_state: st.session_state['username'] = None

# Check Cookies
if not st.session_state['logged_in']:
    cookies = cookie_manager.get_all()
    if "auth_token" in cookies:
        token = cookies["auth_token"]
        user = db.get_user_by_session(token)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = user['id']
            st.session_state['username'] = user['username']
            st.rerun()

def login_page():
    # CUSTOM LOGIN LAYOUT (2 Columns)
    # The user wants the image on the left and compact login on the right
    
    # Force full height container to center vertically if possible, or just top spacing
    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
    
    c_img, c_form = st.columns([1.5, 1]) # Image wider or balanced
    
    with c_img:
        # User uploaded image: uploaded_image_0_1766453858660.png
        # We need to make sure we can access it.
        # Ideally, we should move it to assets, but for now we reference the absolute path or relative if in same dir.
        # Assuming the user allows us to reference the artifact directly or we have a local copy.
        # Use st.image with the full path provided by the system for the artifact.
        
        # NOTE: Using the path provided in user context
        img_path = "assets/uploaded_image_0_1766453858660.png"
        
        try:
            st.image(img_path, use_container_width=True)
            st.caption("Terminal Access v15.0 - Secure Node")
        except:
            st.warning("Imagem de capa não encontrada.")
            st.image(URL_DO_ICONE, width=150)

    with c_form:
        # Compact Container for Form
        with st.container(border=True):
            st.markdown(f"""<div style="text-align:center"><img src="{URL_DO_ICONE}" width="60" style="border-radius:50%"></div>""", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align:center; margin-bottom:20px; color:#5DD9C2'>ACESSO RESTRITO</h3>", unsafe_allow_html=True)
            
            t_login, t_reg = st.tabs(["ENTRAR", "NOVA CONTA"])
            
            with t_login:
                st.markdown("<br>", unsafe_allow_html=True)
                u = st.text_input("USUÁRIO", key="l_user")
                p = st.text_input("SENHA", type="password", key="l_pass")
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("🚀 ACESSAR SISTEMA", key="btn_login", use_container_width=True):
                    user = db.verify_user(u, p)
                    if user:
                        token = db.create_session(user['id'])
                        cookie_manager.set("auth_token", token, expires_at=datetime.now() + timedelta(days=30))

                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user['id']
                        st.session_state['username'] = user['username']
                        time.sleep(1)
                        st.rerun()
                    else: st.error("ACESSO NEGADO")
                
                st.markdown("---")
                st.markdown("---")
                
                # --- GOOGLE AUTH: WEB FLOW (CLOUD COMPATIBLE) ---
                # 1. Configuration (Local vs Cloud)
                client_config = None
                redirect_uri = "http://localhost:8501" # Default Local
                
                if "google_auth" in st.secrets:
                    # CLOUD Mode (Secrets)
                    client_config = dict(st.secrets["google_auth"])
                    redirect_uri = st.secrets.get("REDIRECT_URI", "https://scope3.streamlit.app")
                elif os.path.exists('client_secret.json'):
                    # LOCAL Mode (File)
                    client_config = 'client_secret.json'
                
                if client_config:
                    try:
                        # Scopes
                        SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
                        
                        # Init Flow
                        if isinstance(client_config, str):
                            flow = Flow.from_client_secrets_file(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
                        else:
                            flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
                        
                        # 2. Check for Callback Code
                        auth_code = st.query_params.get("code")
                        
                        if auth_code:
                            with st.spinner("Verificando credenciais Google..."):
                                flow.fetch_token(code=auth_code)
                                credentials = flow.credentials
                                
                                sess = requests.Session()
                                sess.headers.update({'Authorization': f'Bearer {credentials.token}'})
                                user_info = sess.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
                                
                                user = db.login_google_user(user_info['email'], user_info['id'])
                                if user:
                                    token = db.create_session(user['id'])
                                    cookie_manager.set("auth_token", token, expires_at=datetime.now() + timedelta(days=30))
                                    
                                    st.session_state['logged_in'] = True
                                    st.session_state['user_id'] = user['id']
                                    st.session_state['username'] = user['username'] 
                                    st.success("AUTENTICADO!")
                                    # Clear params to prevent re-trigger
                                    st.query_params.clear()
                                    time.sleep(1)
                                    st.rerun()
                        else:
                            # 3. Show Login Link
                            auth_url, _ = flow.authorization_url(prompt='consent')
                            st.link_button("🔵 ENTRAR COM GOOGLE", auth_url, use_container_width=True)
                            
                    except Exception as e:
                        st.error(f"Erro Configuração Google: {str(e)}")
                        st.caption("Verifique se a REDIRECT_URI no console do Google e secrets coincidem.")
                else:
                    st.caption("⚠️ Google Login indisponível (Sem config).")
                    
                # DEBUG: DELETE THIS AFTER FIXING
                st.info(f"🔧 DEBUG STATUS:\n- Secrets Detectados: {'google_auth' in st.secrets}\n- Redirect URI usado: {redirect_uri}")

            with t_reg:
                st.markdown("<br>", unsafe_allow_html=True)
                nu = st.text_input("NOVO USUÁRIO", key="r_user")
                np = st.text_input("SENHA", type="password", key="r_pass")
                nm = st.text_input("EMAIL", key="r_mail")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✨ REGISTRAR", key="btn_reg", use_container_width=True):
                    ok, msg = db.create_user(nu, np, nm)
                    if ok: st.success("SUCESSO! FAÇA LOGIN."); time.sleep(2)
                    else: st.error(msg)

if not st.session_state['logged_in']:
    login_page()
    st.stop()

# ==============================================================================
# 📺 UI PRINCIPAL
# ==============================================================================




# REFACTORED WALLET FUNCTION
def render_add_wallet_form(ticker, current_price, key_suffix="", show_title=False):
    # Using st.form to prevent popover closing/rerun issues during input
    with st.form(key=f"form_add_{ticker}_{key_suffix}"):
        if show_title: st.markdown("##### 💰 ADICIONAR À CARTEIRA")
        st.markdown(f"**{ticker}**")
        qty = st.number_input("QUANTIDADE", min_value=1, step=1, value=100)
        price = st.number_input("PREÇO DE COMPRA", min_value=0.01, step=0.1, value=float(current_price))
        
        # Submit Button
        if st.form_submit_button("CONFIRMAR APORTE"):
            ok, msg = db.add_to_wallet(st.session_state['user_id'], ticker, qty, price)
            if ok: 
                # Success message INSIDE the form/container, below the button
                st.success(f"✅ {msg}")
                time.sleep(1.5) # Give detailed time to read
                st.rerun()
            else: 
                st.error(msg)

@st.dialog("💰 ADICIONAR À CARTEIRA")
def add_wallet_dialog(ticker, current_price):
    render_add_wallet_form(ticker, current_price, key_suffix="dialog", show_title=False)
        
# ------------------------------------------------------------------------------
# LAYOUT & NAVIGATION (TOP NAVBAR)
# ------------------------------------------------------------------------------
# Remove Sidebar content (Terminal Mode leftovers)
st.sidebar.empty()

# Custom Top Header
# Custom Top Header - RENOVATED
# Layout: [Logo + Title] [Tabs (Center)] [User + Logout (Right)]
c1, c2, c3 = st.columns([3, 5, 2])

with c1:
    h_col1, h_col2 = st.columns([1, 4])
    with h_col1: st.image(URL_DO_ICONE, width=55)
    with h_col2: st.markdown("<div style='margin-top:10px;'><span class='header-logo-text'>SCOPE3</span> <span class='header-version'>V15.0</span></div>", unsafe_allow_html=True)

with c2: 
    pass # Tabs will render below, but visually they act as the navbar

with c3:
    # Flex container for User + Button
    st.markdown(f"""
    <div style="display:flex; justify-content:flex-end; align-items:center; margin-top:5px;">
        <span class="header-user">👤 {st.session_state['username']}</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("SAIR", key="logout_top", use_container_width=True):
        # 1. Try to delete specific token from DB (if available)
        cookies = cookie_manager.get_all()
        # 2. NUCLEAR OPTION: Delete ALL sessions for this user from DB
        # This prevents auto-relogin even if cookie persists
        if st.session_state['user_id']:
            db.delete_all_user_sessions(st.session_state['user_id'])
            
        # 3. Delete from Browser (Safe)
        try:
            cookie_manager.delete("auth_token")
        except KeyError:
            pass # Already deleted or not found
        except Exception:
            pass
        
        # 4. Clear Session State
        st.session_state['logged_in'] = False
        st.session_state['user_id'] = None
        st.session_state['username'] = None
        
        # Wait for cookie deletion to sync with browser
        st.success("Saindo do sistema...")
        time.sleep(2) 
        st.rerun()


# MAIN NAVIGATION TABS
# MAIN NAVIGATION TABS
# ------------------------------------------------------------------------------
# HELPER FUNCTIONS FOR DATA LOADING (PIPELINES)
# ------------------------------------------------------------------------------
def load_data_acoes_pipeline():
    df_a = get_data_acoes() 
    if not df_a.empty:
        # FILTER: Exclude ETFs
        df_a['IsETF'] = df_a['ticker'].apply(is_likely_etf)
        df_acoes = df_a[~df_a['IsETF']].copy()
        
        # Apply filters
        df_acoes = df_acoes[(df_acoes['liquidezmediadiaria']>0) & (df_acoes['price']>0)].copy()

        # GRAHAM FORMULA
        df_acoes['graham_term'] = (22.5 * df_acoes['lpa'] * df_acoes['vpa']).apply(lambda x: x if x>0 else 0)
        df_acoes['ValorJusto'] = np.sqrt(df_acoes['graham_term'])
        df_acoes['Margem'] = (df_acoes['ValorJusto']/df_acoes['price']) - 1
        
        # MAGIC FORMULA
        df_magic_calc = df_acoes[(df_acoes['ev_ebit']>0) & (df_acoes['roic']>0)].copy()
        if not df_magic_calc.empty:
            df_magic_calc['R_EV'] = df_magic_calc['ev_ebit'].rank(ascending=True)
            df_magic_calc['R_ROIC'] = df_magic_calc['roic'].rank(ascending=False)
            df_magic_calc['Score'] = df_magic_calc['R_EV'] + df_magic_calc['R_ROIC']
            df_magic_calc['MagicRank'] = df_magic_calc['Score'].rank(ascending=True)
        
        # Merge Magic Formula ranks
        df_acoes = df_acoes.merge(df_magic_calc[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
        
        st.session_state['market_data'] = df_acoes
        return True
    return False

def load_data_etfs_pipeline():
    try:
        tickers_sa = [f"{t}.SA" for t in KNOWN_ETFS]
        batch = yf.download(tickers_sa, period="5d", interval="1d", group_by='ticker', progress=False)
        etf_data = []
        for t_raw in KNOWN_ETFS:
            t_sa = f"{t_raw}.SA"
            try:
                if len(tickers_sa) > 1: df_t = batch[t_sa]
                else: df_t = batch
                
                if not df_t.empty:
                    last_row = df_t.iloc[-1]
                    price = float(last_row['Close'])
                    vol = float(last_row['Volume']) * price
                    if price > 0:
                        etf_data.append({'ticker': t_raw, 'price': price, 'liquidezmediadiaria': vol, 'pvp': 0, 'dy': 0})
            except: pass
        
        if etf_data:
            df_etf = pd.DataFrame(etf_data)
            df_etf = df_etf.sort_values('liquidezmediadiaria', ascending=False)
            st.session_state['market_data_etfs'] = df_etf
            return True
        return False
    except Exception as e:
        return str(e)

tab_carteira, tab_acoes, tab_etfs, tab_mix, tab_fiis, tab_arena = st.tabs(["CARTEIRA", "AÇÕES", "ETFs", "ELITE MIX", "FIIs", "ARENA"])

# ------------------------------------------------------------------------------
# PÁGINA 0: CARTEIRA PESSOAL (HERO DASHBOARD)
# ------------------------------------------------------------------------------
with tab_carteira:
    # 1. Fetch Data
    df_w = db.get_portfolio(st.session_state['user_id'])
    
    if df_w.empty:
        st.info("Sua carteira está vazia. Comece adicionando ativos nas abas 'AÇÕES' ou 'FIIs'.")
    else:
        # 2. Update Prices
        tickers = [f"{t}.SA" for t in df_w['ticker'].unique()]
        try:
            raw_data = yf.download(tickers, period="5d", progress=False)['Close']
            if not raw_data.empty: curr_data = raw_data.ffill().iloc[-1]
            else: curr_data = pd.Series()
        except: curr_data = pd.Series()

        total_invested = 0
        total_current = 0
        
        # Calculate totals for existing items
        df_w['curr_price'] = 0.0
        df_w['total_val'] = 0.0
        
        for idx, row in df_w.iterrows():
            t_sa = f"{row['ticker']}.SA"
            c_price = 0
            # Price Logic
            if isinstance(curr_data, (int, float, np.number)):
                 if len(df_w) == 1: c_price = float(curr_data)
            elif isinstance(curr_data, pd.Series):
                c_price = float(curr_data[t_sa]) if t_sa in curr_data else 0
            elif isinstance(curr_data, pd.DataFrame): 
                c_price = float(curr_data[t_sa]) if t_sa in curr_data.columns else 0
            
            # Fallback
            if c_price == 0 and 'market_data' in st.session_state:
                 f = st.session_state['market_data']
                 f_p = f[f['ticker'] == row['ticker']]
                 if not f_p.empty: c_price = float(f_p.iloc[0]['price'])
            
            # Update row (in memory)
            df_w.at[idx, 'curr_price'] = c_price if c_price > 0 else row['avg_price']
            df_w.at[idx, 'total_val'] = df_w.at[idx, 'curr_price'] * row['quantity']
            
            total_invested += row['quantity'] * row['avg_price']
            total_current += df_w.at[idx, 'total_val']

        variation = total_current - total_invested
        var_pct = (variation / total_invested) if total_invested > 0 else 0

        # WRAPPER FOR GLASS CARD EFFECT
        with st.container(border=True):
            # 3. HERO DASHBOARD (Glass Layout - RENOVATED)
            h1, h2 = st.columns([1.2, 1])
            
            # --- LOGIC: ASSET CLASSIFICATION ---
        def get_asset_class(ticker):
            t = ticker.upper().strip()
            if is_likely_etf(t):
                return "ETFs"
            elif t.endswith("11") or t.endswith("11B"):
                 # If ends in 11 and NOT an ETF (checked above), it's likely FII (or Unit)
                 return "FIIs"
            elif t.endswith("3") or t.endswith("4") or t.endswith("5") or t.endswith("6"):
                 return "AÇÕES"
            else:
                 return "OUTROS"

        df_w['Tipo'] = df_w['ticker'].apply(get_asset_class)
        # -----------------------------------

        with h1:
            # CHART 1: ASSET ALLOCATION (BY CLASS)
            # Group by Type
            df_pie = df_w.groupby('Tipo')['total_val'].sum().reset_index()
            
            fig_alloc = px.pie(df_pie, values='total_val', names='Tipo', hole=0.6, 
                             color_discrete_map={"AÇÕES": "#5DD9C2", "FIIs": "#8338ec", "ETFs": "#3a86ff", "OUTROS": "#999999"})
            
            fig_alloc.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                margin=dict(t=30, b=20, l=20, r=20),
                legend=dict(font=dict(color="white"), orientation="h", y=-0.1),
                showlegend=True,
                height=300,
                annotations=[dict(text='ALOCAÇÃO', x=0.5, y=0.5, font_size=12, showarrow=False, font_color='white')]
            )
            st.markdown("<div style='text-align:center; font-weight:bold; color:#EEE; margin-bottom:-10px'>ALOCAÇÃO POR CLASSE</div>", unsafe_allow_html=True)
            st.plotly_chart(fig_alloc, width='stretch', config={'displayModeBar': False})
            
        with h2:
            # Privacy Logic
            if 'privacy_show' not in st.session_state: st.session_state['privacy_show'] = False
            
            # Privacy Toggle (Small and discreet)
            c_priv, _ = st.columns([1, 2])
            with c_priv:
                p_icon = "👁️" if st.session_state['privacy_show'] else "🔒"
                if st.button(f"{p_icon}", key="btn_privacy_icon"):
                    st.session_state['privacy_show'] = not st.session_state['privacy_show']
                    st.rerun()

            show = st.session_state['privacy_show']
            val_display = format_brl(total_current) if show else "R$ ---"
            
            # CHART 2: PROFIT RING (DONUT)
            # Logic: 
            # If Profit > 0: Segments = [Invested, Profit]
            # If Loss > 0: Segments = [Remaining, Loss] (To show the 'missing' part)
            
            profit_val = total_current - total_invested
            is_profit = profit_val >= 0
            
            if is_profit:
                # GAIN SCENARIO
                labels = ["APORTE", "LUCRO"]
                values = [total_invested, profit_val]
                colors = ["#1f4e78", "#00ff41"] # Dark Blue, Green
            else:
                # LOSS SCENARIO
                labels = ["SALDO ATUAL", "PREJUÍZO"]
                values = [total_current, abs(profit_val)]
                colors = ["#1f4e78", "#ff4444"] # Dark Blue, Red

            # If values need masking
            if not show:
                # Mock chart for Privacy Mode
                values = [100]
                labels = ["OCULTO"]
                colors = ["#333"]
            
            fig_ring = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.7, 
                                            marker=dict(colors=colors),
                                            textinfo='none', # Hide labels on chart
                                            hoverinfo='label+value+percent' if show else 'none')])

            fig_ring.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=False,
                height=260,
                annotations=[
                    dict(text='<span style="font-size:12px; color:#AAA">PATRIMÔNIO</span><br><span style="font-size:22px; font-weight:bold; color:#FFF">{}</span>'.format(val_display), 
                         x=0.5, y=0.5, showarrow=False, font_size=14)
                ]
            )
            
            st.plotly_chart(fig_ring, width='stretch', config={'displayModeBar': False})
            
            # Bottom Details (Rentabilidade)
            var_pct = (profit_val / total_invested) if total_invested > 0 else 0
            pct_fmt = f"{'+' if is_profit else ''}{var_pct:.1%}" if show else "XX%"
            
            st.markdown(f"""
            <div style="text-align:center; margin-top:-10px;">
                <div style="font-size:14px; color:#EEE;">RENTABILIDADE</div>
                <div style="font-size:24px; font-weight:700; color: {'#5DD9C2' if is_profit else '#FF4444'};">
                    {pct_fmt}
                </div>
                <div style="font-size:12px; color:#DDD;">{format_brl(profit_val) if show else 'R$ ---'}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 4. List Items (Segmented by Type)
        st.markdown("<h5 style='color: white; font-weight: 700;'>🧾 SEUS ATIVOS (POR CATEGORIA)</h5>", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:20px'></div>", unsafe_allow_html=True)

        # Helper to render a section
        def render_wallet_section(title, df_segment):
            if df_segment.empty: return
            
            # Section Title
            st.markdown(f"### {title}")
            st.markdown("<div style='margin-bottom:10px'></div>", unsafe_allow_html=True)
            
            # Header Row
            h1, h2, h3, h4, h5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
            h1.markdown("<span style='color:#AAA; font-weight:700; font-size:11px'>ATIVO</span>", unsafe_allow_html=True)
            h2.markdown("<span style='color:#AAA; font-weight:700; font-size:11px'>PREÇO MÉDIO</span>", unsafe_allow_html=True)
            h3.markdown("<span style='color:#AAA; font-weight:700; font-size:11px'>PREÇO ATUAL</span>", unsafe_allow_html=True)
            h4.markdown("<span style='color:#AAA; font-weight:700; font-size:11px'>RENTABILIDADE</span>", unsafe_allow_html=True)
            h5.markdown("<span style='color:#AAA; font-weight:700; font-size:11px'>AÇÕES</span>", unsafe_allow_html=True)
            st.divider()

            # Rows
            for idx, row in df_segment.iterrows():
                p_var = (row['curr_price'] - row['avg_price']) / row['avg_price'] if row['avg_price'] > 0 else 0
                
                c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
                with c1:
                    st.markdown(f"<span style='font-size:16px; font-weight:700; color:#FFF'>{row['ticker']}</span><br><span style='font-size:11px; color:#CCC'>{int(row['quantity'])} un.</span>", unsafe_allow_html=True)
                with c2:
                    v_avg = format_brl(row['avg_price']) if show else "R$ XX,XX"
                    st.markdown(f"<span style='color:#FFF; font-weight:600'>{v_avg}</span>", unsafe_allow_html=True)
                with c3:
                    v_curr = format_brl(row['curr_price']) if show else "R$ XX,XX"
                    st.markdown(f"<span style='color:#FFF; font-weight:600'>{v_curr}</span>", unsafe_allow_html=True)
                with c4:
                    color = '#5DD9C2' if p_var >= 0 else '#FF4444'
                    v_pct = f"{p_var:.1%}" if show else "XX%"
                    st.markdown(f"<span style='color:{color}; font-weight:bold'>{v_pct}</span>", unsafe_allow_html=True)
                with c5:
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✏️", key=f"edit_{row['ticker']}"):
                            edit_position_dialog(row['ticker'], int(row['quantity']), float(row['avg_price']))
                    with b2:
                        # Use a unique key for popover or button to avoid conflicts if needed, but simple button is fine here
                        if st.button("❌", key=f"del_{row['ticker']}"):
                            ok, msg = db.remove_from_wallet(st.session_state['user_id'], row['ticker'])
                            st.rerun()
                
                st.markdown("<div style='border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom:10px; margin-top:10px;'></div>", unsafe_allow_html=True)

        # Render Sections
        render_wallet_section("🏢 AÇÕES", df_w[df_w['Tipo'] == 'AÇÕES'])
        render_wallet_section("🏗️ FIIs", df_w[df_w['Tipo'] == 'FIIs'])
        render_wallet_section("🌐 ETFs", df_w[df_w['Tipo'] == 'ETFs'])
        render_wallet_section("📦 OUTROS", df_w[df_w['Tipo'] == 'OUTROS'])


            
    # DIALOG FOR EDITING (Moved here)
    @st.dialog("✏️ EDITAR POSIÇÃO")
    def edit_position_dialog(ticker, old_qty, old_avg):
        st.markdown(f"### EDITANDO: {ticker}")
        nq = st.number_input("NOVA QUANTIDADE", value=old_qty, step=1)
        np = st.number_input("NOVO PREÇO MÉDIO", value=float(old_avg), step=0.01)
        if st.button("SALVAR ALTERAÇÕES"):
            ok, msg = db.update_wallet_item(st.session_state['user_id'], ticker, nq, np)
            if ok: st.rerun()
            else: st.error(msg)







# ------------------------------------------------------------------------------
# PÁGINA 1: AÇÕES (O ORIGINAL)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# PÁGINA 1: AÇÕES
# ------------------------------------------------------------------------------
with tab_acoes:

    st.divider()
    if 'market_data' not in st.session_state:
        if st.button("⚡ INICIAR VARREDURA AÇÕES", key="btn_scan_acoes"):
            with st.spinner("Baixando Dados Ações..."):
                df_a = get_data_acoes() # Assuming get_data_acoes() returns the full dataframe
                if df_a.empty:
                    st.warning("Sem dados de ações no momento.")
                else:
                    # FILTER: Exclude ETFs from this tab (using is_likely_etf logic)
                    # We must filter out ETFs because they don't have P/L, ROIC etc like stocks
                    df_a['IsETF'] = df_a['ticker'].apply(is_likely_etf)
                    df_acoes = df_a[~df_a['IsETF']].copy()
                    
                    # --- RISK FILTERING (GLOBAL REMOVED) ---
                    # User wants Risky Assets available in Search (Mira Laser)
                    # We will filter them ONLY in the Top 10 Lists logic later.
                    # df_acoes = filter_risky_stocks(df_acoes) <--- REMOVED
                    
                    # Apply general filters for liquidity and price
                    df_acoes = df_acoes[(df_acoes['liquidezmediadiaria']>0) & (df_acoes['price']>0)].copy()

                    # GRAHAM FORMULA
                    df_acoes['graham_term'] = (22.5 * df_acoes['lpa'] * df_acoes['vpa']).apply(lambda x: x if x>0 else 0)
                    df_acoes['ValorJusto'] = np.sqrt(df_acoes['graham_term'])
                    df_acoes['Margem'] = (df_acoes['ValorJusto']/df_acoes['price']) - 1
                    
                    # MAGIC FORMULA
                    # High ROIC + Low EV/EBIT
                    df_magic_calc = df_acoes[(df_acoes['ev_ebit']>0) & (df_acoes['roic']>0)].copy()
                    if not df_magic_calc.empty:
                        df_magic_calc['R_EV'] = df_magic_calc['ev_ebit'].rank(ascending=True)
                        df_magic_calc['R_ROIC'] = df_magic_calc['roic'].rank(ascending=False)
                        df_magic_calc['Score'] = df_magic_calc['R_EV'] + df_magic_calc['R_ROIC']
                        df_magic_calc['MagicRank'] = df_magic_calc['Score'].rank(ascending=True)
                    
                    # Merge Magic Formula ranks back to the main df_acoes
                    df_acoes = df_acoes.merge(df_magic_calc[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
                    
                    st.session_state['market_data'] = df_acoes
                    st.rerun()
    else:
        # PERSISTENT RE-SCAN BUTTON
        if st.button("🔄 NOVA VARREDURA", key="btn_rescan_acoes"):
             with st.spinner("Atualizando Dados..."):
                 load_data_acoes_pipeline()
                 st.rerun()

        df = st.session_state['market_data']
        st.success(f"BASE AÇÕES: {len(df)} ATIVOS.")
        
        st.markdown("### 🎯 MIRA LASER (IA)")
        c_sel, c_btn, c_unit, _ = st.columns([2, 1, 1.5, 4.5])
        
        with c_unit:
            st.markdown("<br>", unsafe_allow_html=True)
            filter_units = st.toggle("UNITS (11)", key="toggle_units", help="Filtrar apenas Units (Final 11)")
        
        # Filter Logic for Selectbox
        df_search = df.copy()
        if filter_units:
             # Keep only tickers ending in 11 (Units)
             df_search = df_search[df_search['ticker'].str.endswith('11')]
        
        with c_sel: 
            target = st.selectbox("CÓDIGO:", options=sorted(df_search['ticker'].unique()), index=None, placeholder="Ex: TAEE11" if filter_units else "Ex: VALE3", key="target_acoes")
        
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_decode = st.button("🧠 DECODE", key="btn_decode_acoes")
            
        # USER REQUEST: Show Explanation immediately if Toggle is ON
        if filter_units:
            st.info("ℹ️ **VOCÊ ESTÁ ANALISANDO UMA UNIT (FINAL 11):**\n\nUnits são pacotes de ações (Ex: 1 Ordinária + 2 Preferenciais) negociadas como um único ativo. Elas geralmente oferecem maior liquidez e dividendos unificados.")
        
        if target:
            # Safe row retrieval
            row_t = df[df['ticker']==target].iloc[0]
            
            with st.spinner(f"Carregando Gráfico {target}..."):
                fig = get_candle_chart(target)
                if fig: st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
                else: st.warning("Gráfico Indisponível (Sem dados do Yahoo)")
            
            if btn_decode:
                with st.spinner("Analisando..."): details = get_stock_details(target)
                show_ai_decode(target, row_t, details)

        st.markdown("---")
        ic1, ic2 = st.columns(2)
        with ic1: min_liq = st.number_input("LIQUIDEZ MÍNIMA", value=200000, step=50000, key="min_liq_acoes")
        with ic2: invest = st.number_input("SIMULAR APORTE", value=0.0, step=100.0, key="invest_acoes")
        
        df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
        
        
        # New Fintech Card Logic
        def fintech_card(t, p, l1, v1, l2, v2, idx):
            sim_html = ""
            if 'invest_acoes' in st.session_state and st.session_state['invest_acoes'] > 0:
                 qtd_sim = int(st.session_state['invest_acoes'] // p)
                 if qtd_sim > 0:
                     sim_html = f"<div style='margin-top:5px; padding-top:5px; border-top:1px solid #333; font-size:12px; color:#5DD9C2'>💰 APORTE: <b>{qtd_sim}</b> AÇÕES</div>"

            return f"""
            <div class="glass-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <div style="font-size:20px; font-weight:700;">{t}</div>
                    <div style="font-size:18px; color:#5DD9C2; font-weight:600;">{format_brl(p)}</div>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:11px; color:#CCC; text-transform:uppercase;">{l1}</div>
                        <div style="font-size:15px; font-weight:600; color:#FFF;">{v1}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:11px; color:#CCC; text-transform:uppercase;">{l2}</div>
                        <div style="font-size:15px; font-weight:600; color:#FFF;">{v2}</div>
                    </div>
                </div>
                {sim_html}
            </div>
            """
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 💎 SELEÇÃO GRAHAM")
            # Graham Logic: Positive Earnings/Assets & High Margin
            df_g = df_fin[(df_fin['lpa']>0) & (df_fin['vpa']>0)].sort_values('Margem', ascending=False)
            df_g = filter_risky_stocks(df_g).head(10) # Apply Risk Filter & Head 10
            
            if df_g.empty:
                 st.info("Nenhuma ação no padrão Graham hoje.")
            else:
                for i, r in df_g.reset_index().iterrows():
                    st.markdown(fintech_card(r['ticker'], r['price'], "VALOR JUSTO", format_brl(r['ValorJusto']), "POTENCIAL", f"{r['Margem']:.1%}", i+1), unsafe_allow_html=True)
                    bc1, bc2 = st.columns([4, 1])
                    with bc1: 
                        if st.button(f"VER DETALHES", key=f"g_{r['ticker']}"): show_graham_details(r['ticker'], r)
                    with bc2:
                        with st.popover(f"⬆️", width='stretch'): 
                             render_add_wallet_form(r['ticker'], r['price'], key_suffix=f"graham_{i}", show_title=True)
                        
        with c2:
            st.markdown("#### ✨ SELEÇÃO MAGIC")
            # Magic Logic: High Rank
            df_m = df_fin.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True)
            df_m = filter_risky_stocks(df_m).head(10) # Apply Risk Filter
            
            if df_m.empty:
                st.info("Nenhuma ação Magic Formula hoje.")
            else:
                for i, r in df_m.reset_index().iterrows():
                     st.markdown(fintech_card(r['ticker'], r['price'], "EV/EBIT", f"{r['ev_ebit']:.2f}", "ROIC", f"{r['roic']:.1%}", i+1), unsafe_allow_html=True)
                     bc1, bc2 = st.columns([4, 1])
                     with bc1:
                         if st.button(f"VER DETALHES", key=f"m_{r['ticker']}"): show_magic_details(r['ticker'], r)
                     with bc2:
                         with st.popover(f"⬆️", width='stretch'):  
                            render_add_wallet_form(r['ticker'], r['price'], key_suffix=f"magic_{i}", show_title=True)



# ------------------------------------------------------------------------------
# PÁGINA X: ETFs (NOVO!!!)
# ------------------------------------------------------------------------------
with tab_etfs:
    st.divider()
    st.markdown("### 🌎 ETFs & ÍNDICES (FUNDO DE ÍNDICE)")
    
    if 'market_data_etfs' not in st.session_state:
        if st.button("⚡ INICIAR VARREDURA ETFs", key="btn_scan_etfs"):
            with st.spinner("Conectando à B3 (YFinance)..."):
                if load_data_etfs_pipeline(): st.rerun()
                else: st.error("Falha ao obter dados da B3.")
    else:
        # PERSISTENT RE-SCAN BUTTON
        if st.button("🔄 NOVA VARREDURA ETFs", key="btn_rescan_etfs"):
             with st.spinner("Atualizando ETFs..."):
                 load_data_etfs_pipeline()
                 st.rerun()
        df_etf = st.session_state['market_data_etfs']
        st.success(f"BASE ETFs: {len(df_etf)} FUNDOS ENCONTRADOS.")
        
        # --- RESTORED SEARCH SECTION (MIRA LASER FOR ETFs) ---
        st.markdown("### 🎯 ANÁLISE DE FUNDO")
        c_sel, c_btn, _ = st.columns([2, 1, 6])
        with c_sel: target_etf = st.selectbox("CÓDIGO:", options=sorted(df_etf['ticker'].unique()), index=None, placeholder="Ex: IVVB11", key="target_etfs_search")
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            # Use general AI decode for ETFs
            btn_decode_etf_search = st.button("🧠 DECODE", key="btn_decode_etf_search")
            
        if target_etf:
            row_e = df_etf[df_etf['ticker']==target_etf].iloc[0]
            with st.spinner(f"Carregando Gráfico {target_etf}..."):
                fig = get_candle_chart(target_etf)
                if fig: st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
            
            if btn_decode_etf_search:
                with st.spinner("Analisando ETF..."): 
                    prompt = f"Analise o ETF {target_etf}. Dados: Preço R${row_e['price']}. O que ele segue? É dolarizado? É bom para longo prazo? Max 4 linhas."
                    ai_analysis = get_ai_generic_analysis(prompt)
                    st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>ANÁLISE DE ETF (IA)</span></div>{ai_analysis}</div>", unsafe_allow_html=True)

        st.markdown("---")
        # -----------------------------------------------------

        # Display Grid for ETFs (2 per row)
        st.markdown("#### 🔥 ETFs MAIS LÍQUIDOS")
        
        # Grid Layout Logic
        cols = st.columns(2)
        for i, row in df_etf.sort_values('liquidezmediadiaria', ascending=False).reset_index().iterrows():
            with cols[i % 2]:
                st.markdown(f"""
                <div class="glass-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                        <div style="font-size:20px; font-weight:700;">{row['ticker']}</div>
                        <div style="font-size:18px; color:#5DD9C2; font-weight:600;">{format_brl(row['price'])}</div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px">
                        <div>
                            <div style="font-size:11px; color:#CCC; text-transform:uppercase;">LIQUIDEZ</div>
                            <div style="font-size:15px; font-weight:600; color:#FFF;">{format_brl(row['liquidezmediadiaria'])}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Action Buttons
                b1, b2 = st.columns([1, 1])
                with b1:
                    if st.button("🧠 DECODE", key=f"btn_dec_etf_{row['ticker']}"):
                        show_etf_decode(row['ticker'], row)
                with b2:
                    with st.popover(f"⬆️ ADICIONAR", width='stretch'): 
                         render_add_wallet_form(row['ticker'], row['price'], key_suffix=f"etf_{i}", show_title=True)

# ------------------------------------------------------------------------------
# PÁGINA 2: ELITE MIX (NOVO!!!)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# PÁGINA 2: ELITE MIX
# ------------------------------------------------------------------------------
with tab_mix:

    st.divider()
    st.markdown("### 🏆 ELITE MIX: O FILTRO SUPREMO")
    st.info("Este módulo cruza as duas estratégias: A empresa deve ser BARATA (Graham) E EFICIENTE (Magic Formula) ao mesmo tempo.")
    
    if 'market_data' in st.session_state:
        df = st.session_state['market_data']
         # Lógica do Filtro MIX
        # 1. Margem Graham Positiva (> 0)
        # 2. Magic Rank existente (ou seja, tem EV/EBIT e ROIC positivos)
        # 3. Liquidez ok
        # 4. Simulação de Aporte (Se houver)
        sim_qty = 0
        if 'invest_acoes' in st.session_state and st.session_state['invest_acoes'] > 0:
            invest_val = st.session_state['invest_acoes']

        df_mix = df[
            (df['Margem'] > 0) & 
            (df['MagicRank'].notnull()) & 
            (df['liquidezmediadiaria'] > 200000)
        ].copy()
        
        # Ordenação: Prioridade para o Magic Rank (Qualidade), mas garantindo que passou no Graham (Preço)
        df_mix = df_mix.sort_values('MagicRank', ascending=True).head(10)
        
        if len(df_mix) > 0:
            st.success(f"{len(df_mix)} ATIVOS ENCONTRADOS NA ELITE.")
            c1, c2 = st.columns(2)
            for i, r in df_mix.reset_index().iterrows():
                with (c1 if i%2==0 else c2):
                    # Card Personalizado da Elite
                    st.markdown(f"""
                    <div class="glass-card" style="border: 1px solid #FFD700; background: rgba(255, 215, 0, 0.05);">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                            <div style="font-size:20px; font-weight:700; color:#FFD700;">{r['ticker']}</div>
                            <div style="font-size:18px; color:#FFD700; font-weight:600;">{format_brl(r['price'])}</div>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <div>
                                <div style="font-size:11px; color:#CCC; text-transform:uppercase;">MARGEM GRAHAM</div>
                                <div style="font-size:15px; font-weight:600; color:#5DD9C2;">{r['Margem']:.1%}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-size:11px; color:#CCC; text-transform:uppercase;">RANK MAGIC</div>
                                <div style="font-size:15px; font-weight:600; color:#FFF;">#{int(r['MagicRank'])}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    bc1, bc2 = st.columns([4, 1])
                    with bc1:
                         if st.button(f"🏆 DECODE ELITE #{i+1}", key=f"mix_{r['ticker']}"):
                            show_mix_details(r['ticker'], r)
                    with bc2:
                        if st.button("⬆️", key=f"add_mix_{r['ticker']}_{i}"): add_wallet_dialog(r['ticker'], r['price'])
        else:
            st.warning("Nenhum ativo passou nos dois filtros rigorosos simultaneamente hoje.")
            
    else:
        st.warning("⚠️ Por favor, vá na aba AÇÕES e clique em 'INICIAR VARREDURA' primeiro para carregar os dados.")

# ------------------------------------------------------------------------------
# PÁGINA 3: FIIs
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# PÁGINA 3: FIIs
# ------------------------------------------------------------------------------
with tab_fiis:

    st.divider()
    st.markdown("### 🏢 FORTALEZA DE RENDA (FIIs)")
    if 'fiis_data' not in st.session_state:
        if st.button("⚡ INICIAR VARREDURA FIIs", key="btn_scan_fiis"):
            with st.spinner("Baixando Dados FIIs..."):
                st.session_state['fiis_data'] = get_data_fiis()
                st.rerun()
    else:
        # PERSISTENT RE-SCAN BUTTON
        if st.button("🔄 NOVA VARREDURA FIIs", key="btn_rescan_fiis"):
             with st.spinner("Atualizando FIIs..."):
                 st.session_state['fiis_data'] = get_data_fiis()
                 st.rerun()
        df_fii = st.session_state['fiis_data']
        st.success(f"BASE FIIs: {len(df_fii)} FUNDOS.")
        c_sel, c_btn, _ = st.columns([2, 1, 6])
        with c_sel: target_fii = st.selectbox("CÓDIGO FII:", options=sorted(df_fii['ticker'].unique()), index=None, placeholder="Ex: MXRF11", key="target_fii")
        if target_fii:
            row_fii = df_fii[df_fii['ticker']==target_fii].iloc[0]
            with st.spinner(f"Carregando Gráfico {target_fii}..."):
                fig = get_candle_chart(target_fii)
                if fig: st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
            if st.button("🧠 DECODE FII", key="btn_decode_fii"):
                show_fii_decode(target_fii, row_fii, {'Segmento': row_fii['segmento']})
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1: min_dy = st.number_input("DY MÍNIMO (%)", value=6.0, step=0.5, key="min_dy")
        with c2: max_pvp = st.number_input("P/VP MÁXIMO", value=1.10, step=0.05, key="max_pvp")
        with c3: tipo = st.selectbox("SEGMENTO", ["TODOS"] + sorted(df_fii['segmento'].dropna().unique().tolist()), key="seg_fii")
        df_f = df_fii[(df_fii['dy'] >= min_dy/100) & (df_fii['pvp'] <= max_pvp) & (df_fii['liquidezmediadiaria'] > 200000)].copy()
        if tipo != "TODOS": df_f = df_f[df_f['segmento'] == tipo]
        st.markdown("---")
        for i, row in df_f.sort_values('dy', ascending=False).head(10).reset_index().iterrows():
            st.markdown(f"""
            <div class="glass-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div style="font-size:20px; font-weight:700;">{row['ticker']}</div>
                    <div style="font-size:18px; font-weight:600; color:#5DD9C2;">{format_brl(row['price'])}</div>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <div><span style="font-size:11px; color:#CCC;">DY (12M)</span><br><strong style="color:#FFF;">{row['dy']:.1%}</strong></div>
                    <div><span style="font-size:11px; color:#CCC;">P/VP</span><br><strong style="color:#FFF;">{row['pvp']:.2f}</strong></div>
                    <div style="text-align:right;"><span style="font-size:11px; color:#CCC;">SETOR</span><br><span style="color:#FFF;">{row['segmento'][:15]}</span></div>
                </div>
            </div>""", unsafe_allow_html=True)
            bc1, bc2 = st.columns([4, 1])
            with bc1:
                if st.button(f"🏢 ANALISAR {row['ticker']}", key=f"fii_list_{row['ticker']}"):
                    show_fii_decode(row['ticker'], row, {'Segmento': row['segmento']})
            with bc2:
                if st.button(f"⬆️", key=f"add_fii_{row['ticker']}_{i}"): add_wallet_dialog(row['ticker'], row['price'])

# ------------------------------------------------------------------------------
# PÁGINA 4: ARENA
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# PÁGINA 4: ARENA
# ------------------------------------------------------------------------------
with tab_arena:

    st.divider()
    st.markdown("### ⚔️ ARENA DE BATALHA: COMPARADOR")
    if 'market_data' in st.session_state:
        df = st.session_state['market_data']
        c1, c2 = st.columns(2)
        with c1: t1 = st.selectbox("LUTADOR 1", options=sorted(df['ticker'].unique()), key="t1")
        with c2: t2 = st.selectbox("LUTADOR 2", options=sorted(df['ticker'].unique()), key="t2")
        if t1 and t2 and t1 != t2:
            d1 = df[df['ticker']==t1].iloc[0]; d2 = df[df['ticker']==t2].iloc[0]
            comp_data = {
                "INDICADOR": ["PREÇO", "P/L", "P/VP", "EV/EBIT", "ROIC", "MARGEM GRAHAM"],
                f"{t1}": [format_brl(d1['price']), f"{d1['pl']:.1f}", f"{d1['pvp']:.1f}", f"{d1['ev_ebit']:.1f}", f"{d1['roic']:.1%}", f"{d1['Margem']:.1%}"],
                f"{t2}": [format_brl(d2['price']), f"{d2['pl']:.1f}", f"{d2['pvp']:.1f}", f"{d2['ev_ebit']:.1f}", f"{d2['roic']:.1%}", f"{d2['Margem']:.1%}"]
            }
            st.dataframe(pd.DataFrame(comp_data).set_index("INDICADOR"), width='stretch')
            if st.button("⚔️ INICIAR COMBATE (IA)", key="btn_battle"):
                with st.spinner("A IA ESTÁ DECIDINDO O VENCEDOR..."):
                    res = get_battle_analysis(t1, str(d1.to_dict()), t2, str(d2.to_dict()))
                    st.markdown(f"<div class='glass-card'><div class='ai-header'><span class='ai-title'>VEREDITO DO ÁRBITRO</span></div>{res}</div>", unsafe_allow_html=True)
            
            st.markdown("---")
            ac1, ac2 = st.columns(2)
            with ac1:
                 if st.button(f"⬆️ ADICIONAR {t1}", key=f"add_arena_{t1}"): add_wallet_dialog(t1, d1['price'])
            with ac2:
                 if st.button(f"⬆️ ADICIONAR {t2}", key=f"add_arena_{t2}"): add_wallet_dialog(t2, d2['price'])
    else:
        st.warning("⚠️ Carregue a base de AÇÕES primeiro na aba principal.")

st.markdown("""<div class="disclaimer">⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO. OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS. ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. O INVESTIDOR É RESPONSÁVEL POR SUAS PRÓPRIAS DECISÕES.</div>""", unsafe_allow_html=True)
