"""
House Flipping - Intelligent Real Estate Opportunity Finder
Pipeline: Serper.dev (agency discovery) -> httpx (site fetching) -> Gemini (data extraction) -> Pandas (analysis)
"""
import httpx
import pandas as pd
import logging
import asyncio
import json
import os
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

BLOCKED_DOMAINS = [
    "olx.com.br", "mercadolivre.com.br", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "youtube.com", "linkedin.com",
    "zapimoveis.com.br", "vivareal.com.br", "imovelweb.com.br",
    "quintoandar.com.br", "chaves-na-mao.com.br", "123i.com.br",
    "google.com", "reclameaqui.com.br", "jusbrasil.com.br",
    "wikipedia.org", "tiktok.com", "pinterest.com", "tripadvisor.com",
    "glassdoor.com", "indeed.com", "gov.br", "creci.org.br",
]

LISTING_URL_PATTERNS = [
    "/imoveis", "/venda", "/comprar", "/casas", "/apartamentos",
    "/imoveis-a-venda", "/imoveis/venda", "/compra", "/lancamentos",
]


# ==================== STEP 1: AGENCY DISCOVERY (Serper.dev) ====================

class SerperAgencyDiscovery:
    """
    Discovers local real estate agencies in a city using Serper.dev Google Search API.
    Returns a list of agency websites filtered from marketplaces and social media.
    """

    def __init__(self):
        self.api_key = os.getenv("SERPER_API_KEY", "")
        self.base_url = "https://google.serper.dev/search"

    async def discover(self, city: str, state: str = None) -> list:
        """
        Search for real estate agencies in a city.
        Returns: [{"name": str, "domain": str, "url": str}]
        """
        if not self.api_key:
            logger.error("[SERPER] SERPER_API_KEY not configured")
            return []

        query = f"Imobiliarias em {city}"
        if state:
            query += f" - {state}"

        logger.info(f"[SERPER] Searching: {query}")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "q": query,
                        "gl": "br",
                        "hl": "pt-br",
                        "num": 20
                    }
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[SERPER] API error: {e.response.status_code} - {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"[SERPER] Request failed: {e}")
            return []

        agencies = []
        seen_domains = set()

        for result in data.get("organic", []):
            url = result.get("link", "")
            if not url:
                continue

            domain = urlparse(url).netloc.replace("www.", "").lower()

            if domain in seen_domains:
                continue

            if any(blocked in domain for blocked in BLOCKED_DOMAINS):
                continue

            seen_domains.add(domain)
            agencies.append({
                "name": result.get("title", domain).split(" - ")[0].split(" | ")[0].strip(),
                "domain": domain,
                "url": url
            })

        logger.info(f"[SERPER] Found {len(agencies)} agencies for '{city}'")
        return agencies


# ==================== STEP 2: LIGHTWEIGHT HTTP CRAWLING + LLM EXTRACTION ====================

