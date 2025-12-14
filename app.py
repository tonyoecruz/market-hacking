import streamlit as st
import pandas as pd
import cloudscraper # A ARMA SECRETA CONTRA BLOQUEIOS
import io
import numpy as np
import time
import random

# --- CONFIGURAÇÃO VISUAL (TEMA HACKER DARK) ---
st.set_page_config(page_title="Market Hacking v24.0", page_icon="💀", layout="wide")

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

# --- CSS DE ALTO CONTRASTE ---
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
</style>
""", unsafe_allow_html=True)

# --- HELPER: FORMATAÇÃO BRL ---
def format_brl(value):
    if pd.isna(value): return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- LOAD EXCEL DATABASE ---
@st.cache_data
def load_excel_db():
    try:
        df_excel = pd.read_excel('empresas.xlsx')
        df_excel.columns = [str(c).lower().strip() for c in df_excel.columns]
        ticker_col = df_excel.columns[0] 
        db = {}
        for index, row in df_excel.iterrows():
            ticker = str(row[ticker_col]).strip().upper()
            nome = row.iloc[1] if len(row) > 1 else "CORP S.A."
            setor = row.iloc[2] if len(row) > 2 else "MERCADO"
            segmento = row.iloc[3] if len(row) > 3 else "GERAL"
            db[ticker] = {'nome': str(nome), 'setor': str(setor), 'segmento': str(segmento)}
        return db
    except Exception:
        return {}
EXCEL_DB = load_excel_db()

# --- ESTADO ---
if 'market_data' not in st.session_state: st.session_state['market_data'] = pd.DataFrame()
if 'data_loaded' not in st.session_state: st.session_state['data_loaded'] = False
if 'valuation_run' not in st.session_state: st.session_state['valuation_run'] = False
if 'stats_raw' not in st.session_state: st.session_state['stats_raw'] = 0
if 'stats_removed' not in st.session_state: st.session_state['stats_removed'] = 0

# --- EXTRAÇÃO REAL (STEALTH MODE / CLOUDSCRAPER) ---
@st.cache_data(show_spinner=False)
def get_data_feed():
    try:
        # USA CLOUDSCRAPER PARA ENGANAR O CLOUDFLARE
        scraper = cloudscraper.create_scraper()
        
        url = 'https://statusinvest.com.br/category/advancedsearchresultexport'
        search_payload = '{}' # TUDO
        params = {'search': search_payload, 'CategoryType': 1}
        
        # Headers mais robustos
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://statusinvest.com.br/acoes/busca-avancada'
        }
        
        # Faz a requisição usando o scraper, não o requests
        response = scraper.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text), sep=';', decimal=',', thousands='.')
            return df
        else:
            return pd.DataFrame() # Retorna vazio se der erro
            
    except Exception:
        return pd.DataFrame()

# --- MODAL: DETALHES GRAHAM ---
@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_graham_details(ticker, row):
    lpa = row['lpa']
    vpa = row['vpa']
    vi = row['ValorJusto']
    
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c_math, c_desc = st.columns([1.5, 1])
    with c_math:
        st.markdown(f"""
        <div class="modal-subtitle">FÓRMULA APLICADA</div>
        <div class="modal-math">
            VI = √(22.5 × LPA × VPA)<br><br>
            VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br><br>
            VI = <span class="highlight-val">{format_brl(vi)}</span>
        </div>
        <div style="text-align:center; color:#000; font-size:20px; margin-top:20px;">
            PREÇO ATUAL: <b>{format_brl(row['price'])}</b> &nbsp;|&nbsp; 
            POTENCIAL: <b style="color:#008000">{row['Margem']:.1%}</b>
        </div>
        """, unsafe_allow_html=True)
    with c_desc:
        st.markdown(f"""
        <div class="modal-subtitle">GLOSSÁRIO TÉCNICO</div>
        <div class="modal-text">
            <b>1. VI (Valor Intrínseco)</b>
            <span class="term-def">É o "Preço Justo" teórico. O valor real que a ação deveria custar baseado em seu lucro e patrimônio.</span>
            <b>2. LPA (Lucro Por Ação): {lpa:.2f}</b>
            <span class="term-def">Valor do lucro líquido dividido pelo nº de ações. Quanto a empresa lucra para cada papel.</span>
            <b>3. VPA (Valor Patrimonial): {vpa:.2f}</b>
            <span class="term-def">Patrimônio Líquido (Bens - Dívidas) dividido por ação. É o valor contábil.</span>
            <b>4. Constante 22.5</b>
            <span class="term-def">Número de Graham. Ele aceitava P/L máximo de 15 e P/VP máximo de 1.5. (15 × 1.5 = 22.5).</span>
            <b>5. Potencial (Upside)</b>
            <span class="term-def">Quanto a ação pode subir até atingir o Valor Justo.</span>
        </div>
        """, unsafe_allow_html=True)

# --- MODAL: DETALHES MAGIC FORMULA ---
@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_magic_details(ticker, row):
    ev_ebit = row['ev_ebit']
    roic = row['roic']
    rank_ev = int(row['R_EV'])
    rank_roic = int(row['R_ROIC'])
    score = int(row['Score'])
    
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c_math, c_desc = st.columns([1.5, 1])
    with c_math:
        st.markdown(f"""
        <div class="modal-subtitle">MODELO GREENBLATT</div>
        <div class="modal-math">
            SCORE = RANK(EV/EBIT) + RANK(ROIC)<br><br>
            SCORE = #{rank_ev} + #{rank_roic}<br><br>
            TOTAL = <span class="highlight-score">{score}</span>
        </div>
        <div style="text-align:center; font-size:16px; color:#333; margin-top:10px;">
            *Quanto MENOR a pontuação, MELHOR a posição no ranking.
        </div>
        """, unsafe_allow_html=True)
    with c_desc:
        st.markdown(f"""
        <div class="modal-subtitle">GLOSSÁRIO TÉCNICO</div>
        <div class="modal-text">
            <b>1. EV/EBIT (Indicador de Preço): {ev_ebit:.2f}</b>
            <span class="term-def"><b>EV:</b> Valor da Firma. <b>EBIT:</b> Lucro Operacional. Indica em quantos anos o lucro paga a empresa. (Você é o <b>#{rank_ev}º</b> mais barato).</span>
            <b>2. ROIC (Indicador de Qualidade): {roic:.1%}</b>
            <span class="term-def"><b>Retorno s/ Capital Investido:</b> Mede a eficiência. Quanto lucro gera para cada real investido. (Você é o <b>#{rank_roic}º</b> mais rentável).</span>
            <b>3. Score {score}</b>
            <span class="term-def">Soma dos rankings. Vence a empresa que é ao mesmo tempo Barata e Boa (Menor soma).</span>
        </div>
        """, unsafe_allow_html=True)


# --- ANIMAÇÃO MATRIX & JUNKING DATA ---
def run_real_scan_animation_and_clean(df_raw):
    terminal_placeholder = st.empty()
    real_tickers = df_raw['ticker'].dropna().unique().tolist()
    random.shuffle(real_tickers)
    
    # 1. ANIMAÇÃO DE CONEXÃO
    header1 = ">>> ESTABELECENDO CONEXÃO SEGURA COM O DATALAKE B3 <<<"
    for i in range(6):
        cursor = "_" if i % 2 == 0 else " "
        terminal_placeholder.markdown(f"""<div class="terminal-box"><span style='color:#fff; font-weight:bold; font-size:18px;'>{header1}</span><br><span style="color: #00ff41; font-size: 20px;">{cursor}</span></div>""", unsafe_allow_html=True)
        time.sleep(0.5)

    header2 = ">>> INICIANDO VARREDURA DE DADOS FINANCEIROS... <<<"
    log_history = []
    log_history.append(f"<span style='color:#fff; font-weight:bold; font-size:18px;'>{header1}</span>")
    log_history.append(f"<span style='color:#00ff41; font-weight:bold; font-size:20px;'>{header2}</span>")
    log_history.append("-" * 60)
    
    actions = ["DECRYPTING", "ACCESSING ROOT", "BYPASSING FIREWALL", "INJECTING SQL", "EXTRACTING"]
    count = 0
    for ticker in real_tickers:
        if ticker in EXCEL_DB:
            info = EXCEL_DB[ticker]
            display_str = f"{info['nome']} | {info['setor']}"
        else:
            display_str = "DATABASE ACESS..."
        action = random.choice(actions)
        log_line = f"> {action}: <span style='color:#fff; font-weight:bold; font-size:18px;'>[{ticker}] {display_str}</span> ... [OK]"
        log_history.append(log_line)
        if len(log_history) > 14: display_logs = log_history[-14:]
        else: display_logs = log_history
        formatted_logs = "<br>".join(display_logs)
        terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
        time.sleep(random.uniform(0.05, 0.2))
        count += 1
        if count >= 30: break
    
    time.sleep(0.5)
    
    # --- LIMPEZA REAL ---
    total_bruto = len(df_raw)
    
    if 'liquidezmediadiaria' in df_raw.columns:
        df_raw['liquidezmediadiaria'] = pd.to_numeric(df_raw['liquidezmediadiaria'], errors='coerce').fillna(0)
    if 'price' in df_raw.columns:
        df_raw['price'] = pd.to_numeric(df_raw['price'], errors='coerce').fillna(0)

    # Lógica de Limpeza
    frac_mask = df_raw['ticker'].astype(str).str.endswith('F')
    qtd_frac = frac_mask.sum()
    
    zombie_mask = (df_raw['liquidezmediadiaria'] <= 0)
    qtd_zombie = zombie_mask.sum()
    
    broken_mask = (df_raw['price'] <= 0)
    qtd_broken = broken_mask.sum()
    
    junk_mask = frac_mask | zombie_mask | broken_mask
    df_clean = df_raw[~junk_mask].copy()
    total_limpo = len(df_clean)
    
    header3 = ">>> INICIANDO PROTOCOLO DE LIMPEZA DE DADOS (DATA PURGE) <<<"
    log_history.append("<br>")
    log_history.append(f"<span style='color:#FFD700; font-weight:bold; font-size:20px;'>{header3}</span>")
    
    formatted_logs = "<br>".join(log_history[-14:])
    terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
    time.sleep(1.5)
    
    log_history.append(f"> TOTAL DE PACOTES BRUTOS BAIXADOS: <span style='color:#fff; font-weight:bold;'>{total_bruto}</span>")
    formatted_logs = "<br>".join(log_history[-14:])
    terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
    time.sleep(1.0)
    
    if qtd_frac > 0:
        log_history.append(f"> DETECTANDO FRACIONÁRIOS... <span style='color:red;'>REMOVED -{qtd_frac}</span>")
        formatted_logs = "<br>".join(log_history[-14:])
        terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
        time.sleep(0.8)
    
    log_history.append(f"> PURGING ATIVOS ZUMBIS (LIQUIDEZ ZERO)... <span style='color:red;'>REMOVED -{qtd_zombie}</span>")
    formatted_logs = "<br>".join(log_history[-14:])
    terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
    time.sleep(0.8)
    
    if qtd_broken > 0:
        log_history.append(f"> CORRIGINDO DADOS CORROMPIDOS (NULL PRICE)... <span style='color:red;'>REMOVED -{qtd_broken}</span>")
        formatted_logs = "<br>".join(log_history[-14:])
        terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
        time.sleep(0.8)
    
    log_history.append("<br>")
    log_history.append(f"> BASE DE DADOS CONSOLIDADA: <span style='color:#00ff41; font-weight:bold; font-size:22px;'>{total_limpo} ATIVOS VÁLIDOS</span>")
    formatted_logs = "<br>".join(log_history[-14:])
    terminal_placeholder.markdown(f"""<div class="terminal-box">{formatted_logs}<br><span style="color: #fff; animation: blink 0.2s infinite;">_</span></div>""", unsafe_allow_html=True)
    
    time.sleep(2.5)
    terminal_placeholder.empty()
    
    return df_clean, total_bruto, (total_bruto - total_limpo)

# --- MAIN ---
st.title("💀 MARKET HACKING_v24.0")
st.markdown("`> PROTOCOLO: DEEP VALUE` | `> ALVO: BOLSA DE VALORES`")
st.divider()

with st.container():
    c_btn, c_status = st.columns([1, 2])
    with c_btn:
        btn_label = "⚡ RE-INICIAR ATAQUE" if st.session_state['data_loaded'] else "⚡ INICIAR ATAQUE DE DADOS"
        if st.button(btn_label):
            status = st.empty()
            status.info("⏳ TENTANDO INVASÃO AUTOMÁTICA (STATUS INVEST)...")
            time.sleep(0.5)
            
            # --- TENTATIVA COM CLOUDSCRAPER ---
            df_raw = get_data_feed()
            
            if not df_raw.empty:
                status.success(">> CONEXÃO BEM SUCEDIDA!")
                time.sleep(1)
                status.empty()
                
                df_clean, raw, rem = run_real_scan_animation_and_clean(df_raw)
                
                st.session_state['market_data'] = df_clean
                st.session_state['stats_raw'] = raw
                st.session_state['stats_removed'] = rem
                st.session_state['data_loaded'] = True
                st.rerun()
            else:
                status.error("FALHA CRÍTICA: CLOUDFLARE BARROU A CONEXÃO (ERRO 403). TENTE MAIS TARDE.")

    with c_status:
        if st.session_state['data_loaded']:
            total = len(st.session_state['market_data'])
            raw = st.session_state['stats_raw']
            rem = st.session_state['stats_removed']
            st.success(f"RELATÓRIO: {raw} BAIXADOS ➔ {rem} ELIMINADOS (LIXO) ➔ {total} ATIVOS VÁLIDOS.")
        else:
            st.info("SISTEMA EM STANDBY. AGUARDANDO COMANDO.")

st.divider()

if st.session_state['data_loaded']:
    df = st.session_state['market_data']
    st.markdown("<h3 style='text-align: center; color: white;'>PARÂMETROS DA OPERAÇÃO</h3>", unsafe_allow_html=True)
    ic1, ic2, ic3, ic4 = st.columns([1, 2, 2, 1])
    with ic2:
        min_liquidez = st.number_input("Liquidez", value=200000, step=50000)
        st.markdown(f"<div class='value-feedback'>ACIMA DE: <span style='color:#00ff41; font-weight:bold;'>{format_brl(min_liquidez)}</span></div>", unsafe_allow_html=True)
    with ic3:
        val_invest = st.number_input("Investimento", value=0.0, step=100.0)
        val_display = format_brl(val_invest) if val_invest > 0 else "NÃO INFORMADO"
        st.markdown(f"<div class='value-feedback'>APORTE TOTAL: <span style='color:#FFD700; font-weight:bold;'>{val_display}</span></div>", unsafe_allow_html=True)

    bc1, bc2, bc3 = st.columns([1, 1, 1])
    with bc2:
        if st.button("💀 EXECUTAR VALORAÇÃO"): st.session_state['valuation_run'] = True

    if st.session_state['valuation_run']:
        cols_numeric = ['price', 'vpa', 'lpa', 'ev_ebit', 'roic', 'liquidezmediadiaria']
        for col in cols_numeric:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')

        df_valid = df.dropna(subset=cols_numeric)
        df_final = df_valid[df_valid['liquidezmediadiaria'] > min_liquidez].copy()

        st.markdown(f"### > RESULTADO: {len(df_final)} ATIVOS ENCONTRADOS")
        tab1, tab2 = st.tabs(["GRAHAM (PREÇO JUSTO)", "MAGIC FORMULA (QUALIDADE)"])

        def render_card_html(ticker, price, label1, val1_fmt, label2, val2_fmt, rank, investment_total=0):
            real_name = ""
            if ticker in EXCEL_DB:
                info = EXCEL_DB[ticker]
                real_name = f"{info['nome']} ({info['segmento']})"
            name_html = f"<div style='color:#888; font-size:12px; margin-bottom:5px;'>{real_name}</div>" if real_name else ""
            invest_html = ""
            if investment_total > 0:
                target_per_stock = investment_total / 10
                if price > 0:
                    qty = int(target_per_stock // price)
                    cost = qty * price
                    invest_html = f"<div class='buy-section'><div>ORDEM DE COMPRA SUGERIDA</div><div class='buy-value'>{qty} un. <span style='font-size:14px; color:#aaa;'>(Total: {format_brl(cost)})</span></div></div>"
                else: invest_html = "<div class='buy-section'>PREÇO INVÁLIDO</div>"
            return f"""<div class="hacker-card"><div><span class="card-ticker">#{rank} {ticker}</span><span class="card-price">{format_brl(price)}</span></div>{name_html}<div style="clear:both;"></div><div class="metric-row"><div><div class="metric-label">{label1}</div><div class="metric-value">{val1_fmt}</div></div><div style="text-align: right;"><div class="metric-label">{label2}</div><div class="metric-value">{val2_fmt}</div></div></div>{invest_html}</div>"""

        with tab1:
            st.markdown("""<div class="intel-box"><div class="intel-title">/// PROTOCOLO: BENJAMIN GRAHAM ///</div><div class="intel-math">VI = √(22.5 x LPA x VPA)</div><div class="intel-desc">*Busca empresas descontadas frente ao lucro e patrimônio.</div></div>""", unsafe_allow_html=True)
            if {'lpa', 'vpa', 'price'}.issubset(df_final.columns):
                df_g = df_final[(df_final['lpa'] > 0) & (df_final['vpa'] > 0)].copy()
                df_g['ValorJusto'] = np.sqrt(22.5 * df_g['lpa'] * df_g['vpa'])
                df_g['Margem'] = (df_g['ValorJusto'] / df_g['price']) - 1
                top_graham = df_g.sort_values('Margem', ascending=False).head(10)
                gc1, gc2 = st.columns(2)
                for i, row in top_graham.reset_index().iterrows():
                    html_card = render_card_html(row['ticker'], row['price'], "VALOR JUSTO", format_brl(row['ValorJusto']), "POTENCIAL", f"{row['Margem']:.1%}", i+1, val_invest)
                    with (gc1 if i % 2 == 0 else gc2):
                        st.markdown(html_card, unsafe_allow_html=True)
                        if st.button(f"📂 EXAMINAR CÁLCULO (DECODE) #{i+1}", key=f"btn_graham_{row['ticker']}"): show_graham_details(row['ticker'], row)

        with tab2:
            st.markdown("""<div class="intel-box"><div class="intel-title">/// PROTOCOLO: JOEL GREENBLATT ///</div><div class="intel-math">SCORE = RANK(EV/EBIT) + RANK(ROIC)</div><div class="intel-desc">*Combina empresas baratas (EV baixo) e rentáveis (ROIC alto).</div></div>""", unsafe_allow_html=True)
            if {'ev_ebit', 'roic'}.issubset(df_final.columns):
                df_m = df_final[(df_final['ev_ebit'] > 0) & (df_final['roic'] > 0) & (df_final['roic'] <= 5)].copy()
                if df_m['roic'].mean() > 50: df_m = df_m[df_m['roic'] <= 500] 
                df_m['R_EV'] = df_m['ev_ebit'].rank(ascending=True)
                df_m['R_ROIC'] = df_m['roic'].rank(ascending=False)
                df_m['Score'] = df_m['R_EV'] + df_m['R_ROIC']
                top_magic = df_m.sort_values('Score', ascending=True).head(10)
                mc1, mc2 = st.columns(2)
                for i, row in top_magic.reset_index().iterrows():
                    html_card = render_card_html(row['ticker'], row['price'], "EV/EBIT", f"{row['ev_ebit']:.2f}", "ROIC", f"{row['roic']:.1%}", i+1, val_invest)
                    with (mc1 if i % 2 == 0 else mc2):
                        st.markdown(html_card, unsafe_allow_html=True)
                        if st.button(f"📂 EXAMINAR CÁLCULO (DECODE) #{i+1}", key=f"btn_magic_{row['ticker']}"): show_magic_details(row['ticker'], row)