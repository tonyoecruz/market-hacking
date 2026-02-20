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

PAGE_SIZE = 500

# Full search filter with all ranges set to null = no filter = return everything
# StatusInvest requires explicit structure to return ALL results (not just a subset)
SEARCH_FILTER_STOCKS = json.dumps({
    "Sector": "",
    "SubSector": "",
    "Segment": "",
    "my_range": "-20;100",
    "dy": {"Item1": None, "Item2": None},
    "p_L": {"Item1": None, "Item2": None},
    "peg_Ratio": {"Item1": None, "Item2": None},
    "p_VP": {"Item1": None, "Item2": None},
    "p_Ativo": {"Item1": None, "Item2": None},
    "margemBruta": {"Item1": None, "Item2": None},
    "margemEbit": {"Item1": None, "Item2": None},
    "margemLiquida": {"Item1": None, "Item2": None},
    "p_Ebit": {"Item1": None, "Item2": None},
    "eV_Ebit": {"Item1": None, "Item2": None},
    "dividaLiquidaEbit": {"Item1": None, "Item2": None},
    "dividaliquidaPatrimonioLiquido": {"Item1": None, "Item2": None},
    "p_SR": {"Item1": None, "Item2": None},
    "p_CapitalGiro": {"Item1": None, "Item2": None},
    "p_AtivoCirculante": {"Item1": None, "Item2": None},
    "roe": {"Item1": None, "Item2": None},
    "roic": {"Item1": None, "Item2": None},
    "roa": {"Item1": None, "Item2": None},
    "liquidezCorrente": {"Item1": None, "Item2": None},
    "pl_Ativo": {"Item1": None, "Item2": None},
    "passivo_Ativo": {"Item1": None, "Item2": None},
    "gpianoTangivel": {"Item1": None, "Item2": None},
    "recepidasNet5Years": {"Item1": None, "Item2": None},
    "lucpidasNet5Years": {"Item1": None, "Item2": None},
    "liqupidasMediaDiaria": {"Item1": None, "Item2": None}
})

SEARCH_FILTER_FIIS = json.dumps({
    "Segment": "",
    "gestao": "",
    "my_range": "-20;100",
    "dy": {"Item1": None, "Item2": None},
    "p_VP": {"Item1": None, "Item2": None},
    "percentualcaixa": {"Item1": None, "Item2": None},
    "dividend": {"Item1": None, "Item2": None},
    "patrimonio": {"Item1": None, "Item2": None},
    "valorpatrimonialcota": {"Item1": None, "Item2": None},
    "numerocotas": {"Item1": None, "Item2": None},
    "lastdividend": {"Item1": None, "Item2": None}
})


