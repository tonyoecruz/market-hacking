"""
Data Updater - Market data fetching and database storage
VERSÃO CORRIGIDA - Compatible with db_manager signatures
"""
import logging
from datetime import datetime
import pandas as pd
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import data_utils directly
import data_utils

# Import DatabaseManager
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Force logs to stdout for Render
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

db = DatabaseManager()

def update_stocks_br():
    """Update Brazilian stocks data"""
    try:
        logger.info("📊 Fetching BR stocks from Fundamentus...")
        df = data_utils.get_data_acoes()
        
        if df is not None and not df.empty:
            # Filter out ETFs
            df['IsETF'] = df['ticker'].apply(data_utils.is_likely_etf)
            df = df[~df['IsETF']].copy()
            
            logger.info(f"✅ Found {len(df)} BR stocks")
            count = db.save_stocks(df, market='BR')
            logger.info(f"💾 Saved {count} BR stocks to database")
            return "SUCCESS"
        else:
            logger.warning("⚠️  No BR stocks data retrieved")
            return "EMPTY_DATA"
            
    except Exception as e:
        logger.error(f"❌ Error updating BR stocks: {str(e)}", exc_info=True)
        return f"ERROR: {str(e)}"

# ... (similar updates for other functions would follow, but I'll focus on update_all_data logic first)

