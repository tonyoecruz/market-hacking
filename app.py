import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import google.generativeai as genai
import yfinance as yf
import plotly.graph_objects as go
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime

# ==============================================================================
# 🛠️ CONFIG DO APP
# ==============================================================================
URL_DO_ICONE = "https://wsrv.nl/?url=raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"
st.set_page_config(page_title="SCOPE3 ULTIMATE", page_icon=URL_DO_ICONE, layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# 🧠 INTELIGÊNCIA ARTIFICIAL (MOTOR V7.1)
# ==============================================================================
if "GEMINI_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_KEY"]
else:
    API_KEY = "" 

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
def get_ai_generic_analysis(prompt):
    if not IA_AVAILABLE: return f"⚠️ IA INDISPONÍVEL: {STARTUP_MSG}"
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e: return f"⚠️ ERRO DE GERAÇÃO: {str(e)}"

def get_graham_analysis(ticker, price, fair_value, lpa, vpa):
    margin = (fair_value/price) - 1 if price > 0 else 0
    prompt = f"Analise {ticker} SÓ pelo Método de Benjamin Graham. DADOS: Preço R${price:.2f} | Justo R${fair_value:.2f} | Margem {margin:.1%}. Resuma se está descontada. Max 3 linhas."
    return get_ai_generic_analysis(prompt)

def get_magic_analysis(ticker, ev_ebit, roic, score):
    prompt = f"Analise {ticker} SÓ pela Magic Formula. DADOS: EV/EBIT {ev_ebit} | ROIC {roic:.1%} | Score {score}. Resuma qualidade e preço. Max 3 linhas."
    return get_ai_generic_analysis(prompt)

def get_sniper_analysis(ticker, price, fair_value, details):
    prompt = f"Analise {ticker} ({details.get('Empresa','N/A')}) Setor {details.get('Setor','N/A')}. Se tiver risco de falência (RJ), ALERTA DE SNIPER. Senão, analise fundamentos. Max 5 linhas."
    return get_ai_generic_analysis(prompt)

def get_fii_analysis(ticker, price, pvp, dy, details):
    prompt = f"Analise o FII {ticker} ({details.get('Segmento','N/A')}). DADOS: Preço R${price} | P/VP {pvp} | DY {dy:.1%}. Bom para renda? Imóvel ou Papel? Max 4 linhas."
    return get_ai_generic_analysis(prompt)

def get_battle_analysis(t1, d1, t2, d2):
    prompt = f"""
    COMPARATIVO DE BATALHA:
    1. {t1}: {d1}
    2. {t2}: {d2}
    
    Qual vence nos fundamentos? Analise P/L, ROIC, Dívida e Crescimento se tiver. Seja direto. Quem ganha? Max 5 linhas.
    """
    return get_ai_generic_analysis(prompt)

# ==============================================================================
# 📡 CRAWLERS & DADOS
# ==============================================================================
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
        rename = {'Papel': 'ticker', 'Cotação': 'price', 'P/L': 'pl', 'P/VP': 'pvp', 'EV/EBIT': 'ev_ebit', 'ROIC': 'roic', 'Liq.2meses': 'liquidezmediadiaria'}
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

# CRAWLER DE GRÁFICO (YFINANCE BLINDADO)
def get_candle_chart(ticker):
    # Não cachear se der erro, pra tentar de novo
    try:
        # Tenta com .SA
        yf_ticker = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
        df = yf.download(yf_ticker, period="6mo", interval="1d", progress=False)
        
        # Se vazio, tenta SEM .SA (alguns BDRs ou casos raros)
        if df.empty or len(df) < 5:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            
        if not df.empty and len(df) > 5:
            fig = go.Figure(data=[go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                increasing_line_color= '#00ff41', decreasing_line_color= '#ff4444'
            )])
            fig.update_layout(
                xaxis_rangeslider_visible=False,
                plot_bgcolor='black', paper_bgcolor='black',
                font=dict(color='white'),
                margin=dict(l=10, r=10, t=10, b=10),
                height=350,
                title=f"GRÁFICO DIÁRIO: {ticker}"
            )
            return fig
        return None
    except Exception as e:
        return None

