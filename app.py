import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random

# --- TENTATIVA DE IMPORTAÇÃO SEGURA (ANTI-CRASH) ---
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# --- CONFIGURAÇÃO VISUAL (TEMA HACKER DARK) ---
st.set_page_config(page_title="Market Hacking v25.0", page_icon="💀", layout="wide")

# --- DATABASE DE NOMES REAIS ---
TICKER_DB = {
    'PETR4': 'PETROLEO BRASILEIRO S.A. PETROBRAS', 'VALE3': 'VALE S.A.', 'ITUB4': 'ITAU UNIBANCO HOLDING S.A.',
    'BBDC4': 'BANCO BRADESCO S.A.', 'BBAS3': 'BANCO DO BRASIL S.A.', 'WEGE3': 'WEG S.A.',
    'ABEV3': 'AMBEV S.A.', 'RENT3': 'LOCALIZA RENT A CAR S.A.', 'BPAC11': 'BANCO BTG PACTUAL S.A.',
    'SUZB3': 'SUZANO S.A.', 'ITSA4': 'ITAUSA S.A.', 'HAPV3': 'HAPVIDA PARTICIPACOES E INVESTIMENTOS S.A.',
    'EQTL3': 'EQUATORIAL ENERGIA S.A.', 'GGBR4': 'GERDAU S.A.', 'RDOR3': 'REDE D OR SAO LUIZ S.A.',
    'RADL3': 'RAIA DROGASIL S.A.', 'CSAN3': 'COSAN S.A.', 'PRIO3': 'PRIO S.A.',
    'JBSS3': 'JBS S.A.', 'LREN3': 'LOJAS RENNER S.A.', 'ENEV3': 'ENEVA S.A.',
    'BBSE3': 'BB SEGURIDADE PARTICIPACOES S.A.', 'VIVT3': 'TELEFONICA BRASIL S.A.', 'RAIL3': 'RUMO S.A.',
    'SBSP3': 'CIA SANEAMENTO BASICO SP', 'CMIG4': 'CIA ENERGETICA MINAS GERAIS',
    'UGPA3': 'ULTRAPAR PARTICIPACOES S.A.', 'CPLE6': 'COPEL', 'EMBR3': 'EMBRAER S.A.', 
    'CSNA3': 'CIA SIDERURGICA NACIONAL', 'TIMS3': 'TIM S.A.', 'ALOS3': 'ALLOS S.A.', 
    'ELET3': 'ELETROBRAS', 'KLBN11': 'KLABIN S.A.', 'BRFS3': 'BRF S.A.', 'CCRO3': 'CCR S.A.',
    'TOTS3': 'TOTVS S.A.', 'MULT3': 'MULTIPLAN S.A.', 'CIEL3': 'CIELO S.A.', 
    'YDUQ3': 'YDUQS S.A.', 'CVCB3': 'CVC BRASIL', 'MGLU3': 'MAGAZINE LUIZA', 
    'VIIA3': 'CASAS BAHIA', 'GOLL4': 'GOL LINHAS AEREAS', 'AZUL4': 'AZUL S.A.', 
    'PETZ3': 'PET CENTER', 'USIM5': 'USIMINAS', 'GOAU4': 'METALURGICA GERDAU',
    'MRFG3': 'MARFRIG', 'BEEF3': 'MINERVA', 'ASAI3': 'ASSAI ATACADISTA',
    'CRFB3': 'CARREFOUR BRASIL', 'PCAR3': 'PAO DE ACUCAR', 'NTCO3': 'NATURA &CO',
    'SOMA3': 'GRUPO SOMA', 'ARZZ3': 'AREZZO', 'FLRY3': 'FLEURY', 'PSSA3': 'PORTO SEGURO', 
    'IRBR3': 'IRB BRASIL', 'CXSE3': 'CAIXA SEGURIDADE', 'SAPR11': 'SANEPAR',
    'TRPL4': 'ISA CTEEP', 'TAEE11': 'TAESA', 'CPFE3': 'CPFL ENERGIA', 
    'EGIE3': 'ENGIE BRASIL', 'ENGI11': 'ENERGISA', 'CYRE3': 'CYRELA', 
    'EZTC3': 'EZTEC', 'MRVE3': 'MRV', 'JHSF3': 'JHSF', 'SLCE3': 'SLC AGRICOLA'
}

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: #000000; background-image: linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px); background-size: 30px 30px; color: #e0e0e0; }
    * { font-family: 'Consolas', 'Courier New', monospace !important; }
    h1, h2, h3 { color: #00ff41 !important; text-shadow: 0 0 10px rgba(0, 255, 65, 0.8); font-weight: 900 !important; text-transform: uppercase; }
    
    div[data-testid="stNumberInput"] input { color: #ffffff !important; background-color: #111 !important; border: 2px solid #00ff41 !important; font-size: 30px !important; font-weight: bold !important; text-align: center !important; height: 70px !important; }
    div[data-testid="stNumberInput"] label { display: none; }
    
    .stButton>button { background-color: #000; color: #00ff41; border: 2px solid #00ff41; font-size: 18px !important; font-weight: bold; text-transform: uppercase; height: 60px; transition: 0.3s; box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); }
    .stButton>button:hover { background-color: #00ff41; color: #000; box-shadow: 0 0 25px #00ff41; transform: scale(1.02); }
    
    .hacker-card { background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 5px; border-radius: 4px; position: relative; }
    .card-ticker { font-size: 24px; color: #fff; font-weight: bold; }
    .card-price { font-size: 28px; color: #00ff41; font-weight: bold; float: right; text-shadow: 0 0 8px rgba(0, 255, 65, 0.4); }
    .metric-row { display: flex; justify-content: space-between; margin-top: 10px; padding-top: 10px; border-top: 1px solid #333; }
    .metric-label { color: #888; font-size: 14px; }
    .metric-value { color: #ffffff; font-weight: bold; font-size: 18px; }
    .buy-section { margin-top: 15px; background-color: rgba(255, 215, 0, 0.1); border: 1px dashed #FFD700; padding: 10px; color: #FFD700; font-weight: bold; text-align: center; text-transform: uppercase; letter-spacing: 1px; }
    .buy-value { font-size: 20px; color: #fff; }
    
    @keyframes unfold { 0% { transform: scaleY(0.005) scaleX(0); opacity: 0; } 30% { transform: scaleY(0.005) scaleX(1); opacity: 1; } 100% { transform: scaleY(1) scaleX(1); opacity: 1; } }

    div[role="dialog"] { width: 85vw !important; max-width: 90vw !important; background-color: #e6e6e6 !important; border: 4px solid #000 !important; box-shadow: 0 0 0 1000px rgba(0,0,0,0.8); border-radius: 5px; animation: unfold 0.8s cubic-bezier(0.165, 0.840, 0.440, 1.000) forwards; }
    div[role="dialog"] > div { width: 100% !important; }
    
    button[aria-label="Close"] { color: #000 !important; transform: scale(3.0) !important; margin-right: 30px !important; margin-top: 30px !important; background: transparent !important; border: none !important; }
    button[aria-label="Close"]:hover { color: #ff0000 !important; }
    
    .modal-header { font-size: 32px; color: #000; border-bottom: 3px solid #000; padding-bottom: 10px; margin-bottom: 20px; text-transform: uppercase; font-weight: 900; letter-spacing: 2px; }
    .modal-math { font-size: 28px; color: #000; background-color: #fff; padding: 30px; border: 2px solid #000; margin: 10px 0; font-family: 'Verdana', sans-serif !important; font-weight: bold; box-shadow: 8px 8px 0px rgba(0,0,0,0.2); }
    .modal-subtitle { font-size: 22px; color: #000; font-weight: bold; margin-top: 15px; margin-bottom: 5px; text-decoration: underline; }
    .modal-text { font-size: 20px; color: #222; line-height: 1.5; margin-bottom: 10px; font-weight: 600; }
    .term-def { color: #444; font-size: 16px; font-style: italic; display: block; margin-bottom: 15px; border-left: 3px solid #ccc; padding-left: 10px; }
    .highlight-val { color: #000; background-color: #00ff41; padding: 0 5px; font-weight: 900; border: 1px solid #000; }
    .highlight-score { color: #fff; background-color: #000; padding: 2px 10px; font-weight: 900; border-radius: 4px; font-size: 110%; }

    .intel-box { border: 2px dashed #444; background-color: #050505; padding: 25px; margin-bottom: 30px; text-align: center; border-radius: 10px; }
    .intel-title { color: #ccc; font-size: 22px; font-weight: bold; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 15px; }
    .intel-math { color: #00ff41; font-size: 40px; font-weight: 900; text-shadow: 0 0 15px rgba(0, 255, 65, 0.6); margin-bottom: 10px; }
    .intel-desc { color: #fff; font-size: 18px; font-style: italic; }
    
    .value-feedback { text-align: center; background-color: #000; color: #fff; font-size: 16px; padding: 5px; border: 1px solid #333; margin-top: 5px; margin-bottom: 20px; }
    .terminal-box { background-color: #050505; border: 1px solid #00ff41; padding: 15px; font-size: 16px; color: #00ff41; margin-bottom: 20px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.1); font-family: 'Courier New', monospace; height: 400px; overflow-y: hidden; display: flex; flex-direction: column; justify-content: flex-end; }
    
    .stFileUploader label { color: #00ff41 !important; font-size: 20px !important; }
    .stFileUploader div[data-testid="stFileUploaderDropzone"] { background-color: #111; border: 2px dashed #00ff41; }
</style>
""", unsafe_allow_html=True)

# --- HELPER: FORMATAÇÃO BRL ---
def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- ESTADO ---
if 'market_data' not in st.session_state: st.session_state['market_data'] = pd.DataFrame()
if 'data_loaded' not in st.session_state: st.session_state['data_loaded'] = False
if 'valuation_run' not in st.session_state: st.session_state['valuation_run'] = False
if 'stats_raw' not in st.session_state: st.session_state['stats_raw'] = 0
if 'stats_removed' not in st.session_state: st.session_state['stats_removed'] = 0
if 'upload_mode' not in st.session_state: st.session_state['upload_mode'] = False

# --- EXTRAÇÃO REAL (COM FALLBACK PARA REQUESTS COMUM) ---
def get_data_feed():
    url = 'https://statusinvest.com.br/category/advancedsearchresultexport'
    search_payload = '{}'
    params = {'search': search_payload, 'CategoryType': 1}
    
    # Tentativa 1: Cloudscraper (A melhor arma)
    if HAS_CLOUDSCRAPER:
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, params=params)
            if response.status_code == 200:
                return pd.read_csv(io.StringIO(response.text), sep=';', decimal=',', thousands='.')
        except Exception:
            pass # Se falhar, tenta o método 2
            
    # Tentativa 2: Requests comum com User-Agent de gente
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return pd.read_csv(io.StringIO(response.text), sep=';', decimal=',', thousands='.')
    except Exception:
        pass
        
    return pd.DataFrame() # Retorna vazio se tudo falhar

# --- MODAIS E VISUALIZAÇÃO ---
@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">FÓRMULA APLICADA</div><div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div><div style="text-align:center;color:#000;font-size:20px;margin-top:20px;">PREÇO: <b>{format_brl(row['price'])}</b> | POTENCIAL: <b style="color:#008000">{row['Margem']:.1%}</b></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="modal-subtitle">GLOSSÁRIO</div><div class="modal-text"><b>VI:</b> Preço Justo teórico.<br><b>LPA:</b> Lucro por Ação.<br><b>VPA:</b> Valor Patrimonial.<br><b>22.5:</b> Constante de Graham.</div>""", unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_magic_details(ticker, row):
    ev = row['ev_ebit']; roic = row['roic']; rev = int(row['R_EV']); rroic = int(row['R_ROIC']); sc = int(row['Score'])
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">MODELO GREENBLATT</div><div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-score">{sc}</span></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="modal-subtitle">GLOSSÁRIO</div><div class="modal-text"><b>EV/EBIT:</b> Preço (menor é melhor).<br><b>ROIC:</b> Qualidade (maior é melhor).<br><b>Score:</b> Soma dos rankings.</div>""", unsafe_allow_html=True)

# --- PROCESSAMENTO ---
def run_scan_logic(df_raw):
    terminal = st.empty()
    real_tickers = df_raw['ticker'].dropna().unique().tolist(); random.shuffle(real_tickers)
    
    # Animação Rápida
    log = [f"<span style='color:#fff'>CONECTANDO...</span>", f"<span style='color:#00ff41'>BAIXANDO DADOS...</span>"]
    for i in range(10):
        t = random.choice(real_tickers) if real_tickers else "..."
        log.append(f"> LENDO: {t} ... [OK]")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-10:])}</div>""", unsafe_allow_html=True)
        time.sleep(0.05)
    
    # Limpeza
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    rmap = {'preco':'price','preço':'price','liquidez media diaria':'liquidezmediadiaria','liq. media diaria':'liquidezmediadiaria','p/l':'p_l','p/vp':'p_vp','ev/ebit':'ev_ebit','ticker':'ticker','roic':'roic','lpa':'lpa','vpa':'vpa'}
    df_raw.rename(columns=rmap, inplace=True)
    
    if 'liquidezmediadiaria' in df_raw.columns: df_raw['liquidezmediadiaria'] = pd.to_numeric(df_raw['liquidezmediadiaria'], errors='coerce').fillna(0)
    if 'price' in df_raw.columns: df_raw['price'] = pd.to_numeric(df_raw['price'], errors='coerce').fillna(0)
    
    total_bruto = len(df_raw)
    mask = df_raw['ticker'].astype(str).str.endswith('F') | (df_raw['liquidezmediadiaria'] <= 0) | (df_raw['price'] <= 0)
    df_clean = df_raw[~mask].copy()
    
    terminal.empty()
    return df_clean, total_bruto, (total_bruto - len(df_clean))

# --- MAIN UI ---
st.title("💀 MARKET HACKING_v25.0")
st.markdown("`> PROTOCOLO: DEEP VALUE` | `> ALVO: BOLSA DE VALORES`")
st.divider()

c_btn, c_status = st.columns([1, 2])
with c_btn:
    lbl = "⚡ RE-INICIAR ATAQUE" if st.session_state['data_loaded'] else "⚡ INICIAR ATAQUE DE DADOS"
    if st.button(lbl):
        s = st.empty()
        s.info("⏳ INICIANDO VARREDURA...")
        
        df_raw = get_data_feed()
        
        if not df_raw.empty:
            s.success("DADOS CAPTURADOS!")
            time.sleep(0.5)
            s.empty()
            df, raw, rem = run_scan_logic(df_raw)
            st.session_state.update({'market_data': df, 'stats_raw': raw, 'stats_removed': rem, 'data_loaded': True, 'upload_mode': False})
            st.rerun()
        else:
            s.error("ERRO 403: SERVIDOR PROTEGIDO. ATIVANDO MODO MANUAL.")
            time.sleep(2); s.empty()
            st.session_state['upload_mode'] = True
            st.rerun()

with c_status:
    if st.session_state['data_loaded']:
        st.success(f"RELATÓRIO: {st.session_state['stats_raw']} BAIXADOS ➔ {st.session_state['stats_removed']} LIXO ➔ {len(st.session_state['market_data'])} VÁLIDOS.")
    elif st.session_state['upload_mode']:
        st.warning("⚠️ MODO MANUAL ATIVO: FAÇA UPLOAD ABAIXO.")
    else:
        status_msg = "SISTEMA PRONTO."
        if not HAS_CLOUDSCRAPER: status_msg += " (MODO SAFE: CLOUDSCRAPER OFF)"
        st.info(status_msg)

if st.session_state['upload_mode']:
    st.markdown("### 📂 UPLOAD MANUAL (STATUSINVEST.CSV)")
    up = st.file_uploader("ARRASTE O ARQUIVO AQUI", type=['csv'])
    if up:
        try:
            df_raw = pd.read_csv(up, sep=';', decimal=',', thousands='.')
            df, raw, rem = run_scan_logic(df_raw)
            st.session_state.update({'market_data': df, 'stats_raw': raw, 'stats_removed': rem, 'data_loaded': True, 'upload_mode': False})
            st.rerun()
        except: st.error("ARQUIVO INVÁLIDO")

st.divider()

if st.session_state['data_loaded']:
    df = st.session_state['market_data']
    st.markdown("<h3 style='text-align:center'>PARÂMETROS</h3>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1,2,2,1])
    with c2: min_liq = st.number_input("Liquidez Min", value=200000, step=50000)
    with c3: invest = st.number_input("Investimento", value=0.0, step=100.0)
    
    st.markdown("<br>", unsafe_allow_html=True)
    cb1, cb2, cb3 = st.columns([1,1,1])
    with cb2: 
        if st.button("💀 EXECUTAR VALORAÇÃO"): st.session_state['valuation_run'] = True

    if st.session_state['valuation_run']:
        cols = ['price', 'vpa', 'lpa', 'ev_ebit', 'roic', 'liquidezmediadiaria']
        for c in cols: 
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df_fin = df[df['liquidezmediadiaria'] > min_liq].dropna(subset=cols).copy()
        
        st.markdown(f"### RESULTADO: {len(df_fin)} ATIVOS")
        t1, t2 = st.tabs(["GRAHAM", "MAGIC FORMULA"])
        
        def card(t, p, l1, v1, l2, v2, r, inv=0):
            nm = f"{EXCEL_DB[t]['nome']} ({EXCEL_DB[t]['segmento']})" if t in EXCEL_DB else ""
            buy = ""
            if inv > 0 and p > 0:
                q = int((invest/10)//p); c = q*p
                buy = f"<div class='buy-section'>COMPRA: <span class='buy-value'>{q} un. ({format_brl(c)})</span></div>"
            return f"""<div class="hacker-card"><div><span class="card-ticker">#{r} {t}</span><span class="card-price">{format_brl(p)}</span></div><div style='color:#888;font-size:12px'>{nm}</div><div class="metric-row"><div><div class="metric-label">{l1}</div><div class="metric-value">{v1}</div></div><div style="text-align:right"><div class="metric-label">{l2}</div><div class="metric-value">{v2}</div></div></div>{buy}</div>"""

        with t1:
            df_g = df_fin[(df_fin['lpa']>0)&(df_fin['vpa']>0)].copy()
            df_g['ValorJusto'] = np.sqrt(22.5 * df_g['lpa'] * df_g['vpa'])
            df_g['Margem'] = (df_g['ValorJusto']/df_g['price']) - 1
            top = df_g.sort_values('Margem', ascending=False).head(10)
            cc1, cc2 = st.columns(2)
            for i, r in top.reset_index().iterrows():
                html = card(r['ticker'], r['price'], "VALOR JUSTO", format_brl(r['ValorJusto']), "POTENCIAL", f"{r['Margem']:.1%}", i+1, invest)
                with (cc1 if i%2==0 else cc2):
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"g_{r['ticker']}"): show_graham_details(r['ticker'], r)

        with t2:
            df_m = df_fin[(df_fin['ev_ebit']>0)&(df_fin['roic']>0)].copy()
            df_m['Score'] = df_m['ev_ebit'].rank(ascending=True) + df_m['roic'].rank(ascending=False)
            df_m['R_EV'] = df_m['ev_ebit'].rank(ascending=True); df_m['R_ROIC'] = df_m['roic'].rank(ascending=False)
            top = df_m.sort_values('Score').head(10)
            cc1, cc2 = st.columns(2)
            for i, r in top.reset_index().iterrows():
                html = card(r['ticker'], r['price'], "EV/EBIT", f"{r['ev_ebit']:.2f}", "ROIC", f"{r['roic']:.1%}", i+1, invest)
                with (cc1 if i%2==0 else cc2):
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"m_{r['ticker']}"): show_magic_details(r['ticker'], r)
