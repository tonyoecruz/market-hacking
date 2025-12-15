import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random
from datetime import datetime

# --- CONFIGURAÇÃO INICIAL (Versão na Aba do Navegador) ---
st.set_page_config(page_title="SCOPE3 v2.24", page_icon="logo.jpeg", layout="wide")

# ==============================================================================
# 🍎 ÁREA DE TRANSFORMAÇÃO EM APP IPHONE (PWA)
# Link direto do SEU GitHub Público
URL_DO_ICONE = "https://raw.githubusercontent.com/tonyoecruz/market-hacking/main/logo.jpeg"
# ==============================================================================

# --- CSS E METADADOS DO IPHONE ---
st.markdown(f"""
<head>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SCOPE3">
    <link rel="apple-touch-icon" href="{URL_DO_ICONE}">
</head>
<style>
    /* ================= ESTILO GERAL (BASE DESKTOP) ================= */
    .stApp {{ background-color: #000000; background-image: linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px); background-size: 30px 30px; color: #e0e0e0; }}
    * {{ font-family: 'Consolas', 'Courier New', monospace !important; }}
    h1, h2, h3 {{ color: #00ff41 !important; text-shadow: 0 0 10px rgba(0, 255, 65, 0.8); font-weight: 900 !important; text-transform: uppercase; }}
    
    /* Inputs */
    div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] > div > div {{ color: #ffffff !important; background-color: #111 !important; border: 2px solid #00ff41 !important; font-size: 20px !important; font-weight: bold !important; }}
    div[data-testid="stSelectbox"] label {{ color: #00ff41 !important; font-size: 18px !important; }}
    
    /* Botões */
    .stButton>button {{ background-color: #000; color: #00ff41; border: 2px solid #00ff41; font-size: 18px !important; font-weight: bold; text-transform: uppercase; height: 50px; transition: 0.3s; box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); width: 100%; }}
    .stButton>button:hover {{ background-color: #00ff41; color: #000; box-shadow: 0 0 25px #00ff41; transform: scale(1.02); }}
    
    /* Cards Gerais */
    .hacker-card {{ background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 5px; border-radius: 4px; position: relative; }}
    
    /* MIRA LASER (DESKTOP) - Altura Fixa para alinhar lado a lado */
    .diag-box {{ height: 340px; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 20px; padding: 20px; border-radius: 10px; }}
    
    /* Cores das Caixas */
    .diag-green {{ border: 4px solid #00ff41; background-color: #051a05; box-shadow: 0 0 20px rgba(0, 255, 65, 0.2); }}
    .diag-red {{ border: 4px solid #ff0000; background-color: #1a0505; box-shadow: 0 0 20px rgba(255, 0, 0, 0.2); }}
    .diag-yellow {{ border: 4px solid #FFD700; background-color: #1a1a05; box-shadow: 0 0 20px rgba(255, 215, 0, 0.2); }}
    .diag-neutral {{ border: 2px dashed #444; background-color: #0e0e0e; }}
    
    /* Textos do Diagnóstico */
    .diag-title {{ font-size: 24px; font-weight: 900; color: #fff; text-align: center; border-bottom: 1px dashed #555; padding-bottom: 10px; margin-bottom: 10px;}}
    .diag-val {{ font-size: 20px; margin: 5px 0; }}
    .diag-status {{ font-weight: bold; font-size: 22px; text-align: center; text-transform: uppercase; margin-top: auto; padding-top: 10px;}}

    /* Terminal */
    .terminal-box {{ background-color: #050505; border: 1px solid #00ff41; padding: 15px; font-size: 16px; color: #00ff41; margin-bottom: 20px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.1); font-family: 'Courier New', monospace; height: 350px; overflow-y: hidden; display: flex; flex-direction: column; justify-content: flex-end; }}

    /* Modal - Padrão Desktop */
    div[role="dialog"] {{ width: 85vw !important; max-width: 90vw !important; }}
    
    /* Ajuste fino para alinhar texto e logo no topo */
    .header-text {{ display: flex; flex-direction: column; justify-content: center; height: 100%; }}

    /* ================= INTEELIGÊNCIA MOBILE (O PULO DO GATO) ================= */
    @media only screen and (max-width: 768px) {{
        /* 1. Ajuste de Fontes Gigantes */
        h1 {{ font-size: 32px !important; }}
        h2, h3 {{ font-size: 22px !important; }}
        /* 2. Ajuste dos Inputs */
        div[data-testid="stNumberInput"] input {{ font-size: 18px !important; height: 50px !important; }}
        /* 3. Ajuste das Caixas de Diagnóstico */
        .diag-box {{ height: auto !important; min-height: 250px; margin-bottom: 15px; }}
        .diag-title {{ font-size: 20px !important; }}
        .diag-val {{ font-size: 16px !important; }}
        .diag-status {{ font-size: 18px !important; margin-top: 15px; }}
        /* 4. Ajuste dos Modais */
        div[role="dialog"] {{ width: 95vw !important; max-width: 98vw !important; margin: 0 auto; }}
        .modal-header {{ font-size: 20px !important; }}
        .modal-math {{ font-size: 18px !important; padding: 15px !important; }}
        .modal-text {{ font-size: 14px !important; }}
        /* 5. Terminal menor no celular */
        .terminal-box {{ height: 250px !important; font-size: 12px !important; }}
        /* 6. Cards da Lista */
        .card-ticker {{ font-size: 20px !important; }}
        .card-price {{ font-size: 22px !important; }}
        .metric-value {{ font-size: 16px !important; }}
    }}

    /* --- PROTOCOLO FANTASMA (Remover marcas) --- */
    #MainMenu, footer, header, div[data-testid="stToolbar"], div[data-testid="stDecoration"], div[data-testid="stStatusWidget"] {{visibility: hidden; display: none;}}
    .disclaimer {{ text-align: center; color: #555; font-size: 12px; margin-top: 50px; padding-top: 20px; border-top: 1px solid #222; }}
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
if 'stats_raw' not in st.session_state: st.session_state['stats_raw'] = 0
if 'stats_removed' not in st.session_state: st.session_state['stats_removed'] = 0
if 'target_ticker' not in st.session_state: st.session_state['target_ticker'] = None
if 'processed_target' not in st.session_state: st.session_state['processed_target'] = False
if 'valuation_run' not in st.session_state: st.session_state['valuation_run'] = False

# --- EXTRAÇÃO DIRETA ---
@st.cache_data(show_spinner=False)
def get_data_direct():
    url = 'https://www.fundamentus.com.br/resultado.php'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
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

# --- MODAIS DETALHADOS ---
@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_graham_details(ticker, row):
    lpa = row['lpa']; vpa = row['vpa']; vi = row['ValorJusto']
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">FÓRMULA APLICADA</div><div class="modal-math">VI = √(22.5 × LPA × VPA)<br>VI = √(22.5 × {lpa:.2f} × {vpa:.2f})<br>VI = <span class="highlight-val">{format_brl(vi)}</span></div><div style="text-align:center;color:#000;font-size:20px;margin-top:20px;">PREÇO: <b>{format_brl(row['price'])}</b> | POTENCIAL: <b style="color:#008000">{row['Margem']:.1%}</b></div>""", unsafe_allow_html=True)
    with c2: 
        st.markdown("""
        <div class="modal-subtitle">GLOSSÁRIO TÉCNICO</div>
        <div class="modal-text">
            <b>1. VI (Valor Intrínseco):</b> O "Preço Justo" teórico segundo Graham.
            <br><b>2. LPA (Lucro/Ação):</b> Quanto a empresa lucra por papel.
            <br><b>3. VPA (Valor/Ação):</b> Quanto vale o patrimônio físico por papel.
            <br><b>4. Constante 22.5:</b> O teto de Graham (P/L x P/VP máximos).
            <br><b>5. Margem (Potencial):</b> Diferença entre o Preço de Tela e o Valor Justo. Positivo = Desconto.
        </div>
        """, unsafe_allow_html=True)

