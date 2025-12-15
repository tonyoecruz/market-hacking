import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==============================================================================
# 🔑 CONFIGURAÇÃO DA INTELIGÊNCIA ARTIFICIAL (NOVA CHAVE)
# ==============================================================================
# Chave atualizada em 15/12
API_KEY = "AIzaSyB4Xu_ebwghWcUb4QnVFRI4qjYNjWBrk1E"

# Configuração para IGNORAR filtros de segurança (Permite falar de Risco/Falência)
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

try:
    genai.configure(api_key=API_KEY)
    # Modelo Flash: Rápido e eficiente para esse tipo de análise
    model = genai.GenerativeModel('gemini-1.5-flash') 
    IA_AVAILABLE = True
except Exception as e:
    IA_AVAILABLE = False
    STARTUP_ERROR = str(e)

# ==============================================================================
# 🛠️ CONFIG DO APP E ÍCONE
# ==============================================================================
URL_DO_ICONE = "https://wsrv.nl/?url=raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"

st.set_page_config(page_title="SCOPE3 ULTIMATE", page_icon=URL_DO_ICONE, layout="wide")

# ==============================================================================
# 🎨 ESTILOS CSS (FONTE BRANCA E CONTRASTE)
# ==============================================================================
st.markdown(f"""
<head><link rel="apple-touch-icon" href="{URL_DO_ICONE}"></head>
<style>
    /* BASE DARK */
    .stApp {{ background-color: #000; color: #e0e0e0; font-family: 'Consolas', monospace; }}
    h1, h2, h3 {{ color: #00ff41 !important; text-transform: uppercase; }}
    
    /* BOTÕES */
    .stButton>button {{ border: 2px solid #00ff41; color: #00ff41; background: #000; font-weight: bold; height: 50px; width: 100%; text-transform: uppercase; transition: 0.3s; }}
    .stButton>button:hover {{ background: #00ff41; color: #000; box-shadow: 0 0 20px #00ff41; }}
    
    /* INPUTS */
    div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] > div > div {{ color: #fff !important; background-color: #111 !important; border: 1px solid #00ff41 !important; }}
    
    /* CARDS TOP 10 */
    .hacker-card {{ background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 10px; border-radius: 4px; }}
    .card-ticker {{ font-size: 20px; font-weight: bold; color: #fff; }}
    .card-price {{ float: right; font-size: 20px; color: #00ff41; }}
    .metric-row {{ display: flex; justify-content: space-between; margin-top: 10px; border-top: 1px dashed #333; padding-top: 5px; }}
    .metric-label {{ font-size: 12px; color: #888; }}
    .metric-value {{ font-size: 16px; font-weight: bold; color: #fff; }}
    .buy-section {{ margin-top: 10px; background: #051a05; padding: 5px; text-align: center; border: 1px solid #00ff41; font-size: 14px; color: #00ff41; }}

    /* CAIXAS DA IA (BRANCO FORÇADO) */
    .ai-box {{ 
        border: 1px solid #9933ff; 
        background-color: #1a0526; 
        padding: 20px; 
        border-radius: 4px; 
        margin-top: 15px; 
        border-left: 5px solid #9933ff;
        color: #ffffff !important;
    }}
    .ai-title {{ color: #c299ff; font-weight: bold; font-size: 18px; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }}
    
    /* ALERTA DE RISCO (BRANCO FORÇADO) */
    .risk-alert {{ 
        background-color: #330000; 
        color: #ffffff !important; 
        border: 2px solid #ff0000; 
        padding: 20px; 
        border-radius: 4px; 
        margin-top: 15px; 
        animation: pulse 2s infinite; 
    }}
    .risk-title {{ color: #ff0000; font-weight: 900; font-size: 20px; margin-bottom: 10px; }}
    
    /* CAIXA DE ERRO */
    .error-box {{ border: 1px solid red; background: #220000; color: #ffcccc; padding: 15px; font-family: monospace; }}

    /* MODAIS MATEMÁTICOS */
    .modal-header {{ font-size: 22px; color: #00ff41; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; }}
    .modal-math {{ background: #111; padding: 15px; border-left: 3px solid #00ff41; font-family: monospace; font-size: 16px; color: #ccc; margin-bottom: 15px; }}
    .highlight-val {{ color: #00ff41; font-weight: bold; font-size: 18px; }}
    .modal-text {{ font-size: 14px; color: #aaa; line-height: 1.5; }}

    /* DISCLAIMER (RODAPÉ) */
    .disclaimer {{ text-align: center; color: #555; font-size: 12px; margin-top: 50px; padding-top: 20px; border-top: 1px solid #222; }}

    @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }} 70% {{ box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }} }}
    #MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# --- HELPER BRL ---
def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==============================================================================
# 📡 CRAWLERS DE DADOS
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
def get_data_direct():
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

# ==============================================================================
# 🧠 INTELIGÊNCIA ARTIFICIAL (SAFETY OFF)
# ==============================================================================
def get_ai_analysis(ticker, price, fair_value, details):
    if not IA_AVAILABLE:
        return f"⚠️ ERRO CRÍTICO: A biblioteca Google Generative AI não carregou.\nErro: {STARTUP_ERROR}\n\nSOLUÇÃO: Verifique o requirements.txt."
    
    prompt = f"""
    Analise a ação {ticker} ({details.get('Empresa', 'N/A')}).
    Dados: Preço R$ {price}, Justo R$ {fair_value}, Setor {details.get('Setor', 'N/A')}.
    
    SE ESTIVER EM RECUPERAÇÃO JUDICIAL ou FALÊNCIA (ex: Americanas, Oi, Light):
    Comece com "ALERTA DE SNIPER 💀" e explique o risco grave.
    
    SE FOR EMPRESA NORMAL:
    Analise brevemente se está barata segundo Graham.
    
    Seja curto (max 5 linhas). Direto ao ponto.
    """
    try:
        # Envia para a IA com a nova chave e SEM filtros
        response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        
        if response.prompt_feedback.block_reason:
            return f"⚠️ BLOQUEIO DO GOOGLE: A resposta foi bloqueada por segurança.\nMotivo: {response.prompt_feedback.block_reason}"
            
        return response.text
    except Exception as e:
        return f"⚠️ ERRO NA COMUNICAÇÃO:\n{str(e)}\n\nVERIFIQUE: Se a API Key '{API_KEY[:10]}...' está ativa no Google Cloud."

# ==============================================================================
# 📂 MODAIS DE DECODE
# ==============================================================================
@st.dialog("📂 DOSSIÊ GRAHAM")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div><div style="text-align:center;color:#fff;">PREÇO: <b>{format_brl(row['price'])}</b> | POTENCIAL: <b style="color:#00ff41">{row['Margem']:.1%}</b></div>""", unsafe_allow_html=True)
    with c2: 
        st.markdown("""
        <div class="modal-text">
            <b>VI (Valor Intrínseco):</b> O "Preço Justo" teórico.
            <br><b>Constante 22.5:</b> O teto de Graham (P/L x P/VP máximos).
            <br><b>Margem:</b> Desconto do Preço de Tela vs Valor Justo.
        </div>
        """, unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ MAGIC FORMULA")
def show_magic_details(ticker, row):
    rev = int(row.get('R_EV', 0)); rroic = int(row.get('R_ROIC', 0)); sc = int(row.get('Score', 0))
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-val">{sc}</span></div>""", unsafe_allow_html=True)
    with c2: 
        st.markdown(f"""
        <div class="modal-text">
            <b>EV/EBIT:</b> Rank de Preço (#{rev}ª mais barata).
            <br><b>ROIC:</b> Rank de Eficiência (#{rroic}ª mais eficiente).
            <br><b>Lógica:</b> Quanto <u>MENOR</u> a pontuação, MELHOR.
        </div>
        """, unsafe_allow_html=True)

