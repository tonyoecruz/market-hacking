
from modules.house_flipping import OLXScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_module_scraping():
    logger.info("Testing OLXScraper Module...")
    scraper = OLXScraper()
    listings = scraper.search_city("Sorocaba")
    
    logger.info(f"Found {len(listings)} listings via Module")
    for item in listings[:3]:
        logger.info(f"{item['Tipo']} | {item['Bairro']} | {item['Valor Total']} | {item['Área (m²)']}")

if __name__ == "__main__":
    # test_local_parsing()
    test_module_scraping()
