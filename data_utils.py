"""
Utilitários compartilhados para o Market Hacking App
Contém funções auxiliares para análise IA, formatação, carregamento de dados, etc.
"""

import pandas as pd
import numpy as np
import requests
import io
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
import edge_tts
import asyncio
import tempfile
import hashlib
import random
import threading

# ==============================================================================
# CONFIGURAÇÃO DA IA
# ==============================================================================

# Configurar API Key
API_KEY = os.getenv("GEMINI_KEY", "")
if not API_KEY:
    try:
        import streamlit as st
        if "GEMINI_KEY" in st.secrets:
            API_KEY = st.secrets["GEMINI_KEY"]
    except:
        pass

ACTIVE_MODEL_NAME = None
IA_AVAILABLE = False

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except:
            pass

        if available_models:
            # PRIORIDADE: GEMINI 1.5 PRO
            if 'models/gemini-1.5-pro' in available_models:
                ACTIVE_MODEL_NAME = 'gemini-1.5-pro'
            elif 'models/gemini-1.5-flash' in available_models:
                ACTIVE_MODEL_NAME = 'gemini-1.5-flash'
            elif 'models/gemini-pro' in available_models:
                ACTIVE_MODEL_NAME = 'gemini-pro'
            else:
                ACTIVE_MODEL_NAME = available_models[0].replace('models/', '')
            
            model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
            IA_AVAILABLE = True
        else:
            ACTIVE_MODEL_NAME = 'gemini-1.5-flash'
            model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
            IA_AVAILABLE = True
    except:
        IA_AVAILABLE = False

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# ==============================================================================
# CONSTANTES
# ==============================================================================

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

RISKY_TICKERS = [
    'AMER3', 'OIBR3', 'OIBR4', 'LIGT3', 'GOLL4', 'RCLA3', 'VIIA3', 'BHIA3', 
    'RCSL3', 'RCSL4', 'TCNO3', 'TCNO4'
]

# ==============================================================================
# FUNÇÕES DE FORMATAÇÃO
# ==============================================================================

def format_brl(value):
    """Formata valor para moeda brasileira"""
    if pd.isna(value):
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def is_likely_etf(ticker):
    """Verifica se o ticker é um ETF conhecido"""
    t = ticker.upper().strip()
    return t in KNOWN_ETFS

# ==============================================================================
# FUNÇÕES DE RISCO
# ==============================================================================

def check_risk(row):
    """
    Verifica se uma ação é de alto risco
    Returns: (True, Risk_Message) if risky, else (False, None)
    """
    ticker = row['ticker'].upper().strip()
    
    # 1. Blacklist Check
    if ticker in RISKY_TICKERS:
        return True, "RECUPERAÇÃO JUDICIAL / ALTO RISCO"
    
    # 2. Debt Check (Massive Debt)
    if 'div_pat' in row and row['div_pat'] > 5.0:
        return True, f"DÍVIDA MASSIVA ({row['div_pat']:.1f}x PL)"
        
    return False, None

def filter_risky_stocks(df):
    """Remove ações de risco do DataFrame"""
    if df.empty:
        return df
    
    safe_indices = [i for i, row in df.iterrows() if not check_risk(row)[0]]
    return df.loc[safe_indices]

# ==============================================================================
# FUNÇÕES DE ANÁLISE IA
# ==============================================================================

def get_ai_generic_analysis(prompt):
    """Análise genérica com IA"""
    if not IA_AVAILABLE:
        return "⚠️ IA INDISPONÍVEL"
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e:
        return f"⚠️ ERRO DE GERAÇÃO: {str(e)}"

