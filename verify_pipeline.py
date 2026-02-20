
import os
import sys
import pandas as pd
import logging

# Add root dir to sys.path
sys.path.append(os.getcwd())

from modules.statusinvest_extractor import get_br_stocks_statusinvest
from database.db_manager import db_manager as db
from routes.acoes import _build_universe
from routes.engines.spreadsheet_engine import apply_spreadsheet_mode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

def verify_pipeline():
    logger.info("--- 1. Testing StatusInvest Fetcher ---")
    df = get_br_stocks_statusinvest()
    if df.empty:
        logger.error("Fetcher returned empty dataframe!")
        return
    
    logger.info(f"Fetcher columns: {df.columns.tolist()}")
    if 'roe' in df.columns and 'roa' in df.columns:
        logger.info(f"✅ roe/roa present in fetcher output. Sample roe={df['roe'].iloc[0]}, roa={df['roa'].iloc[0]}")
    else:
        logger.error(f"❌ roe/roa MISSING from fetcher output! Cols: {df.columns.tolist()}")

    logger.info("\n--- 2. Testing DB Save ---")
    # Take a small sample to avoid bloating DB during test
    sample_df = df.head(10).copy()
    saved_count = db.save_stocks(sample_df, market='BR')
    logger.info(f"Saved {saved_count} stocks to DB (sample).")

    logger.info("\n--- 3. Testing _build_universe ---")
    df_uni = _build_universe(market='BR', filter_risky=False)
    if 'roe' in df_uni.columns and 'roa' in df_uni.columns:
        logger.info(f"✅ roe/roa present in universe. Sample roe={df_uni['roe'].iloc[0]}, roa={df_uni['roa'].iloc[0]}")
    else:
        logger.error(f"❌ roe/roa MISSING from universe!")

    logger.info("\n--- 4. Testing Ranking Engine (Magic) ---")
    df_ranked, caveats = apply_spreadsheet_mode(df_uni, strategy='magic', top_n=5)
    logger.info(f"Ranked {len(df_ranked)} stocks. Top tickers: {df_ranked['ticker'].tolist()}")
    
    logger.info("\n--- 5. Testing Ranking Engine (Mix - uses roe/roa) ---")
    df_ranked_mix, caveats_mix = apply_spreadsheet_mode(df_uni, strategy='mix', top_n=5)
    logger.info(f"Ranked {len(df_ranked_mix)} stocks (Mix).")
    if '_r_roe' in df_ranked_mix.columns and '_r_roa' in df_ranked_mix.columns:
        logger.info("✅ Mix strategy correctly used roe/roa rank columns.")
    else:
        logger.info("⚠️ Mix strategy rank columns missing (check logs for 'column NOT in DataFrame')")

if __name__ == "__main__":
    verify_pipeline()
