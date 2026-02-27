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

PAGE_SIZE = 1000  # StatusInvest returns up to ~616 stocks, request 1000 to get all in one shot

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
        # Use SEARCH_FILTER_STOCKS to get all columns including sectorname.
        data = _fetch_paginated(category_type=1, label="BR stocks", search_filter=SEARCH_FILTER_STOCKS)

        if not data:
            logger.warning("StatusInvest: No stock data returned.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Deduplicate: StatusInvest sometimes returns totalResults > actual unique count,
        # causing the paginator to re-fetch the same rows on subsequent pages.
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['ticker'], keep='first')
        if len(df) < before_dedup:
            logger.info(f"StatusInvest: Removed {before_dedup - len(df)} duplicate rows")

        # Log actual columns for debugging
        logger.info(f"StatusInvest Stocks columns: {sorted(df.columns.tolist())}")

        # MAPPING STATUS INVEST TO APP SCHEMA
        # StatusInvest paginated API returns ALL LOWERCASE keys.
        # Verified via live API probe (36 columns total).
        # ALL columns are mapped to preserve full data fidelity.
        rename_map = {
            # ── Identity ──────────────────────────────────────────────────────
            'ticker': 'ticker',
            'companyname': 'empresa',
            'sectorname': 'setor',
            # ── Price & Valuation ─────────────────────────────────────────────
            'price': 'price',
            'p_l': 'pl',
            'p_vp': 'pvp',
            'ev_ebit': 'ev_ebit',
            'p_ebit': 'p_ebit',
            'p_sr': 'p_sr',
            'peg_ratio': 'peg_ratio',
            'p_ativo': 'p_ativo',
            'p_capitalgiro': 'p_capital_giro',
            'p_ativocirculante': 'p_ativo_circulante',
            # ── Profitability ─────────────────────────────────────────────────
            'roic': 'roic',
            'roe': 'roe',
            'roa': 'roa',
            'dy': 'dy',
            'lpa': 'lpa',
            'vpa': 'vpa',
            'giroativos': 'giro_ativos',
            # ── Margins ───────────────────────────────────────────────────────
            'margembruta': 'margem_bruta',
            'margemebit': 'margem_ebit',
            'margemliquida': 'margem_liquida',
            # ── Debt / Structure ──────────────────────────────────────────────
            'dividaliquidapatrimonioliquido': 'div_pat',
            'dividaliquidaebit': 'div_liq_ebitda',
            'liquidezcorrente': 'liq_corrente',
            'pl_ativo': 'pl_ativo',
            'passivo_ativo': 'passivo_ativo',
            # ── Growth (CAGR 5 anos) ─────────────────────────────────────────
            'lucros_cagr5': 'cagr_lucros',
            'receitas_cagr5': 'cagr_receitas',
            # ── Size & Liquidity ──────────────────────────────────────────────
            'liquidezmediadiaria': 'liquidezmediadiaria',
            'valormercado': 'valor_mercado',
        }

        # Filter only existing columns just in case
        cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df.rename(columns=cols_to_rename, inplace=True)

        # Normalize ALL numeric columns
        numeric_cols = [
            'price', 'pl', 'pvp', 'ev_ebit', 'p_ebit', 'p_sr', 'peg_ratio',
            'p_ativo', 'p_capital_giro', 'p_ativo_circulante',
            'roic', 'roe', 'roa', 'dy', 'lpa', 'vpa', 'giro_ativos',
            'margem_bruta', 'margem_ebit', 'margem_liquida',
            'div_pat', 'div_liq_ebitda', 'liq_corrente', 'pl_ativo', 'passivo_ativo',
            'cagr_lucros', 'cagr_receitas',
            'liquidezmediadiaria', 'valor_mercado',
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # StatusInvest returns percentages as whole numbers (e.g. 15.0 = 15%)
        # App stores as ratios (0.15 = 15%)
        pct_cols = [
            'dy', 'roic', 'roe', 'roa',
            'margem_bruta', 'margem_ebit', 'margem_liquida',
            'cagr_lucros', 'cagr_receitas',
        ]
        for pct_col in pct_cols:
            if pct_col in df.columns:
                df[pct_col] = df[pct_col] / 100.0

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
