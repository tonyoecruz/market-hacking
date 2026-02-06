"""
Data Updater - Market data fetching and database storage
"""
import logging
from datetime import datetime
import pandas as pd
import os
import importlib.util

# CORREÇÃO: Importar a Classe para evitar conflito com o nome do arquivo
from database.db_manager import DatabaseManager

# Import data_utils dinamicamente
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

logger = logging.getLogger(__name__)
db = DatabaseManager() # Instância para salvar os dados

def update_stocks_br():
    """Update Brazilian stocks data"""
    try:
        logger.info("Updating BR stocks...")
        data = data_utils.scan_br_stocks() # Assume que esta função existe no seu data_utils
        if data:
            db.save_stocks(data, market='BR')
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating BR stocks: {e}")
        return False

def update_stocks_us():
    """Update US stocks data"""
    try:
        logger.info("Updating US stocks...")
        data = data_utils.scan_us_stocks()
        if data:
            db.save_stocks(data, market='US')
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating US stocks: {e}")
        return False

def update_fiis():
    """Update FIIs data"""
    try:
        logger.info("Updating FIIs...")
        data = data_utils.scan_fiis()
        if data:
            db.save_fiis(data)
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating FIIs: {e}")
        return False

def update_etfs():
    """Update ETFs data"""
    try:
        logger.info("Updating ETFs...")
        data = data_utils.scan_etfs()
        if data:
            db.save_etfs(data)
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating ETFs: {e}")
        return False

def update_all_data():
    """Run all market data updates"""
    logger.info("="*80)
    logger.info(f"🔄 Starting complete market update at {datetime.now()}")
    logger.info("="*80)
    
    results = {}
    
    # Update BR Stocks
    try:
        logger.info("📊 [1/4] Updating Brazilian stocks...")
        results['stocks_br'] = update_stocks_br()
        logger.info(f"✅ BR Stocks: {'SUCCESS' if results['stocks_br'] else 'FAILED'}")
    except Exception as e:
        logger.error(f"❌ BR Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_br'] = False
    
    # Update US Stocks
    try:
        logger.info("📊 [2/4] Updating US stocks...")
        results['stocks_us'] = update_stocks_us()
        logger.info(f"✅ US Stocks: {'SUCCESS' if results['stocks_us'] else 'FAILED'}")
    except Exception as e:
        logger.error(f"❌ US Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_us'] = False
    
    # Update FIIs
    try:
        logger.info("📊 [3/4] Updating FIIs...")
        results['fiis'] = update_fiis()
        logger.info(f"✅ FIIs: {'SUCCESS' if results['fiis'] else 'FAILED'}")
    except Exception as e:
        logger.error(f"❌ FIIs ERROR: {str(e)}", exc_info=True)
        results['fiis'] = False
    
    # Update ETFs
    try:
        logger.info("📊 [4/4] Updating ETFs...")
        results['etfs'] = update_etfs()
        logger.info(f"✅ ETFs: {'SUCCESS' if results['etfs'] else 'FAILED'}")
    except Exception as e:
        logger.error(f"❌ ETFs ERROR: {str(e)}", exc_info=True)
        results['etfs'] = False
    
    # Log results to database
    try:
        db.log_update(results)
        logger.info("📝 Results logged to database")
    except Exception as e:
        logger.error(f"❌ Failed to log results: {str(e)}", exc_info=True)
    
    logger.info("="*80)
    logger.info(f"✅ Update cycle finished. Results: {results}")
    logger.info("="*80)

def cleanup_old_logs():
    """Remove old update logs"""
    db.cleanup_logs(days=7)