# ==============================================================================
# 🎨 ESTILOS CSS
# ==============================================================================
st.markdown(f"""
<head><link rel="apple-touch-icon" href="{URL_DO_ICONE}"></head>
<style>
    .stApp {{ background-color: #000; color: #fff; font-family: 'Consolas', monospace; }}
    h1, h2, h3 {{ color: #00ff41 !important; text-transform: uppercase; }}
    .stButton>button {{ border: 2px solid #00ff41; color: #00ff41; background: #000; font-weight: bold; height: 50px; width: 100%; transition: 0.3s; }}
    .stButton>button:hover {{ background: #00ff41; color: #000; box-shadow: 0 0 20px #00ff41; }}
    
    /* INPUTS E SELECTBOXES - CORREÇÃO DE COR */
    div[data-testid="stNumberInput"] input {{ color: #ffffff !important; background-color: #111 !important; border: 1px solid #00ff41 !important; }}
    div[data-testid="stSelectbox"] > div > div {{ color: #ffffff !important; background-color: #111 !important; border: 1px solid #00ff41 !important; }}
    
    /* ABAS NO TOPO (TABS) */
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        height: 50px; white-space: pre-wrap; background-color: #111; border-radius: 4px 4px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; color: #fff; border: 1px solid #333;
    }}
    .stTabs [aria-selected="true"] {{ background-color: #00ff41 !important; color: #000 !important; font-weight: bold; }}
    
    /* GARANTE QUE O TEXTO DIGITADO SEJA BRANCO */
    .stSelectbox div[data-baseweb="select"] > div {{ color: #ffffff !important; }}
    .stSelectbox div[data-baseweb="select"] span {{ color: #ffffff !important; }}
    .stSelectbox label, .stNumberInput label {{ color: #00ff41 !important; font-weight: bold; font-size: 14px; }}
    
    .hacker-card {{ background-color: #ffffff; border: 1px solid #ccc; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 10px; border-radius: 4px; }}
    .card-ticker {{ font-size: 20px; font-weight: bold; color: #000; }}
    .card-price {{ float: right; font-size: 20px; color: #009926; font-weight: bold; }}
    .metric-row {{ display: flex; justify-content: space-between; margin-top: 10px; border-top: 1px dashed #ccc; padding-top: 5px; }}
    .metric-label {{ font-size: 12px; color: #555; font-weight: bold; }}
    .metric-value {{ font-size: 16px; font-weight: bold; color: #000; }}
    .buy-section {{ margin-top: 10px; background: #e6ffe6; padding: 5px; text-align: center; border: 1px solid #00cc33; font-size: 14px; color: #006600; font-weight: bold; }}

    .ai-box {{ border: 1px solid #9933ff; background-color: #f3e5ff; padding: 15px; border-radius: 6px; margin-top: 10px; border-left: 4px solid #9933ff; color: #000 !important; font-size: 14px; line-height: 1.5; }}
    .ai-header {{ display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #d1b3ff; padding-bottom: 5px; margin-bottom: 10px; }}
    .ai-title {{ color: #6600cc; font-weight: bold; font-size: 16px; text-transform: uppercase; }}

    .tag-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; }}
    .info-tag {{ background: #ffffff; border: 1px solid #ccc; padding: 8px; border-radius: 4px; display: flex; flex-direction: column; justify-content: center; }}
    .info-label {{ font-size: 11px; text-transform: uppercase; color: #009926; margin-bottom: 2px; font-weight: bold; }}
    .info-val {{ color: #000; font-weight: bold; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    
    .status-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
    .status-box {{ padding: 10px; border-radius: 4px; text-align: center; border: 1px solid #ccc; background: #fff; }}
    .status-title {{ font-size: 12px; font-weight: bold; margin-bottom: 5px; color: #000; }}
    .status-result {{ font-size: 15px; font-weight: bold; text-transform: uppercase; }}

    .risk-alert {{ background-color: #ffe6e6; color: #cc0000 !important; border: 2px solid #ff0000; padding: 20px; border-radius: 6px; margin-top: 15px; animation: pulse 2s infinite; }}
    .risk-title {{ color: #cc0000; font-weight: 900; font-size: 20px; margin-bottom: 10px; text-transform: uppercase; display: flex; align-items: center; gap: 10px; }}

    .modal-header {{ font-size: 22px; color: #00ff41; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; }}
    .modal-math {{ background: #f0f0f0; padding: 15px; border-left: 3px solid #009926; font-family: monospace; font-size: 16px; color: #000; margin-bottom: 15px; }}
    .highlight-val {{ color: #009926; font-weight: bold; font-size: 18px; }}
    .modal-text {{ font-size: 14px; color: #000; line-height: 1.4; margin-top: 10px; border-top: 1px solid #ccc; padding-top: 10px; }}
    .detail-list {{ font-size: 13px; color: #000; margin-top: 10px; }}
    .detail-item {{ margin-bottom: 8px; padding-left: 10px; border-left: 2px solid #009926; }}
    .detail-key {{ color: #009926; font-weight: bold; font-size: 12px; text-transform: uppercase; }}
    .disclaimer {{ text-align: center; color: #aaa; font-size: 12px; margin-top: 50px; padding-top: 20px; border-top: 1px solid #555; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==============================================================================
# 📂 MODAIS (AÇÕES)
# ==============================================================================
@st.dialog("📂 DOSSIÊ GRAHAM", width="large")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']; margem = row['Margem']
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div>""", unsafe_allow_html=True)
    with c2:
        status_color = "#009926" if margem > 0 else "#cc0000"
        status_txt = "DESCONTADA" if margem > 0 else "ACIMA DO VI"
        st.markdown(f"""<div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px; background:#fff"><div style="font-size:12px; color:#000">STATUS</div><div style="font-size:20px; font-weight:bold; color:{status_color}">{status_txt}</div><div style="font-size:14px; margin-top:5px; color:#000">Margem: {margem:.1%}</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="modal-text"><b>🔍 ENTENDENDO A LÓGICA:</b> Benjamin Graham...</div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: ANALISANDO..."):
        ai_text = get_graham_analysis(ticker, row['price'], vi, lpa, vpa)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ MAGIC FORMULA", width="large")
def show_magic_details(ticker, row):
    rev = int(row.get('R_EV', 0)); rroic = int(row.get('R_ROIC', 0)); sc = int(row.get('Score', 0))
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-val">{sc} PONTOS</span></div>""", unsafe_allow_html=True)
    with c2:
        is_good = (row['roic'] > 0.15) and (row['ev_ebit'] > 0)
        status_color = "#009926" if is_good else "#ffaa00"
        status_txt = "ALTA QUALIDADE" if is_good else "EM OBSERVAÇÃO"
        st.markdown(f"""<div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px; background:#fff"><div style="font-size:12px; color:#000">QUALIDADE</div><div style="font-size:18px; font-weight:bold; color:{status_color}">{status_txt}</div><div style="font-size:12px; margin-top:5px; color:#000">ROIC: {row['roic']:.1%}</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="modal-text"><b>🔍 ENTENDENDO A LÓGICA:</b> Joel Greenblatt...</div>""", unsafe_allow_html=True)
    with st.spinner("🤖 IA: ANALISANDO..."):
        ai_text = get_magic_analysis(ticker, row['ev_ebit'], row['roic'], sc)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)

