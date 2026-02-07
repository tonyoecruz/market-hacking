import requests
import pandas as pd
import json
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://statusinvest.com.br/acoes/busca-avancada",
    "Origin": "https://statusinvest.com.br",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
}

def get_br_stocks_statusinvest():
    """
    Fetches FULL Brazilian Stock Market data from Status Invest via undocumented API.
    Returns: DataFrame with standardized columns (ticker, price, pl, pvp, etc.)
    """
    url = "https://statusinvest.com.br/category/advancedsearchresult"
    params = {
        "search": "{}",
        "CategoryType": 1 # 1 = Ações
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if not data or not isinstance(data, list):
            logger.error("Status Invest API returned empty list or invalid format.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        
        # MAPPING STATUS INVEST TO APP SCHEMA
        # Status Invest Keys (Common): 
        # ticker, price, p_L, p_VP, ev_Ebit, roic, dividendYield, liquidezMediaDiaria, lpa, vpa, dividaLiquida_Patrimonio
        
        rename_map = {
            'ticker': 'ticker',
            'price': 'price',
            'p_L': 'pl',
            'p_VP': 'pvp',
            'ev_Ebit': 'ev_ebit',
            'roic': 'roic',
            'dividendYield': 'dy',
            'liquidezMediaDiaria': 'liquidezmediadiaria',
            'lpa': 'lpa',
            'vpa': 'vpa',
            'dividaLiquida_Patrimonio': 'div_pat'
        }
        
        # Filter only existing columns just in case
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df.rename(columns=cols_to_rename, inplace=True)
        
        # Normalize Data Types
        numeric_cols = ['price', 'pl', 'pvp', 'ev_ebit', 'roic', 'dy', 'liquidezmediadiaria', 'lpa', 'vpa', 'div_pat']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Status Invest usually returns percentages as whole numbers or ratios?
        # Check: dy is usually percentage (e.g. 5.5 = 5.5%). App expects ratio (0.055) OR percentage?
        # Let's check app.py calc.
        # graham/magic use ratios for roic (e.g. 0.15 = 15%).
        # Status Invest 'roic' usually implies Percentage (e.g. 15.0).
        # Same for DY.
        
        if 'dy' in df.columns: df['dy'] = df['dy'] / 100.0
        if 'roic' in df.columns: df['roic'] = df['roic'] / 100.0
        
        # Ensure Ticker has .SA suffix for consistency across app?
        # App uses straight tickers often, but yfinance extractor added .SA?
        # Actually yfinance extractor removed .SA for display?
        # Re-verify: app.py specifices .SA for yfinance.
        # Let's keep raw valid ticker here, data_fetcher can adjust if needed.
        # But for 'Region' logic, 'BR' is assumed.
        # Many parts of app use ticker without .SA.
        
        return df

    except Exception as e:
        logger.error(f"Error fetching Status Invest Stocks: {e}")
        return pd.DataFrame()

def get_br_fiis_statusinvest():
    """
    Fetches FULL Brazilian FII Market data from Status Invest.
    Returns: DataFrame with standardized columns.
    """
    url = "https://statusinvest.com.br/category/advancedsearchresult"
    params = {
        "search": "{}",
        "CategoryType": 2 # 2 = FIIs
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if not data or not isinstance(data, list):
            return pd.DataFrame()

        df = pd.DataFrame(data)
        
        # Mapping for FIIs
        # Keys: ticker, price, p_VP, dividendYield, liquidezMediaDiaria, segmento (sometimes), valorPatrimonialCota (vp_cota)
        
        rename_map = {
            'ticker': 'ticker',
            'price': 'price',
            'p_VP': 'pvp',
            'dividendYield': 'dy',
            'liquidezMediaDiaria': 'liquidezmediadiaria',
            'segmentName': 'segmento', # Sometimes subSectorName
            'valorPatrimonialCota': 'vp_cota' # equivalent to VPA for FIIs
        }
        
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df.rename(columns=cols_to_rename, inplace=True)

        numeric_cols = ['price', 'pvp', 'dy', 'liquidezmediadiaria', 'vp_cota']
        for col in numeric_cols:
            if col in df.columns:
                 df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Normalize percentages
        if 'dy' in df.columns: df['dy'] = df['dy'] / 100.0
        
        return df

    except Exception as e:
        logger.error(f"Error fetching Status Invest FIIs: {e}")
        return pd.DataFrame()
