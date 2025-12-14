import streamlit as st
import pandas as pd
import requests
import io
import numpy as np
import time
import random
from datetime import datetime

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Market Hacking v2.15", page_icon="💀", layout="wide")

# --- CSS DE ALTO CONTRASTE & REMOÇÃO DE BRANDING ---
st.markdown("""
<style>
    /* Fundo e Fonte Hacker */
    .stApp { background-color: #000000; background-image: linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px); background-size: 30px 30px; color: #e0e0e0; }
    * { font-family: 'Consolas', 'Courier New', monospace !important; }
    h1, h2, h3 { color: #00ff41 !important; text-shadow: 0 0 10px rgba(0, 255, 65, 0.8); font-weight: 900 !important; text-transform: uppercase; }
    
    /* Inputs e Selectbox */
    div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] > div > div { color: #ffffff !important; background-color: #111 !important; border: 2px solid #00ff41 !important; font-size: 20px !important; font-weight: bold !important; }
    div[data-testid="stSelectbox"] label { color: #00ff41 !important; font-size: 18px !important; }
    
    /* Botões */
    .stButton>button { background-color: #000; color: #00ff41; border: 2px solid #00ff41; font-size: 18px !important; font-weight: bold; text-transform: uppercase; height: 50px; transition: 0.3s; box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); width: 100%; }
    .stButton>button:hover { background-color: #00ff41; color: #000; box-shadow: 0 0 25px #00ff41; transform: scale(1.02); }
    
    /* Cards Gerais */
    .hacker-card { background-color: #0e0e0e; border: 1px solid #333; border-top: 3px solid #00ff41; padding: 15px; margin-bottom: 5px; border-radius: 4px; position: relative; }
    
    /* CARDS DE DIAGNÓSTICO (MIRA LASER) */
    .diag-box-green { border: 4px solid #00ff41; background-color: #051a05; padding: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.2); margin-bottom: 20px; }
    .diag-box-red { border: 4px solid #ff0000; background-color: #1a0505; padding: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(255, 0, 0, 0.2); margin-bottom: 20px; }
    .diag-box-yellow { border: 4px solid #FFD700; background-color: #1a1a05; padding: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(255, 215, 0, 0.2); margin-bottom: 20px; }
    
    .diag-title { font-size: 28px; font-weight: 900; color: #fff; text-align: center; margin-bottom: 10px; border-bottom: 1px dashed #555; padding-bottom: 10px; }
    .diag-val { font-size: 22px; margin: 10px 0; }
    .diag-status-green { color: #00ff41; font-weight: bold; font-size: 24px; text-align: center; margin-top: 15px; text-transform: uppercase; }
    .diag-status-red { color: #ff0000; font-weight: bold; font-size: 24px; text-align: center; margin-top: 15px; text-transform: uppercase; }
    
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
    
    .terminal-box { background-color: #050505; border: 1px solid #00ff41; padding: 15px; font-size: 16px; color: #00ff41; margin-bottom: 20px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.1); font-family: 'Courier New', monospace; height: 350px; overflow-y: hidden; display: flex; flex-direction: column; justify-content: flex-end; }
    
    /* DISCLAIMER */
    .disclaimer { text-align: center; color: #555; font-size: 12px; margin-top: 50px; padding-top: 20px; border-top: 1px solid #222; }

    /* --- PROTOCOLO FANTASMA: REMOVENDO MARCAS --- */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} 
    div[data-testid="stToolbar"] {visibility: hidden;} div[data-testid="stDecoration"] {display: none;} div[data-testid="stStatusWidget"] {visibility: hidden;}
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

# --- LÓGICA DO SCAN ---
def run_scan_logic():
    terminal = st.empty()
    df_raw = get_data_direct()
    if df_raw.empty: return pd.DataFrame(), 0, 0
    
    total_bruto = len(df_raw)
    real_tickers = df_raw['ticker'].unique().tolist()
    random.shuffle(real_tickers)
    
    # Animação Rápida
    log = ["<span style='color:#fff'>CONECTANDO DATABASE FUNDAMENTUS...</span>", "<span style='color:#00ff41'>ACESSO CONCEDIDO.</span>", "-"*40]
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
    
    # CÁLCULOS GLOBAIS NA BASE LIMPA
    df_clean['ValorJusto'] = np.sqrt(22.5 * df_clean['lpa'] * df_clean['vpa']).fillna(0)
    df_clean['Margem'] = (df_clean['ValorJusto'] / df_clean['price']) - 1
    
    # Magic Formula (Rankings)
    df_magic = df_clean[(df_clean['ev_ebit'] > 0) & (df_clean['roic'] > 0)].copy()
    df_magic['R_EV'] = df_magic['ev_ebit'].rank(ascending=True)
    df_magic['R_ROIC'] = df_magic['roic'].rank(ascending=False)
    df_magic['Score'] = df_magic['R_EV'] + df_magic['R_ROIC']
    df_magic['MagicRank'] = df_magic['Score'].rank(ascending=True)
    
    # Merge de volta para o principal
    df_final = df_clean.merge(df_magic[['ticker', 'Score', 'MagicRank']], on='ticker', how='left')
    
    removed = total_bruto - len(df_final)
    
    terminal.markdown(f"""<div class="terminal-box"><br><br><span style='color:#00ff41;font-weight:bold;font-size:20px'> >>> INTRUSÃO CONCLUÍDA. {len(df_final)} ATIVOS VÁLIDOS NA MEMÓRIA.</span></div>""", unsafe_allow_html=True)
    time.sleep(1.5)
    terminal.empty()
    return df_final, total_bruto, removed

# --- MAIN UI ---
st.title("💀 MARKET HACKING v2.15")
st.markdown("`> PROTOCOLO: SNIPER` | `> FONTE: FUNDAMENTUS`")
st.divider()

# Botão Iniciar
if not st.session_state['data_loaded']:
    if st.button("⚡ INICIAR VARREDURA DE DADOS"):
        df, raw, rem = run_scan_logic()
        if not df.empty:
            st.session_state.update({'market_data': df, 'stats_raw': raw, 'stats_removed': rem, 'data_loaded': True})
            st.rerun()
        else: st.error("ERRO DE CONEXÃO.")
else:
    # --- ÁREA DE OPERAÇÃO PÓS-LOAD ---
    st.success(f"BASE CARREGADA: {len(st.session_state['market_data'])} ATIVOS PRONTOS.")

    # --- SNIPER (BUSCA INDIVIDUAL) ---
    st.markdown("### 🎯 MIRA LASER (DIAGNÓSTICO INDIVIDUAL)")
    c_search, c_act = st.columns([3, 1])
    
    df = st.session_state['market_data']
    all_tickers = sorted(df['ticker'].unique())
    
    with c_search:
        target = st.selectbox("DIGITE O CÓDIGO DO ATIVO:", options=all_tickers, index=None, placeholder="Ex: PETR4, VALE3...")
        st.session_state['target_ticker'] = target
        
    with c_act:
        st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
        if st.button("PROCESSAR ALVO"):
            st.session_state['processed_target'] = True

    # --- RESULTADO DA BUSCA ---
    if st.session_state['processed_target'] and st.session_state['target_ticker']:
        ticker = st.session_state['target_ticker']
        row = df[df['ticker'] == ticker].iloc[0]
        
        # Lógica de Cores
        preco = row['price']
        vi = row['ValorJusto']
        magic_rank = row['MagicRank']
        
        # Graham Logic
        if preco < vi: 
            graham_class = "diag-box-green"
            graham_status = "<div class='diag-status-green'>BARATO (OPORTUNIDADE)</div>"
        elif preco > vi * 1.1: # 10% de margem
            graham_class = "diag-box-red"
            graham_status = "<div class='diag-status-red'>CARO (AGUARDE)</div>"
        else:
            graham_class = "diag-box-yellow"
            graham_status = "<div style='color:#FFD700;text-align:center;font-weight:bold;font-size:24px;margin-top:15px'>PREÇO JUSTO</div>"

        # Magic Logic (Top 100 = Bom)
        if not pd.isna(magic_rank) and magic_rank <= 100:
            magic_icon = "✅"
            magic_text = "<span style='color:#00ff41'>MAGIC APROVADO</span>"
        else:
            magic_icon = "❌"
            magic_text = "<span style='color:#ff0000'>MAGIC REPROVADO</span>"
            if pd.isna(magic_rank): magic_rank = 999

        st.markdown("---")
        sc1, sc2 = st.columns(2)
        
        with sc1:
            st.markdown(f"""
            <div class="{graham_class}">
                <div class="diag-title">MÉTODO GRAHAM</div>
                <div class="diag-val">PREÇO ATUAL: <span style="color:#fff">{format_brl(preco)}</span></div>
                <div class="diag-val">VALOR JUSTO: <span style="color:#fff">{format_brl(vi)}</span></div>
                <div class="diag-val">MARGEM: <span style="color:#fff">{row['Margem']:.1%}</span></div>
                {graham_status}
            </div>
            """, unsafe_allow_html=True)
            
        with sc2:
            st.markdown(f"""
            <div class="hacker-card" style="padding: 30px; text-align: center; height: 100%; border: 2px dashed #444;">
                <div class="diag-title">FORMULA MÁGICA</div>
                <div style="font-size: 60px; margin: 20px 0;">{magic_icon}</div>
                <div style="font-size: 24px; font-weight:bold;">{magic_text}</div>
                <div style="margin-top:15px; color:#888;">POSIÇÃO NO RANKING: #{int(magic_rank)}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("---")

    # --- ÁREA DE DOWNLOAD ---
    st.markdown("### 💾 EXPORTAÇÃO DE DADOS")
    
    # Preparar Excel Limpo
    df_export = df.copy()
    if 'ticker' in EXCEL_DB: # Adicionar nomes se possível
        df_export['Nome_Empresa'] = df_export['ticker'].apply(lambda x: EXCEL_DB.get(x, {}).get('nome', 'N/A'))
    
    # Selecionar colunas bonitas
    cols_export = ['ticker', 'price', 'ValorJusto', 'Margem', 'ev_ebit', 'roic', 'MagicRank', 'liquidezmediadiaria']
    df_export = df_export[cols_export]
    df_export.columns = ['ATIVO', 'PRECO_ATUAL', 'VALOR_JUSTO_GRAHAM', 'POTENCIAL_%', 'EV_EBIT', 'ROIC', 'POSICAO_MAGIC', 'LIQUIDEZ']
    df_export['DATA_CAPTURA'] = datetime.now().strftime("%d/%m/%Y")
    
    # Converter para Excel na memória
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Analise_Hacker')
    
    st.download_button(
        label="📥 DOWNLOAD LISTA COMPLETA (.XLSX)",
        data=buffer.getvalue(),
        file_name=f"RELATORIO_HACKER_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- DISCLAIMER ---
    st.markdown("""
    <div class="disclaimer">
        ⚠️ AVISO LEGAL: ESTA FERRAMENTA É APENAS PARA FINS EDUCACIONAIS E DE CÁLCULO AUTOMATIZADO.<br>
        OS DADOS SÃO OBTIDOS DE FONTES PÚBLICAS E PODEM CONTER ATRASOS.<br>
        ISTO NÃO É UMA RECOMENDAÇÃO DE COMPRA OU VENDA DE ATIVOS. USE COM RESPONSABILIDADE.
    </div>
    """, unsafe_allow_html=True)
