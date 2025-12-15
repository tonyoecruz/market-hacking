import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime

# ==============================================================================
# 🛠️ CONFIG DO APP
# ==============================================================================
URL_DO_ICONE = "https://wsrv.nl/?url=raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"
st.set_page_config(page_title="SCOPE3 ULTIMATE", page_icon=URL_DO_ICONE, layout="wide")

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

# --- FUNÇÕES DE ANÁLISE ESPECÍFICAS (COMPLIANCE MODE) ---
def get_ai_generic_analysis(prompt):
    if not IA_AVAILABLE: return f"⚠️ IA INDISPONÍVEL: {STARTUP_MSG}"
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e: return f"⚠️ ERRO DE GERAÇÃO: {str(e)}"

def get_graham_analysis(ticker, price, fair_value, lpa, vpa):
    margin = (fair_value/price) - 1 if price > 0 else 0
    prompt = f"""
    Analise {ticker} SÓ pelo Método de Benjamin Graham para fins educacionais.
    DADOS: Preço Tela: R${price:.2f} | Preço Justo Teórico (Graham): R${fair_value:.2f} | Margem Teórica: {margin:.1%} | LPA: {lpa} | VPA: {vpa}.
    
    Explique tecnicamente se a ação está descontada (abaixo do valor intrínseco) ou com prêmio (acima).
    NÃO dê recomendação de compra ou venda. Use termos como "potencial de valor", "desconto teórico", "margem de segurança".
    Máximo 3 linhas. Direto e Educacional.
    """
    return get_ai_generic_analysis(prompt)

def get_magic_analysis(ticker, ev_ebit, roic, score):
    prompt = f"""
    Analise {ticker} SÓ pela Magic Formula (Joel Greenblatt) para fins educacionais.
    DADOS: EV/EBIT: {ev_ebit} | ROIC: {roic:.1%} | Score Geral: {score}.
    
    Explique se os indicadores sugerem uma empresa "Boa (ROIC alto) e Barata (EV/EBIT baixo)".
    NÃO dê recomendação de investimento. Fale sobre "qualidade dos fundamentos" e "posição no ranking".
    Máximo 3 linhas. Direto e Educacional.
    """
    return get_ai_generic_analysis(prompt)

def get_sniper_analysis(ticker, price, fair_value, details):
    prompt = f"""
    Analise a ação {ticker} ({details.get('Empresa', 'N/A')}).
    Dados: Preço R$ {price}, Justo R$ {fair_value}, Setor {details.get('Setor', 'N/A')}.
    
    1. SE TIVER RISCO DE FALÊNCIA (Recuperação Judicial): Comece com "ALERTA DE SNIPER 💀" e explique o risco nos demonstrativos.
    2. SE NÃO: Analise os fundamentos de forma neutra e técnica.
    
    IMPORTANTE: Nunca use "Compre" ou "Venda". Use "Atrativa", "Descontada", "Arriscada", "Cara".
    Foco total em educação financeira.
    Máximo 5 linhas.
    """
    return get_ai_generic_analysis(prompt)

