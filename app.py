import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Market Hacking v27.0", page_icon="💀", layout="wide")

# --- CSS DE ALTO CONTRASTE ---
st.markdown("""
<style>
    .stApp { background-color: #000000; background-image: linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px); background-size: 30px 30px; color: #e0e0e0; }
    * { font-family: 'Consolas', 'Courier New', monospace !important; }
    h1, h2, h3 { color: #00ff41 !important; text-shadow: 0 0 10px rgba(0, 255, 65, 0.8); font-weight: 900 !important; text-transform: uppercase; }
    div[data-testid="stNumberInput"] input { color: #ffffff !important; background-color: #111 !important; border: 2px solid #00ff41 !important; font-size: 30px !important; font-weight: bold !important; text-align: center !important; height: 70px !important; }
    .stButton>button { background-color: #000; color: #00ff41; border: 2px solid #00ff41; font-size: 18px !important; font-weight: bold; text-transform: uppercase; height: 60px; transition: 0.3s; box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); }
    .stButton>button:hover { background-color: #00ff41; color: #000; box-shadow: 0 0 25px #00ff41; transform: scale(1.02); }
    .hacker-card { background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 5px; border-radius: 4px; position: relative; }
    .card-ticker { font-size: 24px; color: #fff; font-weight: bold; }
    .card-price { font-size: 28px; color: #00ff41; font-weight: bold; float: right; text-shadow: 0 0 8px rgba(0, 255, 65, 0.4); }
    .metric-row { display: flex; justify-content: space-between; margin-top: 10px; padding-top: 10px; border-top: 1px solid #333; }
    .metric-label { color: #888; font-size: 14px; }
    .metric-value { color: #ffffff; font-weight: bold; font-size: 18px; }
    .buy-section { margin-top: 15px; background-color: rgba(255, 215, 0, 0.1); border: 1px dashed #FFD700; padding: 10px; color: #FFD700; font-weight: bold; text-align: center; text-transform: uppercase; letter-spacing: 1px; }
    
    /* MODAL */
    @keyframes unfold { 0% { transform: scaleY(0.005) scaleX(0); opacity: 0; } 30% { transform: scaleY(0.005) scaleX(1); opacity: 1; } 100% { transform: scaleY(1) scaleX(1); opacity: 1; } }
    div[role="dialog"] { width: 85vw !important; max-width: 90vw !important; background-color: #e6e6e6 !important; border: 4px solid #000 !important; box-shadow: 0 0 0 1000px rgba(0,0,0,0.8); border-radius: 5px; animation: unfold 0.8s cubic-bezier(0.165, 0.840, 0.440, 1.000) forwards; }
    div[role="dialog"] > div { width: 100% !important; }
    button[aria-label="Close"] { color: #000 !important; transform: scale(3.0) !important; margin-right: 30px !important; margin-top: 30px !important; }
    
    .modal-header { font-size: 32px; color: #000; border-bottom: 3px solid #000; padding-bottom: 10px; margin-bottom: 20px; text-transform: uppercase; font-weight: 900; letter-spacing: 2px; }
    .modal-math { font-size: 28px; color: #000; background-color: #fff; padding: 30px; border: 2px solid #000; margin: 10px 0; font-family: 'Verdana', sans-serif !important; font-weight: bold; box-shadow: 8px 8px 0px rgba(0,0,0,0.2); }
    .modal-subtitle { font-size: 22px; color: #000; font-weight: bold; margin-top: 15px; margin-bottom: 5px; text-decoration: underline; }
    .modal-text { font-size: 20px; color: #222; line-height: 1.5; margin-bottom: 10px; font-weight: 600; }
    .term-def { color: #444; font-size: 16px; font-style: italic; display: block; margin-bottom: 15px; border-left: 3px solid #ccc; padding-left: 10px; }
    .highlight-val { color: #000; background-color: #00ff41; padding: 0 5px; font-weight: 900; border: 1px solid #000; }
    .highlight-score { color: #fff; background-color: #000; padding: 2px 10px; font-weight: 900; border-radius: 4px; font-size: 110%; }
    
    .terminal-box { background-color: #050505; border: 1px solid #00ff41; padding: 15px; font-size: 16px; color: #00ff41; margin-bottom: 20px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.1); font-family: 'Courier New', monospace; height: 350px; overflow-y: hidden; display: flex; flex-direction: column; justify-content: flex-end; }
</style>
""", unsafe_allow_html=True)