def get_graham_analysis(ticker, price, fair_value, lpa, vpa):
    """Análise Graham com IA"""
    margin = (fair_value/price) - 1 if price > 0 else 0
    
    if margin <= 0:
        focus_instruction = f"O ativo REPROVOU no Método Graham (Preço {format_brl(price)} > Justo {format_brl(fair_value)}). EXPLIQUE O MOTIVO: O mercado está pagando ágio por crescimento (Qualidade Premium)? Ou é uma bolha/supervalorização? Seja crítico."
    else:
        focus_instruction = "O ativo tem Margem de Segurança. Investigue: É uma oportunidade real ou 'Value Trap' (Barato que sai caro)? Cite riscos"
    
    extra_instruction = "Cite DATAS de eventos críticos (Ex: Início RJ, Fraude) se houver."

    prompt = f"""
    Atue como um Analista Sênior de Value Investing (Estilo Benjamin Graham).
    ALVO: {ticker}
    DADOS: Preço Atual R${price:.2f} | Preço Justo R${fair_value:.2f} | Margem: {margin:.1%}.
    
    Seu Trabalho:
    1. Breve resumo do Business.
    2. {focus_instruction}
    3. {extra_instruction}
    4. Conclusão: O prêmio/desconto se justifica?
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação", "Compra" ou "Venda".
    - Use termos como "Atrativo", "Descontado", "Arriscado", "Ágio por Qualidade".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Análise de Fundamentos, Fatos Relevantes (CVM) e RI da {ticker}."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_magic_analysis(ticker, ev_ebit, roic, score):
    """Análise Magic Formula com IA"""
    is_good = (roic > 0.15) and (ev_ebit > 0)
    
    if not is_good:
        focus_instruction = "O ativo NÃO SE DESTACA na Magic Formula. Explique: O ROIC é baixo (Ineficiência)? O EV/EBIT é alto (Caro)? Justifique se é um momento ruim do ciclo ou perda de fundamento."
    else:
        focus_instruction = "O ativo brilha na Magic Formula (Barato e Bom). Valide: O lucro é recorrente ou houve um 'não-recorrente' inflando os números?"

    prompt = f"""
    Atue como um Gestor de Fundo Quantitativo (Estilo Joel Greenblatt).
    ALVO: {ticker}
    DADOS: EV/EBIT {ev_ebit:.2f} (Quanto menor, mais barata) | ROIC {roic:.1%} (Quanto maior, mais qualidade).
    
    Análise Profunda:
    1. {focus_instruction}
    2. Qualidade vs Preço: A assimetria é favorável?
    3. Cite eventos recentes se relevante.
    
    REGRAS DE COMPLIANCE:
    - NUNCA use a palavra "Recomendação".
    - RODAPÉ OBRIGATÓRIO: "Fontes: Dados Financeiros Padronizados e RI da {ticker}."
    - Max 7 linhas.
    """
    return get_ai_generic_analysis(prompt)

def get_mix_analysis(ticker, price, fair_value, ev_ebit, roic):
    """Análise Elite Mix com IA"""
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

def get_sniper_analysis(ticker, price, fair_value, details, graham_ok, magic_ok):
    """Análise Sniper (Decode) com IA"""
    method_context = ""
    if not graham_ok:
        method_context += f"- FALHOU no Método Graham (Preço > Valor Justo). Explique: É prêmio de qualidade ou bolha?\n"
    if not magic_ok:
        method_context += f"- FALHOU/FRACA na Magic Formula. Explique: Problema de eficiência (ROIC) ou Preço?\n"
    
    prompt = f"""
    RELATÓRIO DE INTELIGÊNCIA TÁTICA: {ticker} ({details.get('Empresa', 'N/A')}).
    Setor: {details.get('Setor', 'N/A')}.
    
    CONTEXTO DOS MÉTODOS:
    {method_context}
    
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
    """Análise FII com IA"""
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
    """Análise de batalha entre dois ativos"""
    prompt = f"""
    COMPARATIVO DE BATALHA:
    1. {t1}: {d1}
    2. {t2}: {d2}
    
    Qual vence nos fundamentos?
    
    REGRA DE NARRAÇÃO:
    Comece EXATAMENTE com a frase: "E QUEM GANHOOOOU ESSA BATALHA FOI O ATIVO [NOME_DO_VENCEDOR]!" (Substitua [NOME_DO_VENCEDOR] pelo código real, ex: VALE3).
    
    Em seguida, faça uma ANÁLISE COMPARATIVA PROFUNDA para justificar a vitória:
    1. Compare Margens (Quem é mais eficiente?).
    2. Compare Endividamento (Quem é mais segura?).
    3. Compare Valor (Quem está mais barata no P/L e EV/EBIT?).
    4. Conclusão: Por que a vencedora é superior no Longo Prazo?
    
    Seja vibrante mas tecnicamente rigoroso. Max 8 linhas.
    """
    return get_ai_generic_analysis(prompt)

# ==============================================================================
# FUNÇÕES DE ÁUDIO (TTS)
# ==============================================================================