# ==============================================================================
# 🎨 ESTILOS CSS (FONTE MAIS LEGÍVEL)
# ==============================================================================
st.markdown(f"""
<head><link rel="apple-touch-icon" href="{URL_DO_ICONE}"></head>
<style>
    /* BASE */
    .stApp {{ background-color: #000; color: #e0e0e0; font-family: 'Consolas', monospace; }}
    h1, h2, h3 {{ color: #00ff41 !important; text-transform: uppercase; }}
    
    /* UI ELEMENTS */
    .stButton>button {{ border: 2px solid #00ff41; color: #00ff41; background: #000; font-weight: bold; height: 50px; width: 100%; transition: 0.3s; text-transform: uppercase; }}
    .stButton>button:hover {{ background: #00ff41; color: #000; box-shadow: 0 0 20px #00ff41; }}
    div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] > div > div {{ color: #fff !important; background-color: #111 !important; border: 1px solid #00ff41 !important; }}
    
    /* CARDS */
    .hacker-card {{ background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 10px; border-radius: 4px; }}
    .card-ticker {{ font-size: 20px; font-weight: bold; color: #fff; }}
    .card-price {{ float: right; font-size: 20px; color: #00ff41; }}
    .metric-row {{ display: flex; justify-content: space-between; margin-top: 10px; border-top: 1px dashed #333; padding-top: 5px; }}
    .metric-label {{ font-size: 12px; color: #bbb; }} /* COR AJUSTADA PARA MAIS CLARO */
    .metric-value {{ font-size: 16px; font-weight: bold; color: #fff; }}
    .buy-section {{ margin-top: 10px; background: #051a05; padding: 5px; text-align: center; border: 1px solid #00ff41; font-size: 14px; color: #00ff41; }}

    /* IA BOX */
    .ai-box {{ border: 1px solid #9933ff; background-color: #0d0214; padding: 15px; border-radius: 6px; margin-top: 10px; border-left: 4px solid #9933ff; color: #e0e0e0 !important; font-size: 14px; line-height: 1.5; }}
    .ai-header {{ display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #3d1466; padding-bottom: 5px; margin-bottom: 10px; }}
    .ai-title {{ color: #c299ff; font-weight: bold; font-size: 16px; text-transform: uppercase; }}

    /* INFO TAGS & STATUS BOXES */
    .tag-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; }}
    .info-tag {{ background: #111; border: 1px solid #333; padding: 8px; border-radius: 4px; display: flex; flex-direction: column; justify-content: center; }}
    .info-label {{ font-size: 10px; text-transform: uppercase; color: #bbb; margin-bottom: 2px; }} /* COR AJUSTADA */
    .info-val {{ color: #fff; font-weight: bold; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    
    .status-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
    .status-box {{ padding: 10px; border-radius: 4px; text-align: center; border: 1px solid #333; }}
    .status-title {{ font-size: 11px; font-weight: bold; margin-bottom: 5px; color: #fff; }}
    .status-result {{ font-size: 14px; font-weight: bold; text-transform: uppercase; }}

    .risk-alert {{ background-color: #2b0505; color: #ffcccc !important; border: 2px solid #ff0000; padding: 20px; border-radius: 6px; margin-top: 15px; animation: pulse 2s infinite; }}
    .risk-title {{ color: #ff0000; font-weight: 900; font-size: 20px; margin-bottom: 10px; text-transform: uppercase; display: flex; align-items: center; gap: 10px; }}

    /* MODAIS MATEMÁTICOS */
    .modal-header {{ font-size: 22px; color: #00ff41; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; }}
    .modal-math {{ background: #111; padding: 15px; border-left: 3px solid #00ff41; font-family: monospace; font-size: 16px; color: #fff; margin-bottom: 15px; }} /* FONTE MAIS CLARA */
    .highlight-val {{ color: #00ff41; font-weight: bold; font-size: 18px; }}
    .modal-text {{ font-size: 14px; color: #ddd; line-height: 1.4; margin-top: 10px; border-top: 1px solid #333; padding-top: 10px; }} /* FONTE MAIS CLARA */
    .detail-list {{ font-size: 13px; color: #eee; margin-top: 10px; }} /* FONTE MAIS CLARA */
    .detail-item {{ margin-bottom: 8px; padding-left: 10px; border-left: 2px solid #555; }}
    .detail-key {{ color: #00ff41; font-weight: bold; font-size: 11px; text-transform: uppercase; }}
    
    .disclaimer {{ text-align: center; color: #777; font-size: 12px; margin-top: 50px; padding-top: 20px; border-top: 1px solid #222; }}
    @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }} 70% {{ box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }} }}
    #MainMenu, footer, header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==============================================================================
# 📡 CRAWLERS
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
# 📂 MODAIS (EDUCATIONAL & COMPLIANT)
# ==============================================================================
@st.dialog("📂 DOSSIÊ GRAHAM", width="large")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']
    margem = row['Margem']
    
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    
    # 1. CÁLCULO E STATUS
    c1, c2 = st.columns([1.5, 1])
    with c1: 
        st.markdown(f"""
        <div class="modal-math">
            VI = √(22.5 × LPA × VPA)<br>
            VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>
            VI = <span class="highlight-val">{format_brl(vi)}</span>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        status_color = "#00ff41" if margem > 0 else "#ff4444"
        # MUDANÇA: TERMOS MAIS TÉCNICOS/EDUCACIONAIS
        status_txt = "DESCONTADA" if margem > 0 else "ACIMA DO VI"
        st.markdown(f"""
        <div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px;">
            <div style="font-size:12px; color:#aaa">STATUS</div>
            <div style="font-size:20px; font-weight:bold; color:{status_color}">{status_txt}</div>
            <div style="font-size:14px; margin-top:5px">Margem: {margem:.1%}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. GLOSSÁRIO E EXPLICAÇÃO (FONTE MAIS CLARA)
    st.markdown("""
    <div class="modal-text">
        <b>🔍 ENTENDENDO A LÓGICA:</b>
        Benjamin Graham (mentor de Warren Buffett) dizia que o preço justo de uma ação deve ser calculado pelo lucro que ela gera e pelo patrimônio que ela possui.
    </div>
    <div class="detail-list">
        <div class="detail-item">
            <div class="detail-key">LPA (LUCRO POR AÇÃO)</div>
            Quanto a empresa lucra para cada ação que você tem. <br>LPA Alto = Empresa Lucrativa.
        </div>
        <div class="detail-item">
            <div class="detail-key">VPA (VALOR PATRIMONIAL POR AÇÃO)</div>
            Quanto vale tudo que a empresa tem (prédios, caixa, máquinas) dividido pelas ações. <br>VPA Alto = Empresa Rica em Ativos.
        </div>
        <div class="detail-item">
            <div class="detail-key">CONSTANTE 22.5</div>
            É o "número mágico" de Graham. Ele aceitava pagar no máximo P/L de 15 e P/VP de 1.5 (15 x 1.5 = 22.5).
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. ANÁLISE IA
    with st.spinner("🤖 IA: ANALISANDO MÉTODO GRAHAM..."):
        ai_text = get_graham_analysis(ticker, row['price'], vi, lpa, vpa)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ MAGIC FORMULA", width="large")
def show_magic_details(ticker, row):
    rev = int(row.get('R_EV', 0)); rroic = int(row.get('R_ROIC', 0)); sc = int(row.get('Score', 0))
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    
    # 1. CÁLCULO E STATUS
    c1, c2 = st.columns([1.5, 1])
    with c1: 
        st.markdown(f"""
        <div class="modal-math">
            SCORE = RANK(EV) + RANK(ROIC)<br>
            SCORE = #{rev} + #{rroic}<br>
            TOTAL = <span class="highlight-val">{sc} PONTOS</span>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        is_good = (row['roic'] > 0.15) and (row['ev_ebit'] > 0)
        status_color = "#00ff41" if is_good else "#ffaa00"
        # MUDANÇA: TERMOS MAIS TÉCNICOS/EDUCACIONAIS
        status_txt = "ALTA QUALIDADE" if is_good else "EM OBSERVAÇÃO"
        st.markdown(f"""
        <div style="text-align:center; border:1px solid {status_color}; padding:10px; border-radius:4px;">
            <div style="font-size:12px; color:#aaa">QUALIDADE</div>
            <div style="font-size:18px; font-weight:bold; color:{status_color}">{status_txt}</div>
            <div style="font-size:12px; margin-top:5px">ROIC: {row['roic']:.1%}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. GLOSSÁRIO E EXPLICAÇÃO (FONTE MAIS CLARA)
    st.markdown("""
    <div class="modal-text">
        <b>🔍 ENTENDENDO A LÓGICA:</b>
        Joel Greenblatt busca empresas "Boas e Baratas". Ele cria dois rankings separados e soma a posição da empresa em cada um. A empresa com MENOS pontos vence.
    </div>
    <div class="detail-list">
        <div class="detail-item">
            <div class="detail-key">EV/EBIT (O QUÃO BARATA ELA É)</div>
            Mede em quanto tempo o lucro operacional (EBIT) paga o valor da empresa (EV). <br>Quanto MENOR, mais barata.
        </div>
        <div class="detail-item">
            <div class="detail-key">ROIC (O QUÃO BOA ELA É)</div>
            Retorno sobre o Capital Investido. Mede a eficiência da gestão. <br>Quanto MAIOR, melhor a empresa.
        </div>
        <div class="detail-item">
            <div class="detail-key">SCORE FINAL</div>
            É a soma da posição no ranking de preço + posição no ranking de eficiência. <br>Pontuação Baixa = Top do Ranking.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. ANÁLISE IA
    with st.spinner("🤖 IA: ANALISANDO MAGIC FORMULA..."):
        ai_text = get_magic_analysis(ticker, row['ev_ebit'], row['roic'], sc)
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-title'>OPINIÃO DA IA</span></div>{ai_text}</div>", unsafe_allow_html=True)


@st.dialog("🧠 DECODE INTELLIGENCE", width="large")
def show_ai_decode(ticker, row, details):
    st.markdown(f"### 🎯 ALVO: {ticker}")
    st.markdown(f"""
    <div class="tag-grid">
        <div class="info-tag"><span class="info-label">EMPRESA</span><span class="info-val">{details.get('Empresa', 'N/A')}</span></div>
        <div class="info-tag"><span class="info-label">SETOR</span><span class="info-val">{details.get('Setor', 'N/A')}</span></div>
        <div class="info-tag"><span class="info-label">SEGMENTO</span><span class="info-val">{details.get('Segmento', 'N/A')}</span></div>
    </div>
    """, unsafe_allow_html=True)

    graham_ok = row['Margem'] > 0
    magic_ok = (row['roic'] > 0.10) and (row['ev_ebit'] > 0)
    
    st.markdown(f"""
    <div class="status-grid">
        <div class="status-box" style="background-color: {'#051a05' if graham_ok else '#1a0505'}; border-color: {'#00ff41' if graham_ok else '#ff4444'};">
            <div class="status-title" style="color:{'#00ff41' if graham_ok else '#ff4444'}">MÉTODO GRAHAM</div>
            <div class="status-result" style="color:{'#00ff41' if graham_ok else '#ff4444'}">{'✅ POSITIVO' if graham_ok else '❌ NEGATIVO'}</div>
            <div style="font-size:10px; color:#aaa; margin-top:2px">{'MARGEM: ' + f"{row['Margem']:.1%}" if graham_ok else 'SEM MARGEM'}</div>
        </div>
        <div class="status-box" style="background-color: {'#051a05' if magic_ok else '#1a1a05'}; border-color: {'#00ff41' if magic_ok else '#ffaa00'};">
            <div class="status-title" style="color:{'#00ff41' if magic_ok else '#ffaa00'}">MAGIC FORMULA</div>
            <div class="status-result" style="color:{'#00ff41' if magic_ok else '#ffaa00'}">{'✅ APROVADA' if magic_ok else '⚠️ ATENÇÃO'}</div>
            <div style="font-size:10px; color:#aaa; margin-top:2px">{'ROIC: ' + f"{row['roic']:.1%}" if magic_ok else 'ROIC BAIXO'}</div>
        </div>
    </div>
    <hr style="border-color: #333; margin: 15px 0;">
    """, unsafe_allow_html=True)
    
    with st.spinner("🛰️ SATÉLITE: PROCESSANDO..."):
        analise = get_sniper_analysis(ticker, row['price'], row['ValorJusto'], details)
    
    if "ALERTA" in analise.upper() or "RISCO" in analise.upper():
        st.markdown(f"<div class='risk-alert'><div class='risk-title'>💀 ALERTA DE RISCO DETECTADO</div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-box'><div class='ai-header'><span class='ai-icon'>🧠</span><span class='ai-title'>ANÁLISE TÁTICA (GEMINI)</span></div>{analise.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

# ==============================================================================
# 📺 UI PRINCIPAL
# ==============================================================================
c_logo, c_title = st.columns([1, 8])
with c_logo: st.image(URL_DO_ICONE, width=70)
with c_title: st.markdown(f"<h2 style='margin-top:10px'>SCOPE3 <span style='font-size:14px;color:#9933ff'>| ULTIMATE v9.0</span></h2>", unsafe_allow_html=True)
st.divider()

if 'market_data' not in st.session_state:
    if st.button("⚡ INICIAR VARREDURA COMPLETA"):
        with st.spinner("Baixando e Processando Dados da B3..."):
            df = get_data_direct()
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
    st.success(f"BASE OPERACIONAL: {len(df)} ATIVOS.")
    c_sel, c_btn, _ = st.columns([2, 1, 6])
    with c_sel: target = st.selectbox("ALVO:", options=sorted(df['ticker'].unique()))
    with c_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧠 DECODE IA") and target:
            row = df[df['ticker']==target].iloc[0]
            with st.spinner("BUSCANDO DETALHES..."): details = get_stock_details(target)
            show_ai_decode(target, row, details)

    st.markdown("---")
    ic1, ic2, ic3 = st.columns([1, 2, 2])
    with ic2: min_liq = st.number_input("Liquidez Mínima", value=200000, step=50000)
    with ic3: invest = st.number_input("Simular Investimento (R$)", value=0.0, step=100.0)
    df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
    t1, t2 = st.tabs(["💎 GRAHAM", "✨ MAGIC FORMULA"])
    
    # AJUSTE DE COMPLIANCE NO CARD TAMBÉM
    def card(t, p, l1, v1, l2, v2, r, inv=0):
        buy = f"<div class='buy-section'>APORTE SUGERIDO: <span class='buy-value'>{int((inv/10)//p)} ações</span></div>" if inv>0 and p>0 else ""
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
    st.markdown("---")
    df_exp = df_fin[['ticker', 'price', 'ValorJusto', 'Margem', 'ev_ebit', 'roic', 'MagicRank', 'liquidezmediadiaria']].copy()
    buffer = io.BytesIO(); 
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_exp.to_excel(writer, index=False)
    st.download_button("📥 DOWNLOAD EXCEL", data=buffer.getvalue(), file_name=f"SCOPE3_{datetime.now().strftime('%Y%m%d')}.xlsx")

st.markdown("""<div class="disclaimer">⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO. OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS. ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. O INVESTIDOR É RESPONSÁVEL POR SUAS PRÓPRIAS DECISÕES.</div>""", unsafe_allow_html=True)
