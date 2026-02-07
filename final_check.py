import asyncio
import sys
import os

# Add root dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from scheduler.data_updater import update_all_data

def main():
    print("Running final full update...")
    results = update_all_data()
    print(f"\nFINAL RESULTS: {results}")
    
    # Check if any part crashed
    all_ok = all("SUCCESS" in str(v) or "EMPTY_DATA" in str(v) for v in results.values())
    if all_ok:
        print("\n✅ ALL SYSTEMS GO! No TypeErrors found.")
    else:
        print("\n⚠️  Some updates had issues (see results above).")

if __name__ == "__main__":
    main()