# Common User-Agent to avoid being blocked
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _html_to_text(html: str) -> str:
    """
    Lightweight HTML-to-text conversion. Strips scripts, styles and tags,
    preserving meaningful text content for LLM extraction.
    No external dependencies required.
    """
    # Remove script and style blocks entirely
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<noscript[^>]*>.*?</noscript>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    # Preserve <a href="..."> links as "text (URL)" so the LLM can extract them
    text = re.sub(
        r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'\2 (\1)',
        text, flags=re.DOTALL | re.IGNORECASE
    )
    # Replace <br>, <p>, <div>, <li>, <tr> with newlines for readability
    text = re.sub(r'<(?:br|p|div|li|tr|h[1-6])[^>]*/?>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'&\w+;', ' ', text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()


class AgencyCrawler:
    """
    Fetches real estate agency websites using httpx (no browser needed) and extracts
    structured listing data using Google Gemini LLM.
    Lightweight: no Playwright/Chromium dependency, works on any hosting platform.
    """

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_KEY", "") or os.getenv("GEMINI_API_KEY", "")

    def _get_gemini_model(self):
        """Initialize Gemini model (lazy load to avoid import-time side effects)"""
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_api_key)
        return genai.GenerativeModel("gemini-2.0-flash")

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch a single page and return cleaned text content."""
        try:
            logger.info(f"[CRAWL] Fetching: {url}")
            response = await client.get(url, headers=_HTTP_HEADERS, follow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.info(f"[CRAWL] Skipping {url} - not HTML (content-type: {content_type})")
                return ""

            html = response.text
            if len(html) < 500:
                logger.info(f"[CRAWL] Skipping {url} - HTML too short ({len(html)} chars)")
                return ""

            text = _html_to_text(html)

            if len(text) < 200:
                logger.info(f"[CRAWL] Skipping {url} - extracted text too short ({len(text)} chars)")
                return ""

            logger.info(f"[CRAWL] Got {len(text)} chars of text from {url}")
            return text

        except httpx.HTTPStatusError as e:
            logger.info(f"[CRAWL] HTTP {e.response.status_code} for {url}")
            return ""
        except httpx.ConnectError:
            logger.info(f"[CRAWL] Connection failed for {url}")
            return ""
        except httpx.TimeoutException:
            logger.info(f"[CRAWL] Timeout for {url}")
            return ""
        except Exception as e:
            logger.warning(f"[CRAWL] Error fetching {url}: {e}")
            return ""

    async def crawl_agency(self, agency: dict, city: str, max_pages: int = 2, is_capital: bool = False) -> list:
        """
        Fetch agency site pages via HTTP and extract structured listings.
        Returns list of dicts matching the expected DataFrame schema.
        """
        base_url = agency["url"]
        domain_root = f"https://{agency['domain']}"
        all_listings = []

        # Build candidate URLs to try (homepage + listing patterns)
        urls_to_try = [base_url]
        for pattern in LISTING_URL_PATTERNS:
            candidate = f"{domain_root}{pattern}"
            if candidate != base_url:
                urls_to_try.append(candidate)

        async with httpx.AsyncClient(timeout=12, verify=False) as client:
            pages_crawled = 0
            for url in urls_to_try:
                if pages_crawled >= max_pages:
                    break

                text = await self._fetch_page(client, url)
                if not text:
                    continue

                listings = await self._extract_with_gemini(text, city, agency["name"], domain_root, is_capital)
                if listings:
                    all_listings.extend(listings)
                    pages_crawled += 1
                    logger.info(f"[CRAWL] Extracted {len(listings)} listings from {url}")
                    # If we got listings from first page, skip trying more URLs
                    if pages_crawled >= 1 and len(all_listings) >= 5:
                        break
                else:
                    logger.info(f"[CRAWL] No listings found on {url}")

                await asyncio.sleep(0.3)

        logger.info(f"[CRAWL] Total: {len(all_listings)} listings from {agency['name']}")
        return all_listings

    async def _extract_with_gemini(self, page_text: str, city: str, agency_name: str, base_domain: str = "", is_capital: bool = False) -> list:
        """
        Send page text to Gemini and extract structured listing data.
        """
        if not self.gemini_api_key:
            logger.error("[GEMINI] No API key configured (GEMINI_KEY or GEMINI_API_KEY)")
            return []

        # Truncate to avoid token limits
        content = page_text[:15000]

        # Build region field instruction for capitals
        regiao_field = ""
        if is_capital:
            regiao_field = f"""- "Regiao": classifique em qual regiao da cidade de {city} o bairro esta localizado. Use exatamente um de: "Norte", "Sul", "Leste", "Oeste", "Centro". Baseie-se na geografia conhecida da cidade (string)\n"""

        prompt = f"""Analise o conteudo abaixo de um site de imobiliaria e extraia TODOS os imoveis a venda listados.