def generate_audio(text, key_suffix=""):
    """Gera áudio TTS usando edge-tts"""
    import hashlib
    import random
    
    # Customization for Battle Arena
    is_battle = "battle" in key_suffix
    
    # 1. Select Voice
    if is_battle:
        voice = "pt-BR-FranciscaNeural"
    else:
        voice = "pt-BR-AntonioNeural"

    # 2. Dynamic Intro (Only for Battle)
    final_text_content = text
    if is_battle:
        comm_intros = [
            "Respeitável público! O ringue pegou fogo hoje! Rufem os tambores para o resultado!",
            "Senhoras e senhores! Em uma disputa brutal de fundamentos, apenas um sobreviveu! A hora da verdade chegou!",
            "Extra! Extra! O combate acabou e a poeira baixou! Quem levou a melhor nos números? Vamos descobrir agora!",
            "Atenção investidores! Tivemos um duelo de titãs, mas a matemática é soberana! Ouçam o veredito do árbitro!",
            "Preparem seus corações! A análise foi profunda e o resultado é surpreendente! Quem será o campeão?"
        ]
        intro = random.choice(comm_intros)
        final_text_content = f"{intro} ... {text}"

    # Generate unique path
    h = hashlib.md5(final_text_content.encode()).hexdigest()
    temp_dir = tempfile.gettempdir()
    fname = os.path.join(temp_dir, f"tts_{h}_{key_suffix}.mp3")
    
    # If file already exists, use it
    if os.path.exists(fname):
        return fname
    
    async def _gen():
        # Clean text for TTS
        clean_text = final_text_content.replace("*", "").replace(" RJ ", " Recuperação Judicial ").replace("RJ ", "Recuperação Judicial ").replace(" R.J. ", " Recuperação Judicial ")
        comm = edge_tts.Communicate(clean_text, voice)
        await comm.save(fname)
        return fname
        
    try:
        result_container = {"error": None}

        def runner():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_gen())
                loop.close()
            except Exception as e:
                result_container["error"] = str(e)

        t = threading.Thread(target=runner)
        t.start()
        t.join()

        if result_container["error"]:
            raise Exception(result_container["error"])
              
        if os.path.exists(fname) and os.path.getsize(fname) > 0:
            return fname
        else:
            return None
            
    except Exception as e:
        return f"ERROR: {e}"
          
    return None

# ==============================================================================
# FUNÇÕES DE DADOS
# ==============================================================================

def get_stock_details(ticker):
    """Busca detalhes de uma ação no Fundamentus"""
    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        df_list = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')
        info = {}
        for df in df_list:
            for i in range(len(df)):
                row = df.iloc[i].astype(str).values
                for j in range(0, len(row), 2):
                    key = row[j].replace('?', '').strip()
                    val = row[j+1].strip()
                    if "Empresa" in key:
                        info['Empresa'] = val
                    if "Setor" in key:
                        info['Setor'] = val
                    if "Subsetor" in key:
                        info['Segmento'] = val
        return info
    except:
        return {'Empresa': ticker}

def get_data_acoes():
    """Busca dados de ações brasileiras do Fundamentus"""
    try:
        url = 'https://www.fundamentus.com.br/resultado.php'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        
        rename = {
            'Papel': 'ticker',
            'Cotação': 'price',
            'P/L': 'pl',
            'P/VP': 'pvp',
            'EV/EBIT': 'ev_ebit',
            'ROIC': 'roic',
            'Liq.2meses': 'liquidezmediadiaria',
            'Dív.Brut/ Patrim.': 'div_pat'
        }
        df.rename(columns=rename, inplace=True)
        for c in df.columns:
            if df[c].dtype == object and c != 'ticker':
                df[c] = df[c].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df['roic'] /= 100
        # Safe division
        df['lpa'] = df.apply(lambda x: x['price']/x['pl'] if x['pl']!=0 and not pd.isna(x['pl']) else 0, axis=1)
        df['vpa'] = df.apply(lambda x: x['price']/x['pvp'] if x['pvp']!=0 and not pd.isna(x['pvp']) else 0, axis=1)
        return df
    except Exception as e:
        print(f"❌ ERRO SCRAPER ACOES: {str(e)}")
        if 'r' in locals():
            print(f"Status Code: {r.status_code}")
        return pd.DataFrame()

def get_data_fiis():
    """Busca dados de FIIs brasileiros do Fundamentus"""
    try:
        url = 'https://www.fundamentus.com.br/fii_resultado.php'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        df = pd.read_html(io.StringIO(r.text), decimal=',', thousands='.')[0]
        rename = {
            'Papel': 'ticker',
            'Cotação': 'price',
            'Dividend Yield': 'dy',
            'P/VP': 'pvp',
            'Liquidez': 'liquidezmediadiaria',
            'Segmento': 'segmento'
        }
        df.rename(columns=rename, inplace=True)
        for c in df.columns:
            if df[c].dtype == object and c not in ['ticker', 'segmento']:
                df[c] = df[c].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df['dy'] /= 100
        return df
    except Exception as e:
        print(f"❌ ERRO SCRAPER FIIS: {str(e)}")
        if 'r' in locals():
            print(f"Status Code: {r.status_code}")
        return pd.DataFrame()

