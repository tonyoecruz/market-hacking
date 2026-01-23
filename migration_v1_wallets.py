import toml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

def get_db_url():
    try:
        if not os.path.exists(".streamlit/secrets.toml"):
            print("Error: .streamlit/secrets.toml not found.")
            return None
            
        secrets = toml.load(".streamlit/secrets.toml")
        
        # Try to find postgres config
        if "connections" in secrets and "postgresql" in secrets["connections"]:
            conf = secrets["connections"]["postgresql"]
        elif "postgres" in secrets:
            conf = secrets["postgres"]
        else:
            print("Error: Could not find [connections.postgresql] in secrets.")
            return None

        # Construct URL
        # Format: postgresql://user:pass@host:port/dbname
        # Handle 'postgres://' vs 'postgresql://' replacement if needed by SQLAlchemy
        
        # Check if type is sql which usually implies key-value pairs
        # Assume standard keys
        user = conf.get("username") or conf.get("user")
        password = conf.get("password")
        host = conf.get("host")
        port = conf.get("port", 5432)
        dbname = conf.get("database") or conf.get("dbname")
        
        if not all([user, password, host, dbname]):
            print(f"Error: Missing DB config keys. Found: {conf.keys()}")
            return None
            
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        
    except Exception as e:
        print(f"Error reading secrets: {e}")
        return None

def run_migration():
    print("Database Migration: Wallets Support (V1)")
    
    url = get_db_url()
    if not url:
        return

    try:
        engine = create_engine(url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("Starting migration...")

        # 1. Create WALLETS table
        print("1. Creating 'wallets' table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS wallets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_user_wallet_name UNIQUE (user_id, name)
            );
        """))

        # 2. Add wallet_id column to PORTFOLIO (nullable first)
        print("2. Adding 'wallet_id' to 'portfolio' table...")
        # Check if column exists first to be safe
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='portfolio' AND column_name='wallet_id';
        """))
        if result.rowcount == 0:
            session.execute(text("ALTER TABLE portfolio ADD COLUMN wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE;"))
        else:
                print("'wallet_id' column already exists.")

        # 3. Create Default Wallets for Existing Users
        print("3. Creating default 'Carteira Principal' for existing users...")
        users = session.execute(text("SELECT id FROM users;")).fetchall()
        
        for user in users:
            user_id = user[0]
            existing_wallet = session.execute(text("SELECT id FROM wallets WHERE user_id = :u AND name = 'Carteira Principal'"), {"u": user_id}).fetchone()
            
            if not existing_wallet:
                session.execute(text("INSERT INTO wallets (user_id, name) VALUES (:u, 'Carteira Principal')"), {"u": user_id})
                print(f"  - Created default wallet for User ID {user_id}")
            else:
                print(f"  - Default wallet already exists for User ID {user_id}")

        # 4. Assign Existing Assets to Default Wallet
        print("4. Migrating assets to default wallet...")
        session.execute(text("""
            UPDATE portfolio p
            SET wallet_id = w.id
            FROM wallets w
            WHERE p.user_id = w.user_id 
            AND w.name = 'Carteira Principal'
            AND p.wallet_id IS NULL;
        """))
        
        # 5. Update Unique Constraint
        print("5. Updating Unique Constraints (User+Ticker -> Wallet+Ticker)...")
        
        try:
            session.execute(text("ALTER TABLE portfolio DROP CONSTRAINT IF EXISTS uq_user_ticker;"))
            print("  - Dropped old constraint 'uq_user_ticker'")
        except Exception as e:
            print(f"  - Could not drop constraint (might not exist): {e}")

        try:
            session.execute(text("ALTER TABLE portfolio ADD CONSTRAINT uq_wallet_ticker UNIQUE (wallet_id, ticker);"))
            print("  - Added new constraint 'uq_wallet_ticker'")
        except Exception as e:
            print(f"  - Could not add new constraint (might already exist): {e}")

        session.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration Failed: {e}")
        # session.rollback() # Handle rollback if needed

if __name__ == "__main__":
    run_migration()
