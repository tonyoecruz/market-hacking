"""
Data Updater - Market data fetching and database storage
VERSÃO CORRIGIDA - Compatible with db_manager signatures
"""
import logging
from datetime import datetime
import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import data_utils directly
import data_utils

# Import DatabaseManager
from database.db_manager import DatabaseManager
from modules.statusinvest_extractor import enrich_queda_maximo

logger = logging.getLogger(__name__)

# Force logs to stdout for Render
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

db = DatabaseManager()

def _calculate_graham_magic(df):
    """Calculate Graham (ValorJusto, Margem) and Magic Formula (MagicRank) for a DataFrame"""
    # Ensure numeric columns
    for col in ['lpa', 'vpa', 'price', 'ev_ebit', 'roic', 'liquidezmediadiaria']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # GRAHAM FORMULA: ValorJusto = sqrt(22.5 * LPA * VPA)
    graham_term = (22.5 * df['lpa'] * df['vpa'])
    df['ValorJusto'] = graham_term.apply(lambda x: x**0.5 if x > 0 else 0)
    df['Margem'] = df.apply(
        lambda r: (r['ValorJusto'] / r['price']) - 1 if r['price'] > 0 else 0, axis=1
    )
    
    # MAGIC FORMULA: Rank by EV/EBIT (lower=better) + ROIC (higher=better)
    df_magic = df[(df['ev_ebit'] > 0) & (df['roic'] > 0)].copy()
    if not df_magic.empty:
        df_magic['R_EV'] = df_magic['ev_ebit'].rank(ascending=True)
        df_magic['R_ROIC'] = df_magic['roic'].rank(ascending=False)
        df_magic['Score'] = df_magic['R_EV'] + df_magic['R_ROIC']
        df_magic['MagicRank'] = df_magic['Score'].rank(ascending=True)
        
        # Merge back
        cols_to_drop = ['Score', 'MagicRank', 'R_EV', 'R_ROIC']
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')
        df = df.merge(df_magic[['ticker', 'Score', 'MagicRank', 'R_EV', 'R_ROIC']], on='ticker', how='left')
        logger.info(f"  📐 Calculated MagicRank for {len(df_magic)} stocks")
    
    return df


def update_stocks_br():
    """Update Brazilian stocks data"""
    try:
        logger.info("📊 Fetching BR stocks from StatusInvest...")
        df = data_utils.get_data_acoes()
        
        if df is not None and not df.empty:
            # Filter out ETFs
            df['IsETF'] = df['ticker'].apply(data_utils.is_likely_etf)
            df = df[~df['IsETF']].copy()
            
            # Calculate Graham + Magic Formula
            df = _calculate_graham_magic(df)

            # Enrich with 52-week high data (Queda do Máximo)
            logger.info("📈 Fetching 52-week high from Google Finance (yfinance)...")
            df = enrich_queda_maximo(df)

            logger.info(f"✅ Found {len(df)} BR stocks (with Graham+Magic+Queda calc)")
            count = db.save_stocks(df, market='BR')
            logger.info(f"💾 Saved {count} BR stocks to database")
            return count
        else:
            logger.warning("⚠️  No BR stocks data retrieved")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Error updating BR stocks: {str(e)}", exc_info=True)
        raise

def update_stocks_us():
    """Update US stocks data"""
    try:
        logger.info("📊 Fetching US stocks from TradingView...")
        df = data_utils.get_data_usa()
        
        if df is not None and not df.empty:
            # Calculate Graham + Magic Formula
            df = _calculate_graham_magic(df)
            
            logger.info(f"✅ Found {len(df)} US stocks (with Graham+Magic calc)")
            count = db.save_stocks(df, market='US')
            logger.info(f"💾 Saved {count} US stocks to database")
            return count
        else:
            logger.warning("⚠️  No US stocks data retrieved")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Error updating US stocks: {str(e)}", exc_info=True)
        raise

def update_fiis():
    """Update FIIs data"""
    try:
        logger.info("📊 Fetching FIIs from StatusInvest...")
        df = data_utils.get_data_fiis()
        
        if df is not None and not df.empty:
            logger.info(f"✅ Found {len(df)} FIIs")
            # FIIs are always BR market
            count = db.save_fiis(df, market='BR')
            logger.info(f"💾 Saved {count} FIIs to database")
            return count
        else:
            logger.warning("⚠️  No FIIs data retrieved")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Error updating FIIs: {str(e)}", exc_info=True)
        raise

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
            return total_count
        else:
            logger.warning("⚠️  No ETFs data retrieved")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Error updating ETFs: {str(e)}", exc_info=True)
        raise