def get_data_usa():
    """Busca dados de ações americanas via TradingView Scanner API"""
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "filter": [
                {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
                {"left": "subtype", "operation": "in_range", "right": ["common", "foreign-issuer"]},
                {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE"]},
                {"left": "close", "operation": "greater", "right": 2},
                {"left": "market_cap_basic", "operation": "greater", "right": 50000000}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": [
                "name", "close", "volume", "market_cap_basic",
                "price_earnings_ttm", "price_book_fq", "enterprise_value_ebitda_ttm",
                "return_on_invested_capital_fq", "dividend_yield_recent",
                "earnings_per_share_basic_ttm", "net_margin_ttm"
            ],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [0, 8000]
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        data = r.json()
        
        if 'data' not in data:
            return pd.DataFrame()
        
        rows = []
        for d in data['data']:
            s = d['d']
            ticker = s[0]
            price = s[1] if s[1] is not None else 0
            vol = s[2] if s[2] is not None else 0
            liq = vol * price
            pl = s[4] if s[4] is not None else 0
            pvp = s[5] if s[5] is not None else 0
            ev_ebit = s[6] if s[6] is not None else 0
            roic = s[7] if s[7] is not None else 0
            dy = s[8] if s[8] is not None else 0
            lpa = s[9] if s[9] is not None else 0
            margin = s[10] if s[10] is not None else 0
            
            vpa = 0
            if pvp > 0 and price > 0:
                vpa = price / pvp
            
            if (vol > 100000) or (liq > 500000):
                if price > 0:
                    rows.append({
                        'ticker': ticker,
                        'price': price,
                        'pl': pl,
                        'pvp': pvp,
                        'ev_ebit': ev_ebit,
                        'roic': roic,
                        'liquidezmediadiaria': liq,
                        'dy': dy,
                        'lpa': lpa,
                        'vpa': vpa,
                        'Margem': margin / 100,
                        'net_margin': margin,
                        'IsETF': False
                    })
                
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

def get_data_usa_etfs():
    """Busca dados de ETFs americanos via TradingView Scanner API"""
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "filter": [
                {"left": "type", "operation": "in_range", "right": ["fund", "dr"]},
                {"left": "subtype", "operation": "in_range", "right": ["etf", "etn", "uit"]},
                {"left": "exchange", "operation": "in_range", "right": ["AMEX", "NASDAQ", "NYSE"]}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "close", "volume", "average_volume_10d_calc"],
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "range": [0, 500]
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        data = r.json()
        
        if 'data' not in data:
            return pd.DataFrame()
        
        rows = []
        for d in data['data']:
            s = d['d']
            ticker = s[0]
            price = s[1] if s[1] is not None else 0
            vol = s[2] if s[2] is not None else 0
            liq = vol * price
            
            if liq > 100000 and price > 0:
                rows.append({
                    'ticker': ticker,
                    'price': price,
                    'liquidezmediadiaria': liq,
                    'pvp': 0,
                    'dy': 0,
                    'Region': 'US'
                })
        
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

def get_data_usa_reits():
    """Busca dados de REITs americanos via TradingView Scanner API"""
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "filter": [
                {"left": "type", "operation": "in_range", "right": ["fund"]},
                {"left": "subtype", "operation": "in_range", "right": ["reit"]},
                {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ"]}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "close", "volume", "dividend_yield_recent", "price_book_fq"],
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "range": [0, 200]
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        data = r.json()
        
        if 'data' not in data:
            return pd.DataFrame()
        
        rows = []
        for d in data['data']:
            s = d['d']
            ticker = s[0]
            price = s[1] if s[1] is not None else 0
            vol = s[2] if s[2] is not None else 0
            dy = s[3] if s[3] is not None else 0
            pvp = s[4] if s[4] is not None else 0
            liq = vol * price
            
            if liq > 100000 and price > 0:
                rows.append({
                    'ticker': ticker,
                    'price': price,
                    'liquidezmediadiaria': liq,
                    'pvp': pvp,
                    'dy': dy / 100,
                    'segmento': 'REIT (US)',
                    'Region': 'US'
                })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df['dy'] = df['dy'] / 100
        return df
    except:
        return pd.DataFrame()

def get_candle_chart(ticker):
    """Gera gráfico de velas usando yfinance"""
    try:
        symbols_to_try = [f"{ticker}.SA", ticker]
        df = pd.DataFrame()
        for sym in symbols_to_try:
            df = yf.download(sym, period="6mo", interval="1d", progress=False)
            if not df.empty and len(df) > 5:
                break
        
        if not df.empty and len(df) > 5:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if 'Open' in df.columns and 'Close' in df.columns:
                fig = go.Figure(data=[go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    increasing_line_color='#00ff41',
                    decreasing_line_color='#ff4444'
                )])
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    plot_bgcolor='black',
                    paper_bgcolor='black',
                    font=dict(color='white'),
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=350,
                    title=dict(
                        text=f"GRÁFICO DIÁRIO: {ticker}",
                        x=0.5,
                        font=dict(size=14, color='#00ff41')
                    )
                )
                return fig
        return None
    except:
        return None

# ==============================================================================
# FUNÇÕES DE PIPELINE DE DADOS
# ==============================================================================

def load_data_acoes_pipeline(selected_markets):
    """Pipeline de carregamento de dados de ações"""
    df_final = pd.DataFrame()
    
    # Check BR
    if any("Brasil" in s for s in selected_markets):
        df_br = get_data_acoes()
        if not df_br.empty:
            df_br['Region'] = 'BR'
            # FILTER: Exclude ETFs
            df_br['IsETF'] = df_br['ticker'].apply(is_likely_etf)
            df_br = df_br[~df_br['IsETF']].copy()
            df_final = pd.concat([df_final, df_br])
            
    # Check US
    if any("Estados Unidos" in s for s in selected_markets):
        df_us = get_data_usa()
        if not df_us.empty:
            df_us['Region'] = 'US'
            if 'IsETF' not in df_us.columns:
                df_us['IsETF'] = False
            df_final = pd.concat([df_final, df_us])

    if not df_final.empty:
        df_acoes = df_final
        
        # Apply general filters
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
        cols_to_drop = ['Score', 'MagicRank', 'R_EV', 'R_ROIC']
        df_acoes = df_acoes.drop(columns=[c for c in cols_to_drop if c in df_acoes.columns], errors='ignore')
        df_acoes = df_acoes.merge(df_magic_calc[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
        
        return df_acoes
    return None

def load_data_etfs_pipeline(selected_markets):
    """Pipeline de carregamento de dados de ETFs"""
    df_final = pd.DataFrame()
    
    # BR ETFs
    if any("Brasil" in s for s in selected_markets):
        try:
            tickers_sa = [f"{t}.SA" for t in KNOWN_ETFS]
            batch = yf.download(tickers_sa, period="5d", interval="1d", group_by='ticker', progress=False)
            etf_data = []
            for t_raw in KNOWN_ETFS:
                t_sa = f"{t_raw}.SA"
                try:
                    if len(tickers_sa) > 1:
                        df_t = batch[t_sa]
                    else:
                        df_t = batch
                    
                    if not df_t.empty:
                        last_row = df_t.iloc[-1]
                        price = float(last_row['Close'])
                        vol = float(last_row['Volume']) * price
                        if price > 0:
                            etf_data.append({
                                'ticker': t_raw,
                                'price': price,
                                'liquidezmediadiaria': vol,
                                'pvp': 0,
                                'dy': 0,
                                'Region': 'BR'
                            })
                except:
                    pass
            
            if etf_data:
                df_etf_br = pd.DataFrame(etf_data)
                df_final = pd.concat([df_final, df_etf_br])
        except:
            pass

    # US ETFs
    if any("Estados Unidos" in s for s in selected_markets):
        df_us = get_data_usa_etfs()
        if not df_us.empty:
            df_final = pd.concat([df_final, df_us])

    if not df_final.empty:
        df_etf = df_final.sort_values('liquidezmediadiaria', ascending=False)
        return df_etf
    return None

def load_data_fiis_pipeline(selected_markets):
    """Pipeline de carregamento de dados de FIIs"""
    df_final = pd.DataFrame()
    
    # BR FIIs
    if any("Brasil" in s for s in selected_markets):
        df_br = get_data_fiis()
        if not df_br.empty:
            df_br['Region'] = 'BR'
            df_final = pd.concat([df_final, df_br])
            
    # US REITs
    if any("Estados Unidos" in s for s in selected_markets):
        df_us = get_data_usa_reits()
        if not df_us.empty:
            df_final = pd.concat([df_final, df_us])
            
    if not df_final.empty:
        return df_final
    return None