@st.dialog("🧠 DECODE INTELLIGENCE", width="large")
def show_ai_decode(ticker, row, details):
    st.markdown(f"### 🎯 ALVO: {ticker}")
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">EMPRESA</span><span class="info-val">{details.get('Empresa', 'N/A')}</span></div><div class="info-tag"><span class="info-label">SETOR</span><span class="info-val">{details.get('Setor', 'N/A')}</span></div><div class="info-tag"><span class="info-label">SEGMENTO</span><span class="info-val">{details.get('Segmento', 'N/A')}</span></div></div>""", unsafe_allow_html=True)
    
    graham_ok = row['Margem'] > 0; magic_ok = (row['roic'] > 0.10) and (row['ev_ebit'] > 0)
    st.markdown(f"""<div class="status-grid"><div class="status-box" style="border-color: {'#009926' if graham_ok else '#cc0000'};"><div class="status-title" style="color:{'#009926' if graham_ok else '#cc0000'}">MÉTODO GRAHAM</div><div class="status-result" style="color:{'#009926' if graham_ok else '#cc0000'}">{'✅ POSITIVO' if graham_ok else '❌ NEGATIVO'}</div><div style="font-size:10px; color:#000; margin-top:2px">{'MARGEM: ' + f"{row['Margem']:.1%}" if graham_ok else 'SEM MARGEM'}</div></div><div class="status-box" style="border-color: {'#009926' if magic_ok else '#ffaa00'};"><div class="status-title" style="color:{'#009926' if magic_ok else '#ffaa00'}">MAGIC FORMULA</div><div class="status-result" style="color:{'#009926' if magic_ok else '#ffaa00'}">{'✅ APROVADA' if magic_ok else '⚠️ ATENÇÃO'}</div><div style="font-size:10px; color:#000; margin-top:2px">{'ROIC: ' + f"{row['roic']:.1%}" if magic_ok else 'ROIC BAIXO'}</div></div></div><hr style="border-color: #333; margin: 15px 0;">""", unsafe_allow_html=True)
    
    with st.spinner("🛰️ SATÉLITE: PROCESSANDO..."):
        analise = get_sniper_analysis(ticker, row['price'], row['ValorJusto'], details)
    if "ALERTA" in analise.upper() or "RISCO" in analise.upper(): st.markdown(f"<div class='risk-alert'><div class='risk-title'>💀 ALERTA DE RISCO DETECTADO</div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    else: st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-icon'>🧠</span><span class='ai-title'>ANÁLISE TÁTICA (GEMINI)</span></div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

# ==============================================================================
# 📂 MODAIS (FIIs)
# ==============================================================================
@st.dialog("🏢 FII DECODE", width="large")
def show_fii_decode(ticker, row, details):
    st.markdown(f"### 🏢 ALVO: {ticker}")
    st.markdown(f"""<div class="tag-grid"><div class="info-tag"><span class="info-label">SEGMENTO</span><span class="info-val">{row['segmento']}</span></div><div class="info-tag"><span class="info-label">Cotação</span><span class="info-val">{format_brl(row['price'])}</span></div><div class="info-tag"><span class="info-label">DY (12M)</span><span class="info-val">{row['dy']:.2%}</span></div></div>""", unsafe_allow_html=True)
    
    pvp_bom = 0.8 <= row['pvp'] <= 1.10
    dy_bom = row['dy'] > 0.08
    st.markdown(f"""<div class="status-grid"><div class="status-box" style="border-color: {'#009926' if pvp_bom else '#ffaa00'};"><div class="status-title" style="color:{'#009926' if pvp_bom else '#ffaa00'}">P/VP (PREÇO JUSTO)</div><div class="status-result" style="color:{'#009926' if pvp_bom else '#ffaa00'}">{'✅ NO PREÇO' if pvp_bom else '⚠️ DESCOLADO'}</div><div style="font-size:10px; color:#000; margin-top:2px">{row['pvp']:.2f}</div></div><div class="status-box" style="border-color: {'#009926' if dy_bom else '#ffaa00'};"><div class="status-title" style="color:{'#009926' if dy_bom else '#ffaa00'}">DIVIDENDOS</div><div class="status-result" style="color:{'#009926' if dy_bom else '#ffaa00'}">{'✅ ATRATIVO' if dy_bom else '⚠️ BAIXO'}</div><div style="font-size:10px; color:#000; margin-top:2px">{row['dy']:.1%} a.a.</div></div></div>""", unsafe_allow_html=True)
    
    with st.spinner("🤖 IA: ANALISANDO FII..."):
        ai_text = get_fii_analysis(ticker, row['price'], row['pvp'], row['dy'], details)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>ANÁLISE DE RENDA (IA)</span></div>{ai_text}</div>", unsafe_allow_html=True)

# ==============================================================================
# 📺 UI PRINCIPAL (NAVEGAÇÃO POR ABAS SUPERIORES)
# ==============================================================================
c_logo, c_title = st.columns([1, 8])
with c_logo: st.image(URL_DO_ICONE, width=70)
with c_title: st.markdown(f"<h2 style='margin-top:10px'>SCOPE3 <span style='font-size:14px;color:#9933ff'>| ULTIMATE v13.0</span></h2>", unsafe_allow_html=True)
st.divider()

# ABAS FIXAS NO TOPO (SUBSTITUINDO SIDEBAR)
tab_acoes, tab_fiis, tab_arena = st.tabs(["AÇÕES (GRAHAM/MAGIC)", "FIIs (RENDA)", "ARENA (BATALHA)"])

# ------------------------------------------------------------------------------
# PÁGINA 1: AÇÕES
# ------------------------------------------------------------------------------
with tab_acoes:
    if 'market_data' not in st.session_state:
        if st.button("⚡ INICIAR VARREDURA AÇÕES", key="btn_scan_acoes"):
            with st.spinner("Baixando Dados Ações..."):
                df = get_data_acoes()
                df = df[(df['liquidezmediadiaria']>0) & (df['price']>0)].copy()
                df['graham_term'] = (22.5 * df['lpa'] * df['vpa']).apply(lambda x: x if x>0 else 0)
                df['ValorJusto'] = np.sqrt(df['graham_term'])
                df['Margem'] = (df['ValorJusto']/df['price']) - 1
                df_m = df[(df['ev_ebit']>0) & (df['roic']>0)].copy()
                df_m['R_EV'] = df_m['ev_ebit'].rank(ascending=True); df_m['R_ROIC'] = df_m['roic'].rank(ascending=False)
                df_m['Score'] = df_m['R_EV'] + df_m['R_ROIC']; df_m['MagicRank'] = df_m['Score'].rank(ascending=True)
                st.session_state['market_data'] = df.merge(df_m[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
                st.rerun()
    else:
        df = st.session_state['market_data']
        st.success(f"BASE AÇÕES: {len(df)} ATIVOS.")
        
        # SNIPER + GRÁFICO
        st.markdown("### 🎯 MIRA LASER (IA)")
        c_sel, c_btn, _ = st.columns([2, 1, 6])
        with c_sel: target = st.selectbox("CÓDIGO:", options=sorted(df['ticker'].unique()), index=None, placeholder="Ex: VALE3", key="target_acoes")
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_decode = st.button("🧠 DECODE", key="btn_decode_acoes")
        
        if target:
            row_t = df[df['ticker']==target].iloc[0]
            with st.spinner(f"Carregando Gráfico {target}..."):
                fig = get_candle_chart(target)
                if fig: st.plotly_chart(fig, use_container_width=True)
                else: st.warning(f"Gráfico não disponível para {target}")
            if btn_decode:
                with st.spinner("Analisando..."): details = get_stock_details(target)
                show_ai_decode(target, row_t, details)

        st.markdown("---")
        ic1, ic2 = st.columns(2)
        with ic1: min_liq = st.number_input("LIQUIDEZ MÍNIMA", value=200000, step=50000, key="min_liq_acoes")
        with ic2: invest = st.number_input("SIMULAR APORTE", value=0.0, step=100.0, key="invest_acoes")
        
        df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
        t1, t2 = st.tabs(["💎 GRAHAM", "✨ MAGIC FORMULA"])
        
        def card(t, p, l1, v1, l2, v2, r, inv=0):
            buy = f"<div class='buy-section'>APORTE: <span class='buy-value'>{int((inv/10)//p)} ações</span></div>" if inv>0 and p>0 else ""
            return f"""<div class="hacker-card"><div><span class="card-ticker">#{r} {t}</span><span class="card-price">{format_brl(p)}</span></div><div class="metric-row"><div><div class="metric-label">{l1}</div><div class="metric-value">{v1}</div></div><div style="text-align:right"><div class="metric-label">{l2}</div><div class="metric-value">{v2}</div></div></div>{buy}</div>"""
        
        with t1:
            df_g = df_fin[(df_fin['lpa']>0)&(df_fin['vpa']>0)].sort_values('Margem', ascending=False).head(10)
            c1, c2 = st.columns(2)
            for i, r in df_g.reset_index().iterrows():
                with (c1 if i%2==0 else c2):
                    st.markdown(card(r['ticker'], r['price'], "VALOR JUSTO", format_brl(r['ValorJusto']), "POTENCIAL", f"{r['Margem']:.1%}", i+1, invest), unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"g_{r['ticker']}"): show_graham_details(r['ticker'], r)
        with t2:
            df_m = df_fin.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True).head(10)
            c1, c2 = st.columns(2)
            for i, r in df_m.reset_index().iterrows():
                with (c1 if i%2==0 else c2):
                    st.markdown(card(r['ticker'], r['price'], "EV/EBIT", f"{r['ev_ebit']:.2f}", "ROIC", f"{r['roic']:.1%}", i+1, invest), unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"m_{r['ticker']}"): show_magic_details(r['ticker'], r)

# ------------------------------------------------------------------------------
# PÁGINA 2: FIIs
# ------------------------------------------------------------------------------
with tab_fiis:
    st.markdown("### 🏢 FORTALEZA DE RENDA (FIIs)")
    if 'fiis_data' not in st.session_state:
        if st.button("⚡ INICIAR VARREDURA FIIs", key="btn_scan_fiis"):
            with st.spinner("Baixando Dados FIIs..."):
                st.session_state['fiis_data'] = get_data_fiis()
                st.rerun()
    else:
        df_fii = st.session_state['fiis_data']
        st.success(f"BASE FIIs: {len(df_fii)} FUNDOS.")
        
        # MIRA LASER FII
        c_sel, c_btn, _ = st.columns([2, 1, 6])
        with c_sel: target_fii = st.selectbox("CÓDIGO FII:", options=sorted(df_fii['ticker'].unique()), index=None, placeholder="Ex: MXRF11", key="target_fii")
        
        if target_fii:
            row_fii = df_fii[df_fii['ticker']==target_fii].iloc[0]
            with st.spinner(f"Carregando Gráfico {target_fii}..."):
                fig = get_candle_chart(target_fii)
                if fig: st.plotly_chart(fig, use_container_width=True)
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
            st.markdown(f"""<div class="hacker-card"><div><span class="card-ticker">{row['ticker']}</span><span class="card-price">{format_brl(row['price'])}</span></div><div class="metric-row"><div><div class="metric-label">DY (12M)</div><div class="metric-value">{row['dy']:.1%}</div></div><div style="text-align:center"><div class="metric-label">P/VP</div><div class="metric-value">{row['pvp']:.2f}</div></div><div style="text-align:right"><div class="metric-label">SEGMENTO</div><div class="metric-value" style="font-size:12px">{row['segmento']}</div></div></div></div>""", unsafe_allow_html=True)
            if st.button(f"🏢 ANALISAR {row['ticker']}", key=f"fii_list_{row['ticker']}"):
                show_fii_decode(row['ticker'], row, {'Segmento': row['segmento']})

# ------------------------------------------------------------------------------
# PÁGINA 3: ARENA
# ------------------------------------------------------------------------------
with tab_arena:
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
            st.table(pd.DataFrame(comp_data).set_index("INDICADOR"))
            if st.button("⚔️ INICIAR COMBATE (IA)", key="btn_battle"):
                with st.spinner("A IA ESTÁ DECIDINDO O VENCEDOR..."):
                    res = get_battle_analysis(t1, str(d1.to_dict()), t2, str(d2.to_dict()))
                    st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>VEREDITO DO ÁRBITRO</span></div>{res}</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Carregue a base de AÇÕES primeiro na aba principal.")

st.markdown("""<div class="disclaimer">⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO. OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS. ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. O INVESTIDOR É RESPONSÁVEL POR SUAS PRÓPRIAS DECISÕES.</div>""", unsafe_allow_html=True)
