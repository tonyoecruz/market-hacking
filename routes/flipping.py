"""
House Flipping Routes
Discovers local real estate agencies, crawls their sites, and analyzes opportunities.
"""
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from modules.house_flipping import SerperAgencyDiscovery, AgencyCrawler, calculate_flipping_opportunity
import pandas as pd
import json
import logging

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def flipping_page(request: Request):
    return templates.TemplateResponse("flipping.html", {"request": request, "title": "House Flipping"})


@router.post("/scan", response_class=HTMLResponse)
async def run_flipping_scan(request: Request, city: str = Form(...)):
    try:
        # Step 1: Discover agencies via Serper.dev
        logger.info(f"[FLIPPING] Starting scan for city: {city}")
        discovery = SerperAgencyDiscovery()
        agencies = await discovery.discover(city)

        if not agencies:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Nenhuma imobiliaria encontrada em '{city}'. Verifique o nome da cidade ou configure a SERPER_API_KEY.",
                "agencies": []
            })

        logger.info(f"[FLIPPING] Found {len(agencies)} agencies, starting crawl...")

        # Step 2: Crawl agencies and extract listings via Crawl4AI + Gemini
        crawler = AgencyCrawler()
        listings = await crawler.crawl_all_agencies(agencies, city)

        # Format agencies for template (compatible with existing partial)
        agencies_for_template = [{"name": a["name"], "site": a["domain"]} for a in agencies]

        if not listings:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Encontramos {len(agencies)} imobiliarias em '{city}', mas nao foi possivel extrair imoveis dos sites. Os sites podem estar bloqueando acesso automatizado.",
                "agencies": agencies_for_template
            })

        # Step 3: Calculate opportunities (UNCHANGED LOGIC)
        df = pd.DataFrame(listings)
        df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
        df['Area (m2)'] = pd.to_numeric(df['Area (m2)'], errors='coerce')
        df = df.dropna(subset=['Valor Total', 'Area (m2)'])

        if df.empty:
            return templates.TemplateResponse("partials/flipping_results.html", {
                "request": request,
                "error": f"Dados extraidos de {len(agencies)} imobiliarias, mas nenhum imovel com preco e area validos.",
                "agencies": agencies_for_template
            })

        df_analyzed = calculate_flipping_opportunity(df)
        results = df_analyzed.to_dict('records')

        # Stats
        agencies_with_data = len(set(r.get("Imobiliaria", "") for r in results))
        stats = {
            "count": len(results),
            "avg_m2": df_analyzed['Valor/m2'].mean() if not df_analyzed.empty else 0,
            "best_deal": results[0] if results else None,
            "agencies_found": len(agencies),
            "agencies_with_data": agencies_with_data
        }

        # Unique property types for filter checkboxes
        tipos_unicos = sorted(df_analyzed['Tipo'].dropna().unique().tolist())

        logger.info(f"[FLIPPING] Scan complete: {len(results)} listings from {agencies_with_data} agencies")

        return templates.TemplateResponse("partials/flipping_results.html", {
            "request": request,
            "results": results,
            "results_json": json.dumps(results, ensure_ascii=False, default=str),
            "agencies": agencies_for_template,
            "stats": stats,
            "tipos": tipos_unicos,
            "city": city
        })

    except Exception as e:
        logger.error(f"[FLIPPING] Scan failed for '{city}': {e}", exc_info=True)
        return templates.TemplateResponse("partials/flipping_results.html", {
            "request": request,
            "error": f"Erro interno durante a varredura: {str(e)}",
            "agencies": []
        })
