import sqlite3
import os

DB_PATH = 'market_data.db'

def check_counts():
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE market='BR'")
        count_br = cursor.fetchone()[0]
        print(f"BR Stocks Count: {count_br}")
        
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE market='US'")
        count_us = cursor.fetchone()[0]
        print(f"US Stocks Count: {count_us}")

        cursor.execute("SELECT COUNT(*) FROM fiis")
        count_fiis = cursor.fetchone()[0]
        print(f"FIIs Count: {count_fiis}")
        
        # Check logs for errors
        cursor.execute("SELECT * FROM update_logs ORDER BY id DESC LIMIT 5")
        logs = cursor.fetchall()
        print("\nLast 5 Logs:")
        for log in logs:
            print(log)
            
    except Exception as e:
        print(f"Error checking DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_counts()