Para cada imovel, extraia exatamente estes campos em JSON:
- "Bairro": nome do bairro ou localizacao (string). Se nao encontrar, use "N/A"
- "Tipo": tipo do imovel - deve ser exatamente um de: "Casa", "Apartamento", "Terreno", "Sitio/Chacara", "Comercial", "Outro" (string)
- "Referencia": codigo de referencia do imovel se disponivel, senao string vazia (string)
- "Area": area em metros quadrados, apenas o numero (float). Ex: 120.0
- "Valor": valor total em reais, apenas o numero sem pontos de milhar (float). Ex: 350000.0
- "Link": URL do anuncio individual do imovel, se disponivel no texto entre parenteses (ex: https://site.com/imovel/123). Se nao encontrar, use string vazia (string)
{regiao_field}
Regras OBRIGATORIAS:
1. SOMENTE inclua imoveis que tenham Area > 0 E Valor > 0 (ambos obrigatorios)
2. Se nao encontrar nenhum imovel valido, retorne: []
3. Retorne APENAS o array JSON puro, sem texto adicional, sem markdown code blocks, sem explicacoes
4. Considere apenas imoveis na cidade de {city} ou regiao proxima
5. Converta valores como "R$ 350.000" para 350000.0 e "120 m2" para 120.0

Conteudo do site da imobiliaria "{agency_name}":
{content}"""

        try:
            model = self._get_gemini_model()
            response = await asyncio.to_thread(model.generate_content, prompt)
            text = response.text.strip()

            # Clean up Gemini response (may wrap in code blocks)
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            if not text or text == "[]":
                return []

            listings_raw = json.loads(text)

            if not isinstance(listings_raw, list):
                return []

            # Normalize to expected DataFrame schema
            normalized = []
            for item in listings_raw:
                try:
                    area = float(item.get("Area", 0))
                    valor = float(item.get("Valor", 0))

                    if area <= 0 or valor <= 0:
                        continue

                    # Resolve relative URLs
                    raw_link = str(item.get("Link", "")).strip()
                    if raw_link and raw_link.startswith("/") and base_domain:
                        raw_link = base_domain.rstrip("/") + raw_link

                    entry = {
                        "Cidade": city,
                        "Imobiliaria": agency_name,
                        "Bairro": str(item.get("Bairro", "N/A")).strip(),
                        "Tipo": str(item.get("Tipo", "Outro")).strip(),
                        "Referencia": str(item.get("Referencia", "")),
                        "Area (m2)": area,
                        "Valor Total": valor,
                        "Link": raw_link,
                    }
                    if is_capital:
                        entry["Regiao"] = str(item.get("Regiao", "")).strip()
                    normalized.append(entry)
                except (ValueError, TypeError):
                    continue

            return normalized

        except json.JSONDecodeError as e:
            logger.warning(f"[GEMINI] Invalid JSON from {agency_name}: {e}")
            return []
        except Exception as e:
            logger.warning(f"[GEMINI] Extraction failed for {agency_name}: {e}")
            return []

    async def crawl_all_agencies(self, agencies: list, city: str, max_agencies: int = 8, is_capital: bool = False) -> list:
        """
        Crawl multiple agencies sequentially with rate limiting.
        Returns combined list of all extracted listings.
        """
        all_listings = []

        for i, agency in enumerate(agencies[:max_agencies]):
            logger.info(f"[CRAWL] Agency {i+1}/{min(len(agencies), max_agencies)}: {agency['name']} ({agency['domain']})")

            try:
                listings = await self.crawl_agency(agency, city, is_capital=is_capital)
                all_listings.extend(listings)
            except Exception as e:
                logger.error(f"[CRAWL] Agency '{agency['name']}' failed: {e}")
                continue

            # Rate limit between agencies
            if i < min(len(agencies), max_agencies) - 1:
                await asyncio.sleep(1.0)

        logger.info(f"[CRAWL] Pipeline complete: {len(all_listings)} total listings from {len(agencies)} agencies")
        return all_listings


# ==================== STEP 3: ANALYSIS (unchanged) ====================

def calculate_flipping_opportunity(df):
    """
    Pandas engine to process real estate data.
    Calculates price/m2, sector average, difference vs average,
    and full profitability analysis (costs, estimated sale value, profit).

    Cost Structure:
      - ITBI + Registration: 6% of property value
      - Renovation: 15% of property value
      - 6-month Maintenance: Condo fee × 6 (if available)
      - Total Cost = Property Value + All Above

    Profit Calculation:
      - Estimated Sale = Average $/m² (by Bairro+Tipo) × Property Area
      - Profit R$ = Sale − Total Cost
      - Profit % = (Profit / Total Cost) × 100
    """
    if df.empty:
        return df

    # 1. Calculate Price/m2
    df['Valor/m2'] = df['Valor Total'] / df['Area (m2)']

    # 2. Calculate Sector Mean (Grouping by Bairro + Tipo)
    df['Media Setor (m2)'] = df.groupby(['Bairro', 'Tipo'])['Valor/m2'].transform('mean')

    # 3. Calculate Diff vs Mean (%)
    df['Dif vs Med (%)'] = ((df['Valor/m2'] - df['Media Setor (m2)']) / df['Media Setor (m2)']) * 100

    # ── PROFITABILITY ANALYSIS ──────────────────────────────────────────

    # 4. Costs
    df['Custo ITBI'] = (df['Valor Total'] * 0.06).round(2)        # 6% ITBI + Registro
    df['Custo Reforma'] = (df['Valor Total'] * 0.15).round(2)     # 15% Reforma

    # Condomínio × 6 (if column exists and has data)
    if 'Condominio' in df.columns:
        df['Condominio'] = pd.to_numeric(df['Condominio'], errors='coerce').fillna(0)
        df['Custo Manutencao'] = (df['Condominio'] * 6).round(2)
    else:
        df['Custo Manutencao'] = 0.0

    df['Custo Total'] = (
        df['Valor Total'] + df['Custo ITBI'] + df['Custo Reforma'] + df['Custo Manutencao']
    ).round(2)

    # 5. Estimated Sale Value = Average $/m² in the region/type × property area
    df['Valor Venda Est'] = (df['Media Setor (m2)'] * df['Area (m2)']).round(2)

    # 6. Profit
    df['Lucro R$'] = (df['Valor Venda Est'] - df['Custo Total']).round(2)
    df['Lucro %'] = ((df['Lucro R$'] / df['Custo Total']) * 100).round(2)

    # Format for display
    df['Dif vs Med (%)'] = df['Dif vs Med (%)'].round(2)
    df['Valor/m2'] = df['Valor/m2'].round(2)
    df['Media Setor (m2)'] = df['Media Setor (m2)'].round(2)

    # Sort by 'Best Deal' (Most negative diff = best opportunity)
    df = df.sort_values('Dif vs Med (%)', ascending=True)

    return df