def update_all_data():
    """Run all market data updates"""
    logger.info("="*80)
    logger.info(f"🔄 Starting complete market update at {datetime.now()}")
    logger.info("="*80)
    
    results = {}
    start_time = datetime.now()
    
    # Update BR Stocks
    try:
        logger.info("📊 [1/4] Updating Brazilian stocks...")
        status_br = update_stocks_br()
        results['stocks_br'] = status_br
        logger.info(f"✅ BR Stocks: {status_br}")
        
        # Log to database
        db.log_update(
            asset_type='stocks',
            market='BR',
            status='success' if status_br == 'SUCCESS' else 'error',
            records_updated=0, # Simplified for now
            error_message=status_br if status_br != 'SUCCESS' else None,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ BR Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_br'] = f"CRASH: {str(e)}"

def update_stocks_us():
    """Update US stocks data"""
    try:
        logger.info("📊 Fetching US stocks from TradingView...")
        df = data_utils.get_data_usa()
        
        if df is not None and not df.empty:
            logger.info(f"✅ Found {len(df)} US stocks")
            count = db.save_stocks(df, market='US')
            logger.info(f"💾 Saved {count} US stocks to database")
            return "SUCCESS"
        else:
            logger.warning("⚠️  No US stocks data retrieved")
            return "EMPTY_DATA"
            
    except Exception as e:
        logger.error(f"❌ Error updating US stocks: {str(e)}", exc_info=True)
        return f"ERROR: {str(e)}"

def update_fiis():
    """Update FIIs data"""
    try:
        logger.info("📊 Fetching FIIs from Fundamentus...")
        df = data_utils.get_data_fiis()
        
        if df is not None and not df.empty:
            logger.info(f"✅ Found {len(df)} FIIs")
            # FIIs are always BR market
            count = db.save_fiis(df, market='BR')
            logger.info(f"💾 Saved {count} FIIs to database")
            return "SUCCESS"
        else:
            logger.warning("⚠️  No FIIs data retrieved")
            return "EMPTY_DATA"
            
    except Exception as e:
        logger.error(f"❌ Error updating FIIs: {str(e)}", exc_info=True)
        return f"ERROR: {str(e)}"

def update_etfs():
    """Update ETFs data (BR and US)"""
    try:
        logger.info("📊 Fetching ETFs...")
        total_count = 0
        
        # BR ETFs
        try:
            logger.info("  - Fetching BR ETFs via yfinance...")
            import yfinance as yf
            tickers_sa = [f"{t}.SA" for t in data_utils.KNOWN_ETFS]
            batch = yf.download(tickers_sa, period="5d", interval="1d", group_by='ticker', progress=False)
            
            etf_data = []
            for t_raw in data_utils.KNOWN_ETFS:
                t_sa = f"{t_raw}.SA"
                try:
                    if len(tickers_sa) > 1:
                        df_t = batch[t_sa]
                    else:
                        df_t = batch
                    
                    if not df_t.empty:
                        last_row = df_t.iloc[-1]
                        price = float(last_row['Close'])
                        vol = float(last_row['Volume']) * price
                        if price > 0:
                            etf_data.append({
                                'ticker': t_raw,
                                'price': price,
                                'liquidezmediadiaria': vol
                            })
                except:
                    pass
            
            if etf_data:
                df_br = pd.DataFrame(etf_data)
                count_br = db.save_etfs(df_br, market='BR')
                logger.info(f"  ✅ Saved {count_br} BR ETFs")
                total_count += count_br
        except Exception as e:
            logger.error(f"  ❌ Error fetching BR ETFs: {str(e)}")
        
        # US ETFs
        try:
            logger.info("  - Fetching US ETFs from TradingView...")
            df_us = data_utils.get_data_usa_etfs()
            if df_us is not None and not df_us.empty:
                # Remove columns that don't exist in ETFDB model
                df_us = df_us[['ticker', 'price', 'liquidezmediadiaria']].copy()
                count_us = db.save_etfs(df_us, market='US')
                logger.info(f"  ✅ Saved {count_us} US ETFs")
                total_count += count_us
        except Exception as e:
            logger.error(f"  ❌ Error fetching US ETFs: {str(e)}")
        
        if total_count > 0:
            logger.info(f"💾 Total ETFs saved: {total_count}")
            return "SUCCESS"
        else:
            logger.warning("⚠️  No ETFs data retrieved")
            return "EMPTY_DATA"
            
    except Exception as e:
        logger.error(f"❌ Error updating ETFs: {str(e)}", exc_info=True)
        return f"ERROR: {str(e)}"

def update_all_data():
    """Run all market data updates"""
    logger.info("="*80)
    logger.info(f"🔄 Starting complete market update at {datetime.now()}")
    logger.info("="*80)
    
    results = {}
    start_time = datetime.now()
    
    # Update BR Stocks
    try:
        logger.info("📊 [1/4] Updating Brazilian stocks...")
        count_br = update_stocks_br()
        results['stocks_br'] = count_br > 0
        logger.info(f"✅ BR Stocks: {'SUCCESS' if results['stocks_br'] else 'FAILED'} ({count_br} records)")
        
        # Log to database
        db.log_update(
            asset_type='stocks',
            market='BR',
            status='success' if results['stocks_br'] else 'failed',
            records_updated=count_br,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ BR Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_br'] = False
    
    # Update US Stocks (Temporarily Disabled for Debugging/Load Reduction)
    try:
        logger.info("📊 [2/4] Updating US stocks (SKIPPED FOR DEBUG)...")
        # status_us = update_stocks_us()
        status_us = "SKIPPED"
        results['stocks_us'] = str(status_us)
        logger.info(f"✅ US Stocks status: {status_us}")
        
        # Log to database
        db.log_update(
            asset_type='stocks',
            market='US',
            status='success',
            records_updated=0,
            error_message="Skipped for debugging",
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ US Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_us'] = f"ERROR: {str(e)}"
    
    # Update FIIs
    try:
        logger.info("📊 [3/4] Updating FIIs...")
        status_fiis = update_fiis()
        results['fiis'] = str(status_fiis)
        logger.info(f"✅ FIIs status: {status_fiis}")
        
        db.log_update(
            asset_type='fiis',
            market='BR',
            status='success' if str(status_fiis).isdigit() and int(status_fiis) > 0 else 'error',
            records_updated=int(status_fiis) if str(status_fiis).isdigit() else 0,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ FIIs ERROR: {str(e)}", exc_info=True)
        results['fiis'] = f"ERROR: {str(e)}"
    
    # Update ETFs
    try:
        logger.info("📊 [4/4] Updating ETFs...")
        status_etfs = update_etfs()
        results['etfs'] = str(status_etfs)
        logger.info(f"✅ ETFs status: {status_etfs}")
        
        db.log_update(
            asset_type='etfs',
            market='BOTH',
            status='success' if str(status_etfs).isdigit() and int(status_etfs) > 0 else 'error',
            records_updated=int(status_etfs) if str(status_etfs).isdigit() else 0,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ ETFs ERROR: {str(e)}", exc_info=True)
        results['etfs'] = f"ERROR: {str(e)}"
    
    logger.info("="*80)
    logger.info(f"✅ Update cycle finished. Results: {results}")
    logger.info("="*80)
    
    return results

def cleanup_old_logs():
    """Remove old update logs"""
    db.cleanup_logs(days=7)