def _fetch_paginated(category_type, label="items", search_filter=None):
    """
    Fetches ALL records from StatusInvest paginated endpoint.
    Returns a list of dicts (raw JSON items).
    """
    url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
    all_items = []
    skip = 0

    while True:
        params = {
            "search": search_filter or "{}",
            "CategoryType": category_type,
            "take": PAGE_SIZE,
            "skip": skip,
        }
        try:
            logger.info(f"StatusInvest: Fetching {label} skip={skip} take={PAGE_SIZE}...")
            response = requests.get(url, params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Paginated endpoint returns {"list": [...], "totalResults": N}
            if isinstance(data, dict):
                items = data.get('list', [])
                total = data.get('totalResults', 0)
            elif isinstance(data, list):
                # Fallback if API returns flat list
                items = data
                total = len(data)
            else:
                logger.error(f"StatusInvest: Unexpected data format: {type(data)}")
                break

            if not items:
                break

            all_items.extend(items)
            logger.info(f"StatusInvest: Got {len(items)} {label} (total so far: {len(all_items)}/{total})")

            # Check if we've fetched everything
            skip += PAGE_SIZE
            if skip >= total or len(items) < PAGE_SIZE:
                break

        except Exception as e:
            logger.error(f"StatusInvest: Error fetching page skip={skip}: {e}")
            break

    logger.info(f"StatusInvest: Total {label} fetched: {len(all_items)}")
    return all_items


def get_br_stocks_statusinvest():
    """
    Fetches FULL Brazilian Stock Market data from Status Invest via paginated API.
    Returns: DataFrame with standardized columns (ticker, price, pl, pvp, etc.)
    """
    try:
        data = _fetch_paginated(category_type=1, label="BR stocks", search_filter=SEARCH_FILTER_STOCKS)

        if not data:
            logger.warning("StatusInvest: No stock data returned.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Log actual columns for debugging
        logger.info(f"StatusInvest Stocks columns: {sorted(df.columns.tolist())}")

        # MAPPING STATUS INVEST TO APP SCHEMA
        # StatusInvest paginated API returns lowercase keys:
        # ticker, price, p_l, p_vp, ev_ebit, roic, dy, liquidezmediadiaria, lpa, vpa,
        # dividaliquidapatrimonioliquido, companyname, sectorname, subsectorname, segmentname
        rename_map = {
            'ticker': 'ticker',
            'price': 'price',
            'p_l': 'pl',
            'p_vp': 'pvp',
            'ev_ebit': 'ev_ebit',
            'roic': 'roic',
            'roe': 'roe_raw',           # raw ROE (from StatusInvest, percentage)
            'dy': 'dy',
            'liquidezmediadiaria': 'liquidezmediadiaria',
            'lpa': 'lpa',
            'vpa': 'vpa',
            'dividaliquidapatrimonioliquido': 'div_pat',
            'liquidezCorrente': 'liq_corrente',
            'lucpidasNet5Years': 'cagr_lucros',  # CAGR Lucros 5 anos
            'companyname': 'empresa',
            'sectorname': 'setor',
        }

        # Filter only existing columns just in case
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df.rename(columns=cols_to_rename, inplace=True)

        # Normalize Data Types
        numeric_cols = ['price', 'pl', 'pvp', 'ev_ebit', 'roic', 'dy', 'liquidezmediadiaria',
                        'lpa', 'vpa', 'div_pat', 'liq_corrente', 'cagr_lucros', 'roe_raw']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # StatusInvest returns percentages as whole numbers (e.g. 15.0 = 15%)
        # App expects ratios (0.15 = 15%)
        if 'dy' in df.columns:
            df['dy'] = pd.to_numeric(df['dy'], errors='coerce').fillna(0)
            df['dy'] = df['dy'] / 100.0
        if 'roic' in df.columns:
            df['roic'] = pd.to_numeric(df['roic'], errors='coerce').fillna(0)
            df['roic'] = df['roic'] / 100.0
        if 'roe_raw' in df.columns:
            # Store ROE as ratio too; rename to roe
            df['roe_raw'] = df['roe_raw'] / 100.0
            df.rename(columns={'roe_raw': 'roe_si'}, inplace=True)

        return df

    except Exception as e:
        logger.error(f"Error fetching Status Invest Stocks: {e}")
        return pd.DataFrame()


def get_br_fiis_statusinvest():
    """
    Fetches FULL Brazilian FII Market data from Status Invest via paginated API.
    Returns: DataFrame with standardized columns.
    """
    try:
        data = _fetch_paginated(category_type=2, label="BR FIIs", search_filter=SEARCH_FILTER_FIIS)

        if not data:
            logger.warning("StatusInvest: No FII data returned.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Log actual columns for debugging
        logger.info(f"StatusInvest FIIs columns: {sorted(df.columns.tolist())}")

        # Mapping for FIIs (lowercase keys from paginated endpoint)
        rename_map = {
            'ticker': 'ticker',
            'price': 'price',
            'p_vp': 'pvp',
            'dy': 'dy',
            'liquidezmediadiaria': 'liquidezmediadiaria',
            'sectorname': 'segmento',
            'companyname': 'empresa',
        }

        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df.rename(columns=cols_to_rename, inplace=True)

        numeric_cols = ['price', 'pvp', 'dy', 'liquidezmediadiaria']
        for col in numeric_cols:
            if col in df.columns:
                 df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Normalize percentages
        if 'dy' in df.columns:
            df['dy'] = pd.to_numeric(df['dy'], errors='coerce').fillna(0)
            df['dy'] = df['dy'] / 100.0

        return df

    except Exception as e:
        logger.error(f"Error fetching Status Invest FIIs: {e}")
        return pd.DataFrame()