# --- HELPER BRL ---
def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- LOAD EXCEL DATABASE ---
@st.cache_data
def load_excel_db():
    try:
        df = pd.read_excel('empresas.xlsx')
        ticker_col = df.columns[0]
        db = {}
        for _, row in df.iterrows():
            ticker = str(row[ticker_col]).strip().upper()
            nome = row.iloc[1] if len(row) > 1 else "S.A."
            segmento = row.iloc[3] if len(row) > 3 else "GERAL"
            db[ticker] = {'nome': str(nome), 'segmento': str(segmento)}
        return db
    except: return {}
EXCEL_DB = load_excel_db()

# --- ESTADO ---
if 'market_data' not in st.session_state: st.session_state['market_data'] = pd.DataFrame()
if 'data_loaded' not in st.session_state: st.session_state['data_loaded'] = False
if 'valuation_run' not in st.session_state: st.session_state['valuation_run'] = False
if 'stats_raw' not in st.session_state: st.session_state['stats_raw'] = 0
if 'stats_removed' not in st.session_state: st.session_state['stats_removed'] = 0

# --- EXTRAÇÃO DIRETA (SEM CLOUDSCRAPER) ---
@st.cache_data(show_spinner=False)
def get_data_direct():
    url = 'https://www.fundamentus.com.br/resultado.php'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        # Tenta conectar direto
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        
        # Lê a tabela usando LXML (que já instalamos)
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        
        rename_map = {'Papel': 'ticker', 'Cotação': 'price', 'P/L': 'pl', 'P/VP': 'pvp', 'EV/EBIT': 'ev_ebit', 'ROIC': 'roic', 'Liq.2meses': 'liquidezmediadiaria'}
        df.rename(columns=rename_map, inplace=True)
        
        for col in df.columns:
            if df[col].dtype == object and col != 'ticker':
                df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['roic'] = df['roic'] / 100
        df['lpa'] = df.apply(lambda x: x['price'] / x['pl'] if x['pl'] > 0 else 0, axis=1)
        df['vpa'] = df.apply(lambda x: x['price'] / x['pvp'] if x['pvp'] > 0 else 0, axis=1)
        return df
    except: return pd.DataFrame()