def update_all_data():
    """Run all market data updates"""
    logger.info("="*80)
    logger.info(f"🔄 Starting complete market update at {datetime.now()}")
    logger.info("="*80)
    
    results = {}
    
    # Update BR Stocks
    start_time = datetime.now()
    try:
        logger.info("📊 [1/4] Updating Brazilian stocks...")
        count = update_stocks_br()
        results['stocks_br'] = f"SUCCESS ({count})"
        logger.info(f"✅ BR Stocks: {count} records")
        
        db.log_update(
            asset_type='stocks',
            market='BR',
            status='success',
            records_updated=count,
            error_message=None,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ BR Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_br'] = f"ERROR: {str(e)}"
        db.log_update(
            asset_type='stocks',
            market='BR',
            status='error',
            records_updated=0,
            error_message=str(e),
            started_at=start_time,
            completed_at=datetime.now()
        )
    
    # Update US Stocks
    start_time = datetime.now()
    try:
        logger.info("📊 [2/4] Updating US stocks...")
        count = update_stocks_us()
        results['stocks_us'] = f"SUCCESS ({count})"
        logger.info(f"✅ US Stocks: {count} records")
        
        db.log_update(
            asset_type='stocks',
            market='US',
            status='success',
            records_updated=count,
            error_message=None,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ US Stocks ERROR: {str(e)}", exc_info=True)
        results['stocks_us'] = f"ERROR: {str(e)}"
        db.log_update(
            asset_type='stocks',
            market='US',
            status='error',
            records_updated=0,
            error_message=str(e),
            started_at=start_time,
            completed_at=datetime.now()
        )
    
    # Update FIIs
    start_time = datetime.now()
    try:
        logger.info("📊 [3/4] Updating FIIs...")
        count = update_fiis()
        results['fiis'] = f"SUCCESS ({count})"
        logger.info(f"✅ FIIs: {count} records")
        
        db.log_update(
            asset_type='fiis',
            market='BR',
            status='success',
            records_updated=count,
            error_message=None,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ FIIs ERROR: {str(e)}", exc_info=True)
        results['fiis'] = f"ERROR: {str(e)}"
        db.log_update(
            asset_type='fiis',
            market='BR',
            status='error',
            records_updated=0,
            error_message=str(e),
            started_at=start_time,
            completed_at=datetime.now()
        )
    
    # Update ETFs
    start_time = datetime.now()
    try:
        logger.info("📊 [4/4] Updating ETFs...")
        count = update_etfs()
        results['etfs'] = f"SUCCESS ({count})"
        logger.info(f"✅ ETFs: {count} records")
        
        db.log_update(
            asset_type='etfs',
            market='BOTH',
            status='success',
            records_updated=count,
            error_message=None,
            started_at=start_time,
            completed_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"❌ ETFs ERROR: {str(e)}", exc_info=True)
        results['etfs'] = f"ERROR: {str(e)}"
        db.log_update(
            asset_type='etfs',
            market='BOTH',
            status='error',
            records_updated=0,
            error_message=str(e),
            started_at=start_time,
            completed_at=datetime.now()
        )
    
    logger.info("="*80)
    logger.info(f"✅ Update cycle finished. Results: {results}")
    logger.info("="*80)
    
    return results

async def update_flipping():
    """Update House Flipping data for all monitored cities"""
    from modules.house_flipping import SerperAgencyDiscovery, AgencyCrawler, calculate_flipping_opportunity

    cities = db.get_flipping_cities()
    if not cities:
        logger.info("[FLIPPING] No monitored cities to update")
        return 0

    logger.info(f"[FLIPPING] Updating {len(cities)} monitored cities...")
    total = 0

    for city_record in cities:
        city = city_record["city"]
        try:
            logger.info(f"[FLIPPING] Scanning '{city}'...")

            # Discover agencies
            discovery = SerperAgencyDiscovery()
            agencies = await discovery.discover(city)
            if not agencies:
                logger.warning(f"[FLIPPING] No agencies found for '{city}'")
                continue

            # Crawl
            crawler = AgencyCrawler()
            listings = await crawler.crawl_all_agencies(agencies, city)
            if not listings:
                logger.warning(f"[FLIPPING] No listings extracted for '{city}'")
                continue

            # Analyze
            df = pd.DataFrame(listings)
            df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
            df['Area (m2)'] = pd.to_numeric(df['Area (m2)'], errors='coerce')
            df = df.dropna(subset=['Valor Total', 'Area (m2)'])

            if df.empty:
                continue

            df_analyzed = calculate_flipping_opportunity(df)
            results = df_analyzed.to_dict('records')

            # Save to cache
            count = db.save_flipping_listings(city, results)
            total += count
            logger.info(f"[FLIPPING] Saved {count} listings for '{city}'")

        except Exception as e:
            logger.error(f"[FLIPPING] Error updating '{city}': {e}", exc_info=True)

    logger.info(f"[FLIPPING] Update complete: {total} total listings across {len(cities)} cities")
    return total


def cleanup_old_logs():
    """Remove old update logs"""
    db.cleanup_logs(days=7)