@st.dialog("🧠 DECODE INTELLIGENCE", width="large")
def show_ai_decode(ticker, row, details):
    st.markdown(f"### 🎯 ALVO: {ticker}")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"**Empresa:** {details.get('Empresa', 'N/A')}")
    with c2: st.markdown(f"**Setor:** {details.get('Setor', 'N/A')}")
    st.markdown("---")
    
    with st.spinner("🛰️ SATÉLITE: PROCESSANDO..."):
        analise = get_ai_analysis(ticker, row['price'], row['ValorJusto'], details)
    
    if "ERRO" in analise or "BLOQUEIO" in analise:
        st.markdown(f"<div class='error-box'>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    elif "ALERTA" in analise.upper() or "RISCO" in analise.upper() or "CAVEIRA" in analise.upper():
        st.markdown(f"<div class='risk-alert'><div class='risk-title'>⚠️ ALERTA DE RISCO</div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-box'><div class='ai-title'>🧠 ANÁLISE TÁTICA</div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

# ==============================================================================
# 📺 INTERFACE PRINCIPAL
# ==============================================================================
c_logo, c_title = st.columns([1, 8])
with c_logo: st.image(URL_DO_ICONE, width=70)
with c_title: 
    st.markdown(f"<h2 style='margin-top:10px'>SCOPE3 <span style='font-size:14px;color:#9933ff'>| AI v3.6</span></h2>", unsafe_allow_html=True)

st.divider()

if 'market_data' not in st.session_state:
    if st.button("⚡ INICIAR VARREDURA COMPLETA"):
        with st.spinner("Baixando e Processando Dados da B3..."):
            df = get_data_direct()
            df = df[(df['liquidezmediadiaria']>0) & (df['price']>0)].copy()
            
            # Graham
            df['graham_term'] = (22.5 * df['lpa'] * df['vpa']).apply(lambda x: x if x>0 else 0)
            df['ValorJusto'] = np.sqrt(df['graham_term'])
            df['Margem'] = (df['ValorJusto']/df['price']) - 1
            
            # Magic Formula
            df_m = df[(df['ev_ebit']>0) & (df['roic']>0)].copy()
            df_m['R_EV'] = df_m['ev_ebit'].rank(ascending=True)
            df_m['R_ROIC'] = df_m['roic'].rank(ascending=False)
            df_m['Score'] = df_m['R_EV'] + df_m['R_ROIC']
            df_m['MagicRank'] = df_m['Score'].rank(ascending=True)
            
            df_final = df.merge(df_m[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
            st.session_state['market_data'] = df_final
            st.rerun()
else:
    df = st.session_state['market_data']
    st.success(f"BASE OPERACIONAL: {len(df)} ATIVOS.")
    
    # --- ÁREA SNIPER (COMPACTA) ---
    st.markdown("### 🎯 MIRA LASER (IA)")
    c_sel, c_btn, c_vazio = st.columns([2, 1, 6])
    with c_sel: 
        target = st.selectbox("ALVO:", options=sorted(df['ticker'].unique()))
    with c_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧠 DECODE IA") and target:
            row = df[df['ticker']==target].iloc[0]
            with st.spinner("BUSCANDO DETALHES..."): details = get_stock_details(target)
            show_ai_decode(target, row, details)

    st.markdown("---")

    # --- ÁREA SCANNER ---
    st.markdown("### 📊 SCANNER DE OPORTUNIDADES")
    ic1, ic2, ic3 = st.columns([1, 2, 2])
    with ic2: min_liq = st.number_input("Liquidez Mínima", value=200000, step=50000)
    with ic3: invest = st.number_input("Simular Investimento (R$)", value=0.0, step=100.0)
    
    df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
    t1, t2 = st.tabs(["💎 GRAHAM (PREÇO JUSTO)", "✨ MAGIC FORMULA (QUALIDADE)"])
    
    def card(t, p, l1, v1, l2, v2, r, inv=0):
        buy = ""
        if inv > 0 and p > 0:
            q = int((inv/10)//p); c = q*p
            buy = f"<div class='buy-section'>COMPRAR: <span class='buy-value'>{q} ações (~{format_brl(c)})</span></div>"
        return f"""<div class="hacker-card"><div><span class="card-ticker">#{r} {t}</span><span class="card-price">{format_brl(p)}</span></div><div class="metric-row"><div><div class="metric-label">{l1}</div><div class="metric-value">{v1}</div></div><div style="text-align:right"><div class="metric-label">{l2}</div><div class="metric-value">{v2}</div></div></div>{buy}</div>"""

    # LISTA GRAHAM
    with t1:
        df_g = df_fin[(df_fin['lpa']>0)&(df_fin['vpa']>0)].sort_values('Margem', ascending=False).head(10)
        c1, c2 = st.columns(2)
        for i, r in df_g.reset_index().iterrows():
            with (c1 if i%2==0 else c2):
                st.markdown(card(r['ticker'], r['price'], "VALOR JUSTO", format_brl(r['ValorJusto']), "POTENCIAL", f"{r['Margem']:.1%}", i+1, invest), unsafe_allow_html=True)
                if st.button(f"📂 DECODE MATEMÁTICO #{i+1}", key=f"g_{r['ticker']}"): show_graham_details(r['ticker'], r)

    # LISTA MAGIC
    with t2:
        df_m = df_fin.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True).head(10)
        c1, c2 = st.columns(2)
        for i, r in df_m.reset_index().iterrows():
            with (c1 if i%2==0 else c2):
                st.markdown(card(r['ticker'], r['price'], "EV/EBIT", f"{r['ev_ebit']:.2f}", "ROIC", f"{r['roic']:.1%}", i+1, invest), unsafe_allow_html=True)
                if st.button(f"📂 DECODE MATEMÁTICO #{i+1}", key=f"m_{r['ticker']}"): show_magic_details(r['ticker'], r)

    # --- DOWNLOAD ---
    st.markdown("---")
    df_exp = df_fin[['ticker', 'price', 'ValorJusto', 'Margem', 'ev_ebit', 'roic', 'MagicRank', 'liquidezmediadiaria']].copy()
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_exp.to_excel(writer, index=False)
    st.download_button("📥 DOWNLOAD RELATÓRIO EXCEL", data=buffer.getvalue(), file_name=f"SCOPE3_SCAN_{datetime.now().strftime('%Y%m%d')}.xlsx")

# --- DISCLAIMER (AVISO LEGAL) ---
st.markdown("""
<div class="disclaimer">
    ⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO.<br>
    OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS.<br>
    ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. USE COM RESPONSABILIDADE.
</div>
""", unsafe_allow_html=True)
