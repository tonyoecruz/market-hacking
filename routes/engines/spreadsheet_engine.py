"""
MODO PLANILHA — Spreadsheet Rank Engine (1:1 com a aba Screener)
===============================================================

Este engine replica o comportamento do "Screener" do Excel/Google Sheets:

- As "macros" só ligam/desligam checkboxes; a inteligência real é:
  1) Para cada critério ativo:
      - Se "Menor é melhor": transforma em 1/valor
      - Se "Maior é melhor": usa valor original
  2) Calcula rank descendente (maior valor transformado = rank 1)
  3) Soma os ranks de todos os critérios ativos => score
  4) Penalidade de liquidez:
      se liquidez <= min_liq => score += 1000
  5) Ordena pelo menor score (ASC)

Observações importantes (igual planilha):
- NÃO filtra universo por valores positivos.
  (Se o indicador é 0/NaN/erro, ele só rankeia mal, mas NÃO remove o ativo.)
- Desempate: rank + rank/10000 (como na planilha)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
LIQ_COL = "liquidezmediadiaria"
DEFAULT_MIN_LIQ = 500_000
LIQ_PENALTY = 1000.0

# Cada critério: (db_column, is_lower_better)
# is_lower_better=True  => "Menor"  => usa 1/valor
# is_lower_better=False => "Maior"  => usa valor
Criterion = Tuple[str, bool]

# -----------------------------------------------------------------------------
# Estratégias (iguais às macros da planilha)
# -----------------------------------------------------------------------------
# IMPORTANTE:
# - Os nomes das colunas abaixo precisam existir no seu DF (mesmo lugar que você já usa).
# - Direções ("Menor"/"Maior") aqui seguem o que você mostrou na planilha.
SPREADSHEET_PRESETS: Dict[str, Dict[str, object]] = {
    # Magic: EV/EBIT baixo + ROIC alto
    "magic": {
        "name": "Magic",
        "criteria": [
            ("ev_ebit", True),   # Menor
            ("roic", False),     # Maior
        ],
    },

    # MagicLucros: Magic + CAGR Lucros 5 anos alto
    "magic_lucros": {
        "name": "MagicLucros",
        "criteria": [
            ("ev_ebit", True),      # Menor
            ("roic", False),        # Maior
            ("cagr_lucros", False), # Maior
        ],
    },

    # Baratas (macro liga D19, D21, D22)
    # Queda do Máximo = Maior (como estava no seu dropdown)
    # P/L = Menor
    # P/VP = (na sua planilha estava como "Maior" — mantido p/ bater 1:1)
    "baratas": {
        "name": "Baratas",
        "criteria": [
            ("queda_do_maximo", False),  # Maior
            ("pl", True),               # Menor
            ("pvp", False),             # Maior (como planilha)
        ],
    },

    # Sólidas (macro liga D30, D34, D42)
    # Div. Líq / Patri = Menor
    # ROE = Maior
    # CAGR Lucros = Maior
    "solidas": {
        "name": "Sólidas",
        "criteria": [
            ("div_liq_patri", True),    # Menor
            ("roe", False),             # Maior
            ("cagr_lucros", False),     # Maior
        ],
    },

    # Mix (macro liga D21, D22, D34, D35, D42)
    # P/L = Menor
    # P/VP = Maior (como planilha)
    # ROE = Maior
    # ROA = Maior
    # CAGR Lucros = Maior
    "mix": {
        "name": "Mix",
        "criteria": [
            ("pl", True),               # Menor
            ("pvp", False),             # Maior (como planilha)
            ("roe", False),             # Maior
            ("roa", False),             # Maior
            ("cagr_lucros", False),     # Maior
        ],
    },

    # Dividendos (macro liga D20, D42)
    "dividendos": {
        "name": "Dividendos",
        "criteria": [
            ("dy", False),              # Maior
            ("cagr_lucros", False),     # Maior
        ],
    },

    # Graham (macro não reseta tudo, mas na prática liga P/L e P/VP
    # (mantemos direção conforme dropdown da planilha -> P/VP = Maior)
    "graham": {
        "name": "Graham",
        "criteria": [
            ("pl", True),               # Menor
            ("pvp", False),             # Maior (como planilha)
        ],
    },

    # GreenBla (macro idêntica ao Magic)
    "greenblatt": {
        "name": "GreenBla",
        "criteria": [
            ("ev_ebit", True),
            ("roic", False),
        ],
    },
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _transform_for_ranking(series: pd.Series, is_lower_better: bool) -> pd.Series:
    """
    Transformação igual planilha:
    - Menor é melhor => 1/valor
    - Maior é melhor => valor

    Regras de robustez:
    - Para divisão: valores <= 0 viram NaN (vão para o fim do rank)
    - NaNs ficam no fim do rank
    """
    s = pd.to_numeric(series, errors="coerce")

    if is_lower_better:
        # Planilha: 1/valor. Evitar 1/0 e 1/negativo.
        s = s.where(s > 0, pd.NA)
        return 1.0 / s.astype("float64")
    else:
        return s.astype("float64")


def _rank_desc_with_tiebreak(values: pd.Series) -> pd.Series:
    """
    Rank descendente (maior = rank 1) + desempate rank/10000 igual planilha.
    """
    ranks = values.rank(ascending=False, method="min", na_option="bottom")
    return ranks + (ranks / 10000.0)


def _compute_score(df: pd.DataFrame, criteria: List[Criterion], min_liq: float) -> Tuple[pd.DataFrame, List[str]]:
    """
    Calcula score = soma de ranks dos critérios + penalidade de liquidez.
    Retorna df com coluna _score e lista de caveats.
    """
    caveats: List[str] = []
    out = df.copy()

    out["_score"] = 0.0

    for col, is_lower_better in criteria:
        if col not in out.columns:
            caveats.append(f"Indicador sem coluna no DF: {col}")
            continue

        vals = _transform_for_ranking(out[col], is_lower_better)

        # Se tudo NaN, adiciona caveat e ignora (igual "sem dados")
        if vals.isna().all():
            caveats.append(f"Indicador sem dados úteis (tudo vazio/0): {col}")
            continue

        ranks = _rank_desc_with_tiebreak(vals)
        out["_score"] += ranks

    # Penalidade de liquidez (igual planilha)
    if LIQ_COL in out.columns:
        liq = pd.to_numeric(out[LIQ_COL], errors="coerce").fillna(0)
        out.loc[liq <= float(min_liq), "_score"] += LIQ_PENALTY
    else:
        caveats.append(f"Coluna de liquidez não encontrada: {LIQ_COL} (penalidade não aplicada)")

    return out, caveats


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def apply_spreadsheet_mode(
    df_universe: pd.DataFrame,
    strategy: str,
    min_liq: float = DEFAULT_MIN_LIQ,
    top_n: int = 100,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Aplica ranking modo planilha.

    Args:
        df_universe: DataFrame com o universo de ativos e indicadores.
        strategy: chave da estratégia (magic, magic_lucros, baratas, solidas, mix, dividendos, graham, greenblatt).
        min_liq: liquidez mínima para não tomar penalidade (+1000 se <= min_liq).
        top_n: quantos itens retornar.

    Returns:
        (df_ranked, caveats)
    """
    preset = SPREADSHEET_PRESETS.get(strategy)
    if not preset:
        return df_universe.head(top_n), [f"Estratégia '{strategy}' não encontrada."]

    criteria: List[Criterion] = preset["criteria"]  # type: ignore[assignment]

    df_scored, caveats = _compute_score(df_universe, criteria, min_liq=min_liq)

    # Ordena igual planilha: menor score primeiro
    df_ranked = df_scored.sort_values("_score", ascending=True, kind="mergesort")

    return df_ranked.head(top_n), caveats