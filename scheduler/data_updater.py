"""
Data Updater - Background jobs for automatic market data updates
Runs hourly to keep database fresh with latest market data
"""
import sys
import os
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import data utilities
import importlib.util
spec = importlib.util.spec_from_file_location("data_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_utils.py"))
data_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_utils)

from database.db_manager import db_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_stocks_br():
    """Update Brazilian stocks data"""
    logger.info("🇧🇷 Starting Brazilian stocks update...")
    started_at = datetime.now()
    
    try:
        # Load data from Fundamentus
        df = data_utils.load_data_acoes_pipeline(['🇧🇷 Brasil (B3)'])
        
        if df is not None and not df.empty:
            # Save to database
            count = db_manager.save_stocks(df, market='BR')
            completed_at = datetime.now()
            
            # Log success
            db_manager.log_update(
                asset_type='stocks',
                market='BR',
                status='success',
                records_updated=count,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"✅ Brazilian stocks updated: {count} records")
            return count
        else:
            raise Exception("No data returned from pipeline")
            
    except Exception as e:
        completed_at = datetime.now()
        error_msg = str(e)
        
        # Log error
        db_manager.log_update(
            asset_type='stocks',
            market='BR',
            status='error',
            error_message=error_msg,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.error(f"❌ Error updating Brazilian stocks: {error_msg}")
        return 0


def update_stocks_us():
    """Update US stocks data"""
    logger.info("🇺🇸 Starting US stocks update...")
    started_at = datetime.now()
    
    try:
        # Load data from TradingView
        df = data_utils.load_data_acoes_pipeline(['🇺🇸 Estados Unidos (NYSE/NASDAQ)'])
        
        if df is not None and not df.empty:
            # Save to database
            count = db_manager.save_stocks(df, market='US')
            completed_at = datetime.now()
            
            # Log success
            db_manager.log_update(
                asset_type='stocks',
                market='US',
                status='success',
                records_updated=count,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"✅ US stocks updated: {count} records")
            return count
        else:
            raise Exception("No data returned from pipeline")
            
    except Exception as e:
        completed_at = datetime.now()
        error_msg = str(e)
        
        # Log error
        db_manager.log_update(
            asset_type='stocks',
            market='US',
            status='error',
            error_message=error_msg,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.error(f"❌ Error updating US stocks: {error_msg}")
        return 0


def update_etfs():
    """Update ETFs data (BR + US)"""
    logger.info("📊 Starting ETFs update...")
    started_at = datetime.now()
    total_count = 0
    
    try:
        # Update Brazilian ETFs
        df_br = data_utils.load_data_etfs_pipeline(['🇧🇷 Brasil (B3)'])
        if df_br is not None and not df_br.empty:
            count_br = db_manager.save_etfs(df_br, market='BR')
            total_count += count_br
            logger.info(f"  ✅ Brazilian ETFs: {count_br} records")
        
        # Update US ETFs
        df_us = data_utils.load_data_etfs_pipeline(['🇺🇸 Estados Unidos (NYSE/NASDAQ)'])
        if df_us is not None and not df_us.empty:
            count_us = db_manager.save_etfs(df_us, market='US')
            total_count += count_us
            logger.info(f"  ✅ US ETFs: {count_us} records")
        
        completed_at = datetime.now()
        
        # Log success
        db_manager.log_update(
            asset_type='etfs',
            market='ALL',
            status='success',
            records_updated=total_count,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.info(f"✅ ETFs updated: {total_count} total records")
        return total_count
        
    except Exception as e:
        completed_at = datetime.now()
        error_msg = str(e)
        
        # Log error
        db_manager.log_update(
            asset_type='etfs',
            market='ALL',
            status='error',
            error_message=error_msg,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.error(f"❌ Error updating ETFs: {error_msg}")
        return 0


def update_fiis():
    """Update FIIs data"""
    logger.info("🏢 Starting FIIs update...")
    started_at = datetime.now()
    
    try:
        # Load FIIs data
        df = data_utils.load_data_fiis_pipeline(['🇧🇷 Brasil (B3)'])
        
        if df is not None and not df.empty:
            # Save to database
            count = db_manager.save_fiis(df, market='BR')
            completed_at = datetime.now()
            
            # Log success
            db_manager.log_update(
                asset_type='fiis',
                market='BR',
                status='success',
                records_updated=count,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"✅ FIIs updated: {count} records")
            return count
        else:
            raise Exception("No data returned from pipeline")
            
    except Exception as e:
        completed_at = datetime.now()
        error_msg = str(e)
        
        # Log error
        db_manager.log_update(
            asset_type='fiis',
            market='BR',
            status='error',
            error_message=error_msg,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.error(f"❌ Error updating FIIs: {error_msg}")
        return 0


def update_all_data():
    """Update all market data (stocks, ETFs, FIIs)"""
    logger.info("🚀 Starting full market data update...")
    start_time = datetime.now()
    
    # Update all asset types
    stocks_br = update_stocks_br()
    stocks_us = update_stocks_us()
    etfs = update_etfs()
    fiis = update_fiis()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    total = stocks_br + stocks_us + etfs + fiis
    logger.info(f"✅ Full update completed in {duration:.1f}s - Total: {total} records")
    
    return {
        'stocks_br': stocks_br,
        'stocks_us': stocks_us,
        'etfs': etfs,
        'fiis': fiis,
        'total': total,
        'duration': duration
    }


def cleanup_old_logs():
    """Cleanup old update logs (keep last 30 days)"""
    logger.info("🧹 Cleaning up old logs...")
    try:
        db_manager.cleanup_old_data(days=30)
        logger.info("✅ Cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")


if __name__ == "__main__":
    # For testing - run a full update
    logger.info("=" * 60)
    logger.info("MANUAL DATA UPDATE TEST")
    logger.info("=" * 60)
    
    result = update_all_data()
    
    logger.info("=" * 60)
    logger.info("UPDATE SUMMARY:")
    logger.info(f"  Brazilian Stocks: {result['stocks_br']}")
    logger.info(f"  US Stocks: {result['stocks_us']}")
    logger.info(f"  ETFs: {result['etfs']}")
    logger.info(f"  FIIs: {result['fiis']}")
    logger.info(f"  Total: {result['total']} records")
    logger.info(f"  Duration: {result['duration']:.1f} seconds")
    logger.info("=" * 60)
