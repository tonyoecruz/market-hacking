"""
RENDA FIXA ENGINE — Strategy-based Screener
=============================================
Implements 4 investment models for Fixed Income:

  1. reserva_emergencia — Daily liquidity, safe issuers, sort by % CDI
  2. ganho_real         — IPCA+ with > 3yr maturity, sort by spread
  3. trava_preco        — Pre-fixed, 1–5yr, sort by highest rate
  4. duelo_tributario   — Gross-up equivalence, sort by equivalent gross rate
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


def _parse_date(d: str) -> datetime:
    """Try parsing date string in common formats."""
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(d, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _days_to_maturity(maturity_str: str) -> int:
    """Calculate days until maturity. Returns 0 if unparseable."""
    d = _parse_date(maturity_str)
    if d is None:
        return 0
    delta = d - datetime.now()
    return max(delta.days, 0)


def _ir_aliquota(days: int) -> float:
    """Brazilian regressive Income Tax table for fixed income."""
    if days <= 180:
        return 0.225
    elif days <= 360:
        return 0.20
    elif days <= 720:
        return 0.175
    else:
        return 0.15


def _is_exempt(product_type: str) -> bool:
    """Check if product type is income tax exempt."""
    return product_type.upper() in ('LCI', 'LCA', 'CRI', 'CRA')


# ══════════════════════════════════════════════════════════════════════════════
# MODEL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _model_reserva_emergencia(data: List[Dict]) -> tuple:
    """
    Reserva de Emergência (Liquidez e Segurança)
    Filters: Liquidez Diária, Emissor seguro, >= 6 meses vencimento
    Sort:    Descending % CDI
    """
    caveats = []
    filtered = []

    for item in data:
        # Must have daily liquidity
        liq = str(item.get('liquidity', '')).lower()
        if 'diária' not in liq and 'diaria' not in liq and 'd+0' not in liq and 'd+1' not in liq:
            continue

        # Must be safe issuer (FGC or Tesouro)
        safety = str(item.get('safety_rating', '')).lower()
        if 'fgc' not in safety and 'tesouro' not in safety:
            continue

        # Maturity >= 6 months
        days = _days_to_maturity(item.get('maturity', ''))
        if days < 180:
            continue

        filtered.append(item)

    # Sort by rate_val (% CDI) descending
    filtered.sort(key=lambda x: x.get('rate_val', 0), reverse=True)

    score_col = {'key': 'rate_val', 'label': '% do CDI', 'pct': False}
    return filtered, score_col, caveats


def _model_ganho_real(data: List[Dict]) -> tuple:
    """
    Ganho Real Longo Prazo (IPCA+)
    Filters: Indexador = IPCA, Vencimento > 3 anos
    Sort:    Descending spread above IPCA
    """
    caveats = []
    filtered = []

    for item in data:
        rate_type = str(item.get('rate_type', '')).lower()
        # Check for IPCA-indexed products
        if 'ipca' not in rate_type and 'inflação' not in rate_type:
            continue

        # Maturity > 3 years (1095 days)
        days = _days_to_maturity(item.get('maturity', ''))
        if days < 1095:
            continue

        filtered.append(item)

    # Sort by rate_val (spread above IPCA) descending
    filtered.sort(key=lambda x: x.get('rate_val', 0), reverse=True)

    if not filtered:
        caveats.append("Nenhum título IPCA+ com vencimento > 3 anos encontrado nos dados atuais.")

    score_col = {'key': 'rate_val', 'label': 'Spread IPCA+ (%)', 'pct': False}
    return filtered, score_col, caveats


def _model_trava_preco(data: List[Dict]) -> tuple:
    """
    Trava de Preço (Pré-Fixado)
    Filters: Indexador = Pré-fixado, Vencimento 1–5 anos
    Sort:    Descending taxa anual
    """
    caveats = []
    filtered = []

    for item in data:
        rate_type = str(item.get('rate_type', '')).lower()
        if 'pré' not in rate_type and 'pre' not in rate_type and 'prefixado' not in rate_type:
            continue

        days = _days_to_maturity(item.get('maturity', ''))
        # 1–5 years = 365–1825 days
        if days < 365 or days > 1825:
            continue

        filtered.append(item)

    # Sort by rate_val (annual %) descending
    filtered.sort(key=lambda x: x.get('rate_val', 0), reverse=True)

    if not filtered:
        caveats.append("Nenhum título Pré-fixado com vencimento entre 1-5 anos encontrado.")

    score_col = {'key': 'rate_val', 'label': 'Taxa Anual (%)', 'pct': False}
    return filtered, score_col, caveats


def _model_duelo_tributario(data: List[Dict]) -> tuple:
    """
    Duelo Tributário (Equivalência Gross-Up)
    Converts exempt (LCI/LCA/CRI/CRA) rates to gross equivalent.
    Formula: Taxa Bruta Equiv = Taxa Isenta / (1 - Alíquota IR do prazo)
    Sort:    Descending Taxa Bruta Equivalente
    """
    caveats = []
    processed = []

    for item in data:
        entry = dict(item)  # copy
        product_type = item.get('type', 'CDB')
        rate_val = item.get('rate_val', 0)
        days = _days_to_maturity(item.get('maturity', ''))

        if _is_exempt(product_type):
            # Convert exempt rate to gross equivalent
            aliquota = _ir_aliquota(days)
            entry['_taxa_bruta_equiv'] = rate_val / (1 - aliquota) if aliquota < 1 else rate_val
            entry['_is_exempt'] = True
            entry['_aliquota_ir'] = aliquota * 100
        else:
            # Already taxed — gross rate = rate as-is
            entry['_taxa_bruta_equiv'] = rate_val
            entry['_is_exempt'] = False
            entry['_aliquota_ir'] = _ir_aliquota(days) * 100

        processed.append(entry)

    # Sort by gross equivalent descending
    processed.sort(key=lambda x: x.get('_taxa_bruta_equiv', 0), reverse=True)

    score_col = {'key': '_taxa_bruta_equiv', 'label': 'Taxa Bruta Equiv. (%)', 'pct': False}
    return processed, score_col, caveats


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════
_MODELS = {
    'reserva_emergencia': _model_reserva_emergencia,
    'ganho_real':         _model_ganho_real,
    'trava_preco':        _model_trava_preco,
    'duelo_tributario':   _model_duelo_tributario,
}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def apply_rendafixa_strategy(
    data: List[Dict],
    strategy: str,
) -> tuple:
    """
    Apply a Renda Fixa strategy engine.

    Args:
        data: list of dicts from FixedIncomeManager.get_top_opportunities()
        strategy: strategy identifier

    Returns:
        (filtered_data, score_col, caveats)
    """
    model_fn = _MODELS.get(strategy)
    if not model_fn:
        logger.warning(f"[rendafixa_engine] unknown strategy '{strategy}'")
        return data, {}, [f"Modelo '{strategy}' não encontrado."]

    try:
        result, score_col, caveats = model_fn(data)
    except Exception as e:
        logger.error(f"[rendafixa_engine] error in model '{strategy}': {e}", exc_info=True)
        return [], {}, [f"Erro ao executar modelo: {str(e)}"]

    return result, score_col, caveats
