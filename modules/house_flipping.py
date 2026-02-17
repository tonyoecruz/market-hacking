import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import random
import time
from urllib.parse import quote

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealEstateScraper:
    """
    Base class for Real Estate Scraping with common utilities.
    """
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def get_soup(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            logger.error(f"Failed to fetch {url}: Status {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

class OLXScraper(RealEstateScraper):
    """
    Targeted scraper for OLX Real Estate listings.
    """
    def search_city(self, city, state="sp"):
        """
        Searches for real estate in a specific city on OLX.
        Note: State is defaulted to SP for MVP, but logic should handle state mapping.
        """
        # Clean city name for URL
        city_slug = city.lower().replace(' ', '-').replace('ã', 'a').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
        
        # Construct Base URL (Simplified for MVP - direct search not always maps perfectly to region subdomains)
        # OLX uses structure: https://www.olx.com.br/imoveis/venda/estado-uf/regiao?q=...
        # A robust way is to use the general search and filter by category.
        
        base_url = f"https://www.olx.com.br/imoveis/venda?q={quote(city)}"
        
        logger.info(f"Scraping OLX for {city}: {base_url}")
        soup = self.get_soup(base_url)
        listings = []
        
        if not soup:
            return []

        # Find listings container using new selectors
        # New OLX Layout uses section.olx-adcard
        items = soup.find_all('section', {'class': lambda x: x and 'olx-adcard' in x})
        
        if not items:
            # Fallback to old selectors just in case
            items = soup.find_all(attrs={"data-ds-component": "DS-AdCard"})
        
        if not items:
             items = soup.select('ul#ad-list > li')

        for item in items:
            try:
                # Extract Link
                link_tag = item.find('a', {'class': lambda x: x and 'olx-adcard__link' in x})
                if not link_tag: 
                    link_tag = item.find('a', href=True) # Fallback
                
                if not link_tag: continue
                link = link_tag['href']
                
                # Extract Title
                title_tag = item.find('h2', {'class': lambda x: x and 'olx-adcard__title' in x})
                if not title_tag: title_tag = item.find('h2')
                title = title_tag.text.strip() if title_tag else "Imóvel Sem Título"
                
                # Extract Price
                price_tag = item.find('h3', {'class': lambda x: x and 'olx-adcard__price' in x})
                if not price_tag: price_tag = item.find(string=lambda x: x and "R$" in x)
                
                price = 0.0
                if price_tag:
                    price_text = price_tag.text if hasattr(price_tag, 'text') else price_tag
                    price_str = price_text.strip().replace('R$', '').replace('.', '').strip()
                    if price_str.isdigit():
                         price = float(price_str)
                
                # Extract Area (m²)
                area = 0.0
                # Look for details class
                details = item.find_all(class_=lambda x: x and 'olx-adcard__detail' in x)
                for detail in details:
                    text = detail.text.strip()
                    if "m²" in text:
                         area_str = text.replace('m²', '').strip()
                         if area_str.isdigit():
                             area = float(area_str)
                             break
                
                # Fallback Area
                if area == 0:
                     area_text = item.find(string=lambda x: x and "m²" in x)
                     if area_text:
                        area_str = area_text.replace('m²', '').strip()
                        if area_str.isdigit():
                            area = float(area_str)

                # Extract Location (Bairro/City)
                location_tag = item.find('p', {'class': lambda x: x and 'olx-adcard__location' in x})
                location = location_tag.text if location_tag else "N/A"
                
                # Heuristic Type deduction
                itype = "Outro"
                title_lower = title.lower()
                if "casa" in title_lower: itype = "Casa"
                elif "apartamento" in title_lower or "apto" in title_lower: itype = "Apartamento"
                elif "terreno" in title_lower or "lote" in title_lower: itype = "Terreno"
                elif "chácara" in title_lower or "sítio" in title_lower: itype = "Sítio/Chácara"

                if price > 0 and area > 0:
                     listings.append({
                         'Cidade': city,
                         'Imobiliária': 'OLX Aggregator',
                         'Bairro': location.split('-')[0].strip(),
                         'Tipo': itype,
                         'Referência': link.split('-')[-1],
                         'Área (m²)': area,
                         'Valor Total': price,
                         'Link': link
                     })

            except Exception as e:
                # logger.warning(f"Error parsing item: {e}")
                continue
                
        return listings

class AgencyFinder:
    """
    Finds agencies in a city to satisfy requirement of "identifying agencies".
    """
    def find_agencies(self, city):
        query = f"imobiliárias em {city}"
        # For MVP, returning a static list or mocked search results to avoid Google blocking
        return [
            {"name": f"Imobiliária {city} Central", "site": f"www.imob{city.lower()}1.com.br"},
            {"name": "ReMax Top", "site": "www.remax.com.br"},
            {"name": "Lopes", "site": "www.lopes.com.br"}
        ]

def calculate_flipping_opportunity(df):
    """
    Pandas engine to process real estate data.
    """
    if df.empty: return df
    
    # 1. Calculate Price/m2
    df['Valor/m²'] = df['Valor Total'] / df['Área (m²)']
    
    # 2. Calculate Sector Mean (Grouping by Bairro + Tipo)
    # Using 'transform' to map back to original rows
    df['Média Setor (m²)'] = df.groupby(['Bairro', 'Tipo'])['Valor/m²'].transform('mean')
    
    # 3. Calculate Diff vs Mean (%)
    df['Dif vs Med (%)'] = ((df['Valor/m²'] - df['Média Setor (m²)']) / df['Média Setor (m²)']) * 100
    
    # Format for display
    df['Dif vs Med (%)'] = df['Dif vs Med (%)'].round(2)
    df['Valor/m²'] = df['Valor/m²'].round(2)
    df['Média Setor (m²)'] = df['Média Setor (m²)'].round(2)
    
    # Sort by 'Best Deal' (Most negative diff)
    df = df.sort_values('Dif vs Med (%)', ascending=True)
    
    return df
