import logging
import os
import sys
from sqlalchemy import text, inspect
from database.db_manager import SessionLocal, engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """
    Adds 'metadata' JSONB column to 'assets' table if it doesn't exist.
    """
    try:
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('assets')]
        
        if 'metadata' in columns:
            logger.info("✅ Column 'metadata' already exists in 'assets' table.")
            return

        logger.info("⚙️ Adding 'metadata' column to 'assets' table...")
        
        with engine.connect() as conn:
            # Using JSON for compatibility (Supabase/Postgres supports JSONB, but simple JSON is safer generic)
            # In Postgres, JSONB is better.
            conn.execute(text("ALTER TABLE assets ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb"))
            conn.commit()
            
        logger.info("✅ Migration successful: 'metadata' column added.")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        # Try generic JSON if JSONB fails (though Supabase IS Postgres)
        try:
           logger.info("⚠️ Retrying with generic JSON type...")
           with engine.connect() as conn:
                conn.execute(text("ALTER TABLE assets ADD COLUMN metadata JSON DEFAULT '{}'"))
                conn.commit()
           logger.info("✅ Migration successful (fallback): 'metadata' column added.")
        except Exception as e2:
             logger.error(f"❌ Fallback failed: {e2}")

if __name__ == "__main__":
    run_migration()
