"""
House Flipping Routes
Discovers local real estate agencies, crawls their sites, and analyzes opportunities.
Results are cached in the database for fast repeat access.
"""
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from modules.house_flipping import SerperAgencyDiscovery, AgencyCrawler, calculate_flipping_opportunity
from database.db_manager import DatabaseManager
import pandas as pd
import json
import logging
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)
db = DatabaseManager()

# ==================== BRAZILIAN CONSTANTS ====================

BRAZILIAN_STATES = [
    ("AC", "Acre"), ("AL", "Alagoas"), ("AM", "Amazonas"), ("AP", "Amapa"),
    ("BA", "Bahia"), ("CE", "Ceara"), ("DF", "Distrito Federal"), ("ES", "Espirito Santo"),
    ("GO", "Goias"), ("MA", "Maranhao"), ("MG", "Minas Gerais"), ("MS", "Mato Grosso do Sul"),
    ("MT", "Mato Grosso"), ("PA", "Para"), ("PB", "Paraiba"), ("PE", "Pernambuco"),
    ("PI", "Piaui"), ("PR", "Parana"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
    ("RO", "Rondonia"), ("RR", "Roraima"), ("RS", "Rio Grande do Sul"), ("SC", "Santa Catarina"),
    ("SE", "Sergipe"), ("SP", "Sao Paulo"), ("TO", "Tocantins"),
]

CAPITALS_BY_STATE = {
    "AC": "Rio Branco", "AL": "Maceio", "AM": "Manaus", "AP": "Macapa",
    "BA": "Salvador", "CE": "Fortaleza", "DF": "Brasilia", "ES": "Vitoria",
    "GO": "Goiania", "MA": "Sao Luis", "MG": "Belo Horizonte", "MS": "Campo Grande",
    "MT": "Cuiaba", "PA": "Belem", "PB": "Joao Pessoa", "PE": "Recife",
    "PI": "Teresina", "PR": "Curitiba", "RJ": "Rio De Janeiro", "RN": "Natal",
    "RO": "Porto Velho", "RR": "Boa Vista", "RS": "Porto Alegre", "SC": "Florianopolis",
    "SE": "Aracaju", "SP": "Sao Paulo", "TO": "Palmas",
}

# Set of capital names (title-cased) for fast lookup
_CAPITAL_NAMES = {v.strip().title() for v in CAPITALS_BY_STATE.values()}


def _is_capital(city_norm: str) -> bool:
    """Check if a city (title-cased) is a Brazilian state capital"""
    return city_norm in _CAPITAL_NAMES


# ==================== ROUTES ====================

@router.get("/", response_class=HTMLResponse)
async def flipping_page(request: Request):
    return templates.TemplateResponse("flipping.html", {
        "request": request,
        "title": "House Flipping",
        "states": BRAZILIAN_STATES,
        "capitals": CAPITALS_BY_STATE,
    })


@router.get("/api/cities")
async def get_monitored_cities():
    """Return list of cities that have been scanned (for autocomplete)"""
    cities = db.get_flipping_cities()
    return {"cities": [{"city": c["city"], "state": c.get("state", "")} for c in cities]}


def _build_response(request, results, agencies_for_template, city, is_capital_city=False):
    """Build the template response from results list"""
    tipos_unicos = sorted(set(r.get("Tipo", "Outro") for r in results))
    agencies_with_data = len(set(r.get("Imobiliaria", "") for r in results))

    # Calculate avg_m2 from results
    valores_m2 = [r["Valor/m2"] for r in results if r.get("Valor/m2")]
    avg_m2 = sum(valores_m2) / len(valores_m2) if valores_m2 else 0

    stats = {
        "count": len(results),
        "avg_m2": avg_m2,
        "best_deal": results[0] if results else None,
        "agencies_found": len(agencies_for_template),
        "agencies_with_data": agencies_with_data,
    }

    # Collect unique regions for capitals
    regioes = []
    if is_capital_city:
        regioes = sorted(set(r.get("Regiao", "") for r in results if r.get("Regiao")))

    return templates.TemplateResponse("partials/flipping_results.html", {
        "request": request,
        "results": results,
        "results_json": json.dumps(results, ensure_ascii=False, default=str),
        "agencies": agencies_for_template,
        "stats": stats,
        "tipos": tipos_unicos,
        "city": city,
        "is_capital": is_capital_city,
        "regioes": regioes,
    })


@router.post("/scan", response_class=HTMLResponse)
async def run_flipping_scan(
    request: Request,
    city: str = Form(...),
    state: str = Form(""),
    region: str = Form(""),
):
    try:
        city_norm = city.strip().title()
        state_norm = state.strip().upper() if state else ""
        region_norm = region.strip() if region else ""
        is_capital_city = _is_capital(city_norm)

        logger.info(f"[FLIPPING] Scan requested for: {city_norm} ({state_norm}), region={region_norm}, capital={is_capital_city}")

        # Always update last_accessed_at (even on cache hit)
        db.touch_flipping_city(city_norm)

        # ── Check cache first ──────────────────────────────────────────
        last_update = db.get_flipping_last_update(city_norm)

        # Get update interval from settings (default: 1 day)
        interval_days = int(db.get_setting("flipping_update_interval_days", "1"))
        cache_valid = (
            last_update is not None
            and (datetime.now() - last_update) < timedelta(days=interval_days)
        )

        if cache_valid:
            logger.info(f"[FLIPPING] Cache hit for '{city_norm}' (last update: {last_update})")
            cached = db.get_flipping_listings(city_norm)
            if cached:
                return _build_response(request, cached, [], city_norm, is_capital_city)

        # ── Cache miss → full scan ─────────────────────────────────────
        logger.info(f"[FLIPPING] Cache miss for '{city_norm}', starting full scan...")

        # Step 1: Discover agencies
        discovery = SerperAgencyDiscovery()
        agencies = await discovery.discover(city_norm, state=state_norm or None)

        if not agencies:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Nenhuma imobiliaria encontrada em '{city_norm}'. Verifique o nome da cidade.",
                "agencies": [],
                "is_capital": is_capital_city,
                "regioes": [],
            })

        logger.info(f"[FLIPPING] Found {len(agencies)} agencies, starting crawl...")

        # Step 2: Crawl agencies
        crawler = AgencyCrawler()
        listings = await crawler.crawl_all_agencies(agencies, city_norm, is_capital=is_capital_city)

        agencies_for_template = [{"name": a["name"], "site": a["domain"]} for a in agencies]

        if not listings:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Encontramos {len(agencies)} imobiliarias em '{city_norm}', mas nao foi possivel extrair imoveis dos sites.",
                "agencies": agencies_for_template,
                "is_capital": is_capital_city,
                "regioes": [],
            })

        # Step 3: Calculate opportunities
        df = pd.DataFrame(listings)
        df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
        df['Area (m2)'] = pd.to_numeric(df['Area (m2)'], errors='coerce')
        df = df.dropna(subset=['Valor Total', 'Area (m2)'])

        if df.empty:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Dados extraidos de {len(agencies)} imobiliarias, mas nenhum imovel com preco e area validos.",
                "agencies": agencies_for_template,
                "is_capital": is_capital_city,
                "regioes": [],
            })

        df_analyzed = calculate_flipping_opportunity(df)
        results = df_analyzed.to_dict('records')

        # Step 4: Save to cache
        db.save_flipping_listings(city_norm, results, state=state_norm or None)
        logger.info(f"[FLIPPING] Saved {len(results)} listings to cache for '{city_norm}'")

        return _build_response(request, results, agencies_for_template, city_norm, is_capital_city)

    except Exception as e:
        logger.error(f"[FLIPPING] Scan failed for '{city}': {e}", exc_info=True)
        return templates.TemplateResponse("partials/flipping_results.html", {
            "request": request,
            "error": f"Erro interno durante a varredura: {str(e)}",
            "agencies": [],
            "is_capital": False,
            "regioes": [],
        })
