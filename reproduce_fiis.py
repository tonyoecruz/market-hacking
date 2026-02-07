import sys
import os
import pandas as pd
import logging

# Add root dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)

from modules.statusinvest_extractor import get_br_fiis_statusinvest

def reproduce():
    print("Testing get_br_fiis_statusinvest()...")
    try:
        df = get_br_fiis_statusinvest()
        print("Function returned.")
        if df.empty:
            print("DataFrame is empty!")
        else:
            print(f"DataFrame Shape: {df.shape}")
            print("Columns:", df.columns.tolist())
            
            # Check 'dy' specifically
            if 'dy' in df.columns:
                print(f"\n'dy' dtype: {df['dy'].dtype}")
                print(f"'dy' head: {df['dy'].head().tolist()}")
                
                # Check for any non-numeric
                non_numeric = df[pd.to_numeric(df['dy'], errors='coerce').isna()]
                if not non_numeric.empty:
                    print(f"\nPotential non-numeric 'dy' values: {non_numeric['dy'].unique()}")
            else:
                print("\n'dy' column NOT FOUND!")

            # Check 'pvp'
            if 'pvp' in df.columns:
                print(f"\n'pvp' dtype: {df['pvp'].dtype}")
            
    except Exception as e:
        print(f"Caught Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduce()
