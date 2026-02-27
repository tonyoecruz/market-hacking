"""
Risk Checker — Automated Issuer Safety Validation
====================================================
Uses Banco Central do Brasil (BCB) PUBLIC data to check financial institutions
for liquidation, intervention, or other special regimes. NO API KEY REQUIRED.

Three risk tiers:
  - 'liquidada'    → NEVER show (institution under liquidation/intervention)
  - 'alto_risco'   → Show only with toggle ON (small/unknown + high risk_score)
  - 'normal'       → Always show

Data sources:
  1. BCB Olinda API (free, public) — list of institutions under special regimes
  2. Local hardcoded safety net — known problem institutions (fallback)
"""

import requests
import logging
import time
from typing import Dict, Optional, Set
from functools import lru_cache

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# LOCAL SAFETY NET — Known problem institutions (always applied, even if BCB
# API is down). Update this list whenever a major case is identified.
# ══════════════════════════════════════════════════════════════════════════════
_BLACKLIST_LIQUIDADAS: Set[str] = {
    # Formato: nome normalizado (lower, stripped)
    "banco master",
    "master",
    "bny mellon banco",       # Exited BR market
    "banco bva",              # Liquidado
    "banco santos",           # Liquidado
    "banco cruzeiro do sul",  # Liquidado
    "cruzeiro do sul",
    "banco panamericano",     # Histórico de fraude (hoje PagBank, mas o nome antigo não deve aparecer)
    "banco rural",            # Liquidado
    "banco morada",           # Liquidado
    "banco beg",              # Liquidado
    "banco schahin",          # Liquidado
    "gradual investimentos",  # Liquidado
    "walpires",               # Liquidado
    "corval",                 # Liquidado
    "portoseg",               # Verificar status
}

_BLACKLIST_ALTO_RISCO: Set[str] = {
    "caruana",
    "caruana financeira",
    "agibank",           # Pequeno, histórico de reclamações
    "banco arbi",        # Muito pequeno
    "banco fibra",       # Pequeno
    "dacasa financeira", # Pequeno
}

# ══════════════════════════════════════════════════════════════════════════════
# BCB PUBLIC API — Institutions under special regimes
# Endpoint: https://olinda.bcb.gov.br/olinda/servico/Informes_ListaRegimeEspecial
# This is FREE and requires NO authentication.
# ══════════════════════════════════════════════════════════════════════════════
_BCB_REGIME_ESPECIAL_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "regimes_especiais/versao/v1/odata/"
    "Regimes?$format=json&$top=500"
)

# Cache duration: 24 hours (86400 seconds)
_bcb_cache: Dict = {
    "data": None,
    "timestamp": 0,
    "ttl": 86400,
}


def _normalize(name: str) -> str:
    """Normalize issuer name for matching."""
    return name.lower().strip().replace("s.a.", "").replace("s/a", "").replace("ltda", "").strip()


def _fetch_bcb_blacklist() -> Set[str]:
    """
    Fetch the list of institutions under special regimes from BCB.
    Returns a set of normalized institution names.
    Falls back gracefully on any error.
    """
    now = time.time()

    # Return cached if fresh
    if _bcb_cache["data"] is not None and (now - _bcb_cache["timestamp"]) < _bcb_cache["ttl"]:
        return _bcb_cache["data"]

    try:
        logger.info("[risk_checker] Fetching BCB regime especial data...")
        resp = requests.get(_BCB_REGIME_ESPECIAL_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        names = set()
        for item in data.get("value", []):
            nome = item.get("NomeInstituicao", "") or item.get("Nome", "")
            if nome:
                names.add(_normalize(nome))

        _bcb_cache["data"] = names
        _bcb_cache["timestamp"] = now
        logger.info(f"[risk_checker] BCB data loaded: {len(names)} institutions under special regimes")
        return names

    except Exception as e:
        logger.warning(f"[risk_checker] BCB API unavailable ({e}). Using local blacklist only.")
        # Return empty set — will fall through to local blacklist
        return set()


def check_issuer_risk(issuer_name: str, risk_score: int = 1) -> str:
    """
    Check the risk tier of a financial institution.

    Args:
        issuer_name: Name of the issuing institution
        risk_score: Internal risk score (1-5)

    Returns:
        'liquidada'   — institution under liquidation/intervention (NEVER show)
        'alto_risco'  — high risk institution (show only with toggle)
        'normal'      — safe to display
    """
    normalized = _normalize(issuer_name)

    # 1. Check local blacklist — LIQUIDADAS (instant, always works)
    for bl_name in _BLACKLIST_LIQUIDADAS:
        if bl_name in normalized or normalized in bl_name:
            return "liquidada"

    # 2. Check BCB data — REGIME ESPECIAL (fetched & cached)
    bcb_names = _fetch_bcb_blacklist()
    for bcb_name in bcb_names:
        if bcb_name in normalized or normalized in bcb_name:
            return "liquidada"

    # 3. Check local blacklist — ALTO RISCO
    for bl_name in _BLACKLIST_ALTO_RISCO:
        if bl_name in normalized or normalized in bl_name:
            return "alto_risco"

    # 4. Risk score heuristic — risk_score >= 4 = alto risco
    if risk_score >= 4:
        return "alto_risco"

    return "normal"


def tag_opportunities(opportunities: list) -> list:
    """
    Tag each opportunity with its risk tier.
    Adds '_risk_tier' field to each dict.
    """
    for opp in opportunities:
        issuer = opp.get("issuer", "")
        risk_score = opp.get("risk_score", 1)
        opp["_risk_tier"] = check_issuer_risk(issuer, risk_score)
    return opportunities


def filter_opportunities(opportunities: list, show_high_risk: bool = False) -> list:
    """
    Filter opportunities based on risk tier.

    - Liquidated: ALWAYS removed (never shown)
    - High risk: shown only if show_high_risk=True
    - Normal: always shown
    """
    tagged = tag_opportunities(opportunities)

    result = []
    for opp in tagged:
        tier = opp.get("_risk_tier", "normal")

        if tier == "liquidada":
            continue  # NEVER show

        if tier == "alto_risco" and not show_high_risk:
            continue  # Only show when toggle is ON

        result.append(opp)

    return result
