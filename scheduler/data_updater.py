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
    logger.info(f"🔄 Starting complete market update at {datetime.now()}")
    
    results = {
        'stocks_br': update_stocks_br(),
        'stocks_us': update_stocks_us(),
        'fiis': update_fiis(),
        'etfs': update_etfs()
    }
    
    # Registra o log da operação no banco
    db.log_update(results)
    logger.info(f"✅ Update cycle finished. Results: {results}")

def cleanup_old_logs():
    """Remove old update logs"""
    db.cleanup_logs(days=7)