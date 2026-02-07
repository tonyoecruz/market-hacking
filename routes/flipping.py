from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from modules.house_flipping import OLXScraper, AgencyFinder, calculate_flipping_opportunity
import pandas as pd
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def flipping_page(request: Request):
    return templates.TemplateResponse("flipping.html", {"request": request, "title": "House Flipping"})

@router.post("/scan", response_class=HTMLResponse)
async def run_flipping_scan(request: Request, city: str = Form(...)):
    # 1. Agencies
    finder = AgencyFinder()
    agencies = finder.find_agencies(city)
    
    # 2. Scrape
    scraper = OLXScraper()
    listings = scraper.search_city(city)
    
    if not listings:
        return templates.TemplateResponse("partials/flipping_results.html", {
            "request": request, 
            "error": "Nenhum imóvel encontrado ou bloqueio detectado.",
            "agencies": agencies
        })

    # 3. Calculate
    df = pd.DataFrame(listings)
    # Ensure numeric
    df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
    df['Área (m²)'] = pd.to_numeric(df['Área (m²)'], errors='coerce')
    df = df.dropna(subset=['Valor Total', 'Área (m²)'])
    
    df_analyzed = calculate_flipping_opportunity(df)
    
    # Limit for display
    results = df_analyzed.to_dict('records')
    
    # Stats
    stats = {
        "count": len(results),
        "avg_m2": df_analyzed['Valor/m²'].mean() if not df_analyzed.empty else 0,
        "best_deal": results[0] if results else None
    }

    return templates.TemplateResponse("partials/flipping_results.html", {
        "request": request,
        "results": results,
        "agencies": agencies,
        "stats": stats,
        "city": city
    })