# --- MODAIS ---
@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">FÓRMULA APLICADA</div><div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div><div style="text-align:center;color:#000;font-size:20px;margin-top:20px;">PREÇO: <b>{format_brl(row['price'])}</b> | POTENCIAL: <b style="color:#008000">{row['Margem']:.1%}</b></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="modal-subtitle">GLOSSÁRIO</div><div class="modal-text"><b>VI:</b> Valor Intrínseco (Preço Justo).<br><b>LPA:</b> Lucro por Ação.<br><b>VPA:</b> Valor Patrimonial.<br><b>22.5:</b> Constante de Graham.</div>""", unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_magic_details(ticker, row):
    ev = row['ev_ebit']; roic = row['roic']; rev = int(row['R_EV']); rroic = int(row['R_ROIC']); sc = int(row['Score'])
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">MODELO GREENBLATT</div><div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-score">{sc}</span></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div class="modal-subtitle">GLOSSÁRIO</div><div class="modal-text"><b>EV/EBIT:</b> Preço (menor é melhor).<br><b>ROIC:</b> Qualidade (maior é melhor).<br><b>Score:</b> Soma dos rankings.</div>""", unsafe_allow_html=True)

# --- LÓGICA DO SCAN ---
def run_scan_logic():
    terminal = st.empty()
    df_raw = get_data_direct()
    
    if df_raw.empty: return pd.DataFrame(), 0, 0
    
    total_bruto = len(df_raw)
    real_tickers = df_raw['ticker'].unique().tolist()
    random.shuffle(real_tickers)
    
    # Animação
    log = ["<span style='color:#fff'>CONECTANDO DATABASE FUNDAMENTUS...</span>", "<span style='color:#00ff41'>ACESSO CONCEDIDO.</span>", "-"*40]
    for i in range(12):
        t = random.choice(real_tickers) if real_tickers else "..."
        log.append(f"> EXTRAINDO: {t} ... [OK]")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}<br><span style="color:#fff;animation:blink 0.2s infinite">_</span></div>""", unsafe_allow_html=True)
        time.sleep(0.05)
    
    # --- LIMPEZA REAL (REFINARIA) ---
    # 1. Zumbis (Liquidez e Preço Zero)
    mask_zombie = (df_raw['liquidezmediadiaria'] <= 0) | (df_raw['price'] <= 0)
    qtd_zombie = mask_zombie.sum()
    
    # 2. Fracionários (Terminam em F)
    mask_frac = df_raw['ticker'].astype(str).str.endswith('F')
    qtd_frac = mask_frac.sum()
    
    # 3. BDRs (Terminam em 32, 33, 34, 35)
    mask_bdr = df_raw['ticker'].astype(str).str.contains(r'(32|33|34|35)$', regex=True)
    qtd_bdr = mask_bdr.sum()
    
    # Aplica Filtros
    mask_trash = mask_zombie | mask_frac | mask_bdr
    df_clean = df_raw[~mask_trash].copy()
    
    removed = total_bruto - len(df_clean)
    
    # Relatório Visual
    log.append(f"<br><span style='color:#FFD700'> >>> INICIANDO REFINARIA DE DADOS <<< </span>")
    terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}</div>""", unsafe_allow_html=True)
    time.sleep(1)
    
    log.append(f"> TOTAL BRUTO: {total_bruto}")
    
    if qtd_frac > 0:
        log.append(f"> REMOVENDO FRACIONÁRIOS... <span style='color:red'>-{qtd_frac}</span>")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}</div>""", unsafe_allow_html=True)
        time.sleep(0.5)
        
    if qtd_bdr > 0:
        log.append(f"> REMOVENDO BDRs (MERCADO EXTERNO)... <span style='color:red'>-{qtd_bdr}</span>")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}</div>""", unsafe_allow_html=True)
        time.sleep(0.5)
        
    if qtd_zombie > 0:
        log.append(f"> REMOVENDO ZUMBIS (SEM LIQUIDEZ)... <span style='color:red'>-{qtd_zombie}</span>")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}</div>""", unsafe_allow_html=True)
        time.sleep(0.5)

    log.append(f"<span style='color:#00ff41;font-weight:bold'> >>> BASE BRASIL CONSOLIDADA: {len(df_clean)} ATIVOS <<< </span>")
    terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-12:])}</div>""", unsafe_allow_html=True)
    time.sleep(2.5)
    terminal.empty()
    return df_clean, total_bruto, removed

# --- MAIN UI ---
st.title("💀 MARKET HACKING v27.0")
st.markdown("`> PROTOCOLO: DEEP VALUE` | `> FONTE: FUNDAMENTUS` | `> FILTRO: AÇÕES BR`")
st.divider()

c1, c2 = st.columns([1, 2])
with c1:
    btn_txt = "⚡ RE-INICIAR ATAQUE" if st.session_state['data_loaded'] else "⚡ INICIAR ATAQUE DE DADOS"
    if st.button(btn_txt):
        s = st.empty()
        s.info("⏳ ACESSANDO GATEWAY DE DADOS...")
        time.sleep(0.5)
        df, raw, rem = run_scan_logic()
        if not df.empty:
            s.empty()
            st.session_state.update({'market_data': df, 'stats_raw': raw, 'stats_removed': rem, 'data_loaded': True})
            st.rerun()
        else: s.error("ERRO DE CONEXÃO.")

with c2:
    if st.session_state['data_loaded']:
        st.success(f"RELATÓRIO: {st.session_state['stats_raw']} TOTAIS ➔ {st.session_state['stats_removed']} FILTRADOS (BDR/LIXO) ➔ {len(st.session_state['market_data'])} AÇÕES BR VÁLIDAS.")
    else: st.info("SISTEMA EM STANDBY. CLIQUE PARA INICIAR.")

st.divider()

if st.session_state['data_loaded']:
    df = st.session_state['market_data']
    st.markdown("<h3 style='text-align:center'>PARÂMETROS</h3>", unsafe_allow_html=True)
    ic1, ic2, ic3, ic4 = st.columns([1,2,2,1])
    with ic2: min_liq = st.number_input("Liquidez Min", value=200000, step=50000)
    with ic3: invest = st.number_input("Investimento", value=0.0, step=100.0)
    
    st.markdown("<br>", unsafe_allow_html=True)
    cb1, cb2, cb3 = st.columns([1,1,1])
    with cb2: 
        if st.button("💀 EXECUTAR VALORAÇÃO"): st.session_state['valuation_run'] = True

    if st.session_state['valuation_run']:
        df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
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