@st.dialog("📂 DOSSIÊ DO ATIVO")
def show_magic_details(ticker, row):
    ev = row.get('ev_ebit', 0); roic = row.get('roic', 0)
    rev = int(row.get('R_EV', 0)); rroic = int(row.get('R_ROIC', 0)); sc = int(row.get('Score', 0))
    
    st.markdown(f'<div class="modal-header">ANÁLISE DE CÁLCULO: {ticker}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: st.markdown(f"""<div class="modal-subtitle">MODELO GREENBLATT</div><div class="modal-math">SCORE = RANK(EV) + RANK(ROIC)<br>SCORE = #{rev} + #{rroic}<br>TOTAL = <span class="highlight-score">{sc}</span></div>""", unsafe_allow_html=True)
    with c2: 
        st.markdown(f"""
        <div class="modal-subtitle">ENTENDENDO A PONTUAÇÃO</div>
        <div class="modal-text">
            <b>1. EV/EBIT (Preço):</b> Mede se a empresa está barata. (Você é a #{rev}ª mais barata da bolsa).
            <br><b>2. ROIC (Qualidade):</b> Mede a eficiência. (Você é a #{rroic}ª mais eficiente da bolsa).
            <br><b>3. Score (Soma):</b> A soma das duas posições.
            <br><b>4. Lógica:</b> Na Fórmula Mágica, <u>quanto MENOR a pontuação, MELHOR</u>. O objetivo é comprar empresas boas por preços baixos.
        </div>
        """, unsafe_allow_html=True)

# --- LÓGICA DO SCAN ---
def run_scan_logic():
    terminal = st.empty()
    df_raw = get_data_direct()
    if df_raw.empty: return pd.DataFrame(), 0, 0
    
    total_bruto = len(df_raw)
    real_tickers = df_raw['ticker'].unique().tolist()
    random.shuffle(real_tickers)
    
    # Animação Rápida
    log = ["<span style='color:#fff'>CONECTANDO DATABASE SEGURO...</span>", "<span style='color:#00ff41'>ACESSO CONCEDIDO.</span>", "-"*40]
    for i in range(8):
        t = random.choice(real_tickers) if real_tickers else "..."
        log.append(f"> EXTRAINDO: {t} ... [OK]")
        terminal.markdown(f"""<div class="terminal-box">{"<br>".join(log[-10:])}<br><span style="color:#fff;animation:blink 0.2s infinite">_</span></div>""", unsafe_allow_html=True)
        time.sleep(0.05)
    
    # Limpeza
    mask_zombie = (df_raw['liquidezmediadiaria'] <= 0) | (df_raw['price'] <= 0)
    mask_frac = df_raw['ticker'].astype(str).str.endswith('F')
    mask_bdr = df_raw['ticker'].astype(str).str.contains(r'(32|33|34|35)$', regex=True)
    df_clean = df_raw[~(mask_zombie | mask_frac | mask_bdr)].copy()
    
    # CÁLCULOS GLOBAIS
    df_clean['ValorJusto'] = np.sqrt(22.5 * df_clean['lpa'] * df_clean['vpa']).fillna(0)
    df_clean['Margem'] = (df_clean['ValorJusto'] / df_clean['price']) - 1
    
    df_magic = df_clean[(df_clean['ev_ebit'] > 0) & (df_clean['roic'] > 0)].copy()
    df_magic['R_EV'] = df_magic['ev_ebit'].rank(ascending=True)
    df_magic['R_ROIC'] = df_magic['roic'].rank(ascending=False)
    df_magic['Score'] = df_magic['R_EV'] + df_magic['R_ROIC']
    df_magic['MagicRank'] = df_magic['Score'].rank(ascending=True)
    
    df_final = df_clean.merge(df_magic[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
    df_final['Score'] = df_final['Score'].fillna(0)
    
    removed = total_bruto - len(df_final)
    
    terminal.markdown(f"""<div class="terminal-box"><br><br><span style='color:#00ff41;font-weight:bold;font-size:20px'> >>> INTRUSÃO CONCLUÍDA. {len(df_final)} ATIVOS VÁLIDOS NA MEMÓRIA.</span></div>""", unsafe_allow_html=True)
    time.sleep(1.5)
    terminal.empty()
    return df_final, total_bruto, removed

# --- MAIN UI (INTERFACE HEADER COMPACTO) ---
# Coluna 1 (Pequena): Logo | Coluna 2 (Grande): Texto
c_head_logo, c_head_text = st.columns([1, 8])

with c_head_logo:
    # width=70 é pequeno e discreto, canto esquerdo
    st.image("logo.jpeg", width=70)

with c_head_text:
    # Texto alinhado ao lado da logo - AGORA COM A VERSÃO v2.24
    st.markdown("""
    <div class='header-text'>
        <h2 style='color: #00ff41; margin: 0; padding: 0; line-height: 1.2;'>SCOPE3</h2>
        <span style='color: #888; font-weight: bold; font-size: 14px;'>PROTOCOLO: SNIPER & SCAN | v2.24</span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

if not st.session_state['data_loaded']:
    if st.button("⚡ INICIAR VARREDURA DE DADOS"):
        df, raw, rem = run_scan_logic()
        if not df.empty:
            st.session_state.update({'market_data': df, 'stats_raw': raw, 'stats_removed': rem, 'data_loaded': True})
            st.rerun()
        else: st.error("ERRO DE CONEXÃO.")
else:
    st.success(f"BASE CARREGADA: {len(st.session_state['market_data'])} ATIVOS PRONTOS.")
    
    # ================= SNIPER (MIRA LASER) =================
    st.markdown("### 🎯 MIRA LASER (DIAGNÓSTICO)")
    c_search, c_act = st.columns([3, 1])
    df = st.session_state['market_data']
    
    with c_search:
        target = st.selectbox("DIGITE O CÓDIGO DO ATIVO:", options=sorted(df['ticker'].unique()), index=None, placeholder="Ex: PETR4, VALE3...")
        st.session_state['target_ticker'] = target
        
    with c_act:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("PROCESSAR ALVO"):
            st.session_state['processed_target'] = True

    if st.session_state['processed_target'] and st.session_state['target_ticker']:
        ticker = st.session_state['target_ticker']
        row = df[df['ticker'] == ticker].iloc[0]
        preco = row['price']; vi = row['ValorJusto']; magic_rank = row['MagicRank']
        
        # Lógica Graham
        if preco < vi: 
            g_cls = "diag-green"; g_stat = "<span style='color:#00ff41'>BARATO (OPORTUNIDADE)</span>"
        elif preco > vi * 1.1: 
            g_cls = "diag-red"; g_stat = "<span style='color:#ff0000'>CARO (AGUARDE)</span>"
        else:
            g_cls = "diag-yellow"; g_stat = "<span style='color:#FFD700'>PREÇO JUSTO</span>"

        # Lógica Magic
        if not pd.isna(magic_rank) and magic_rank <= 100:
            m_icon = "✅"; m_stat = "<span style='color:#00ff41'>MAGIC APROVADO</span>"
        else:
            m_icon = "❌"; m_stat = "<span style='color:#ff0000'>MAGIC REPROVADO</span>"
            if pd.isna(magic_rank): magic_rank = 999

        st.markdown("---")
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown(f"""
            <div class="diag-box {g_cls}">
                <div class="diag-title">MÉTODO GRAHAM</div>
                <div class="diag-val">PREÇO: <span style="color:#fff">{format_brl(preco)}</span></div>
                <div class="diag-val">JUSTO: <span style="color:#fff">{format_brl(vi)}</span></div>
                <div class="diag-val">MARGEM: <span style="color:#fff">{row['Margem']:.1%}</span></div>
                <div class="diag-status">{g_stat}</div>
            </div>
            """, unsafe_allow_html=True)
        with sc2:
            st.markdown(f"""
            <div class="diag-box diag-neutral">
                <div class="diag-title">FORMULA MÁGICA</div>
                <div style="font-size: 50px; text-align:center; margin: 10px 0;">{m_icon}</div>
                <div class="diag-status" style="margin-top:0;">{m_stat}</div>
                <div style="text-align:center; margin-top:15px; color:#888;">RANKING ATUAL: #{int(magic_rank)}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ================= LISTAGEM GLOBAL =================
    st.markdown("<h3 style='text-align:center'>PARÂMETROS GLOBAIS</h3>", unsafe_allow_html=True)
    ic1, ic2, ic3, ic4 = st.columns([1, 2, 2, 1])
    with ic2:
        min_liq = st.number_input("Liquidez Min", value=200000, step=50000)
    with ic3:
        invest = st.number_input("Investimento", value=0.0, step=100.0)

    st.markdown("<br>", unsafe_allow_html=True)
    cb1, cb2, cb3 = st.columns([1, 1, 1])
    with cb2:
        if st.button("💀 EXECUTAR VALORAÇÃO GLOBAL"):
            st.session_state['valuation_run'] = True

    if st.session_state['valuation_run']:
        # Filtro de Liquidez
        df_fin = df[df['liquidezmediadiaria'] > min_liq].copy()
        
        st.markdown(f"### > RESULTADO: {len(df_fin)} ATIVOS")
        t1, t2 = st.tabs(["GRAHAM (PREÇO JUSTO)", "MAGIC FORMULA (QUALIDADE)"])
        
        def card(t, p, l1, v1, l2, v2, r, inv=0):
            nm = f"{EXCEL_DB[t]['nome']} ({EXCEL_DB[t]['segmento']})" if t in EXCEL_DB else ""
            buy = ""
            if inv > 0 and p > 0:
                q = int((invest/10)//p); c = q*p
                buy = f"<div class='buy-section'>COMPRA: <span class='buy-value'>{q} un. ({format_brl(c)})</span></div>"
            return f"""<div class="hacker-card"><div><span class="card-ticker">#{r} {t}</span><span class="card-price">{format_brl(p)}</span></div><div style='color:#888;font-size:12px'>{nm}</div><div class="metric-row"><div><div class="metric-label">{l1}</div><div class="metric-value">{v1}</div></div><div style="text-align:right"><div class="metric-label">{l2}</div><div class="metric-value">{v2}</div></div></div>{buy}</div>"""

        # ABA GRAHAM
        with t1:
            df_g = df_fin[(df_fin['lpa']>0)&(df_fin['vpa']>0)].copy()
            top_graham = df_g.sort_values('Margem', ascending=False).head(10)
            gc1, gc2 = st.columns(2)
            for i, r in top_graham.reset_index().iterrows():
                html = card(r['ticker'], r['price'], "VALOR JUSTO", format_brl(r['ValorJusto']), "POTENCIAL", f"{r['Margem']:.1%}", i+1, invest)
                with (gc1 if i % 2 == 0 else gc2):
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"g_{r['ticker']}"): show_graham_details(r['ticker'], r)

        # ABA MAGIC
        with t2:
            df_m = df_fin.dropna(subset=['MagicRank']).sort_values('MagicRank', ascending=True).head(10)
            mc1, mc2 = st.columns(2)
            for i, r in df_m.reset_index().iterrows():
                html = card(r['ticker'], r['price'], "EV/EBIT", f"{r['ev_ebit']:.2f}", "ROIC", f"{r['roic']:.1%}", i+1, invest)
                with (mc1 if i % 2 == 0 else mc2):
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button(f"📂 DECODE #{i+1}", key=f"m_{r['ticker']}"): show_magic_details(r['ticker'], r)

    # --- DOWNLOAD ---
    st.markdown("---")
    st.markdown("### 💾 EXPORTAÇÃO")
    df_export = df.copy()
    if 'ticker' in EXCEL_DB:
        df_export['Nome_Empresa'] = df_export['ticker'].apply(lambda x: EXCEL_DB.get(x, {}).get('nome', 'N/A'))
    
    cols = ['ticker', 'price', 'ValorJusto', 'Margem', 'ev_ebit', 'roic', 'MagicRank', 'liquidezmediadiaria']
    df_export = df_export[cols]
    df_export.columns = ['ATIVO', 'PRECO_ATUAL', 'VALOR_JUSTO', 'POTENCIAL', 'EV_EBIT', 'ROIC', 'RANK_MAGIC', 'LIQUIDEZ']
    df_export['DATA'] = datetime.now().strftime("%d/%m/%Y")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False)
    
    st.download_button("📥 DOWNLOAD LISTA COMPLETA (.XLSX)", data=buffer.getvalue(), file_name=f"RELATORIO_HACKER_{datetime.now().strftime('%Y%m%d')}.xlsx")

# --- DISCLAIMER (SEMPRE VISÍVEL) ---
st.markdown("""
<div class="disclaimer">
    ⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO.<br>
    OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS.<br>
    ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. USE COM RESPONSABILIDADE.
</div>
""", unsafe_allow_html=True)
