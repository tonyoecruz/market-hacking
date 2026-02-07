import asyncio
import logging
import sys
import os

# Add root dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from scheduler.data_updater import update_all_data

async def main():
    print("Starting manual update...")
    try:
        await update_all_data()
        print("Update finished successfully.")
    except Exception as e:
        print(f"Update failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
