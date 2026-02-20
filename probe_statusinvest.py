
import requests
import json
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://statusinvest.com.br/acoes/busca-avancada",
    "Origin": "https://statusinvest.com.br",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
}

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

def probe():
    url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
    params = {
        "search": SEARCH_FILTER_STOCKS,
        "CategoryType": 1,
        "take": 10,
        "skip": 0,
    }
    r = requests.get(url, params=params, headers=HEADERS, verify=False)
    data = r.json()
    items = data.get('list', [])
    if items:
        df = pd.DataFrame(items)
        print("Columns returned by StatusInvest:")
        print(sorted(df.columns.tolist()))
        print("\nFirst row sample:")
        print(items[0])

if __name__ == "__main__":
    probe()
