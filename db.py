import streamlit as st
import bcrypt
import datetime
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Float, DateTime, UniqueConstraint, inspect

# --- DATABASE CONNECTION & CONFIG ---

def get_db_engine():
    """
    Returns a SQLAlchemy Engine.
    Prioritizes Supabase/Postgres configuration.
    Falls back to local SQLite if not found.
    """
    try:
        # 1. Try Streamlit Connection (Native)
        if "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
            conn = st.connection("postgresql", type="sql")
            return conn.engine
            
        # 2. Try Manual URL from Secrets (Supabase specific)
        # Supabase provides a direct connection string
        elif "SUPABASE_DB_URL" in st.secrets:
            url = st.secrets["SUPABASE_DB_URL"]
            # Fix protocol for SQLAlchemy if needed
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return create_engine(url)

    except Exception as e:
        print(f"Postgres/Supabase not configured or connection failed: {e}")

    # 3. Fallback to SQLite
    print("⚠️ Using Local SQLite (Ephemeral)")
    return create_engine("sqlite:///market_hacking.db", connect_args={"check_same_thread": False})

# Global/Singleton Engine
engine = get_db_engine()
metadata = MetaData()

# --- SCHEMA DEFINITIONS (SQLAlchemy Core) ---
# This ensures DDL works for both SQLite and Postgres

users = Table(
    'users', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True), # Serial in PG, Autoinc in SQLite
    Column('username', String, unique=True, nullable=False),
    Column('email', String, unique=True),
    Column('password_hash', String, nullable=False), # hex/bytes stored as string
    Column('google_id', String),
    Column('created_at', DateTime, default=datetime.datetime.utcnow)
)

sessions = Table(
    'sessions', metadata,
    Column('token', String, primary_key=True),
    Column('user_id', Integer, nullable=False),
    Column('created_at', DateTime, default=datetime.datetime.utcnow)
)

portfolio = Table(
    'portfolio', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', Integer, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    Column('avg_price', Float, nullable=False),
    Column('last_updated_at', DateTime, default=datetime.datetime.utcnow),
    UniqueConstraint('user_id', 'ticker', name='uq_user_ticker')
)

transactions = Table(
    'transactions', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', Integer, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    Column('price', Float, nullable=False),
    Column('type', String, nullable=False), # BUY, SELL
    Column('date', DateTime, default=datetime.datetime.utcnow)
)

def init_db():
    """Creates tables if they don't exist."""
    try:
        metadata.create_all(engine)
    except Exception as e:
        print(f"Error initializing DB: {e}")

# --- AUTHENTICATION ---

def create_user(username, password, email=None):
    try:
        if isinstance(password, str): 
            password = password.encode('utf-8')
            
        hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8') # Store as string
        
        with engine.connect() as conn:
            stmt = users.insert().values(
                username=username, 
                password_hash=hashed, 
                email=email
            )
            conn.execute(stmt)
            conn.commit()
            
        return True, "Usuário criado com sucesso!"
    except sqlalchemy.exc.IntegrityError:
        return False, "Usuário já existe!"
    except Exception as e:
        return False, str(e)

def verify_user(username, password):
    with engine.connect() as conn:
        stmt = users.select().where(users.c.username == username)
        result = conn.execute(stmt).fetchone()
        
    if result:
        # result is a Row object/tuple. 
        # columns: id(0), username(1), email(2), pass(3)...
        stored_hash = result.password_hash
        # Ensure bytes
        if isinstance(stored_hash, str): stored_hash = stored_hash.encode('utf-8')
        
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return {"id": result.id, "username": result.username}
    return None

def login_google_user(email, google_id):
    """Loga ou cria usuário via Google"""
    with engine.connect() as conn:
        # Check Exists
        # Using text() for OR condition across columns is easiest with Core mix
        # Or using or_()
        from sqlalchemy import or_
        stmt = users.select().where(or_(users.c.email == email, users.c.google_id == google_id))
        user = conn.execute(stmt).fetchone()
        
        if user:
            # Update Google ID if valid
            if not user.google_id:
                upd = users.update().where(users.c.id == user.id).values(google_id=google_id)
                conn.execute(upd)
                conn.commit()
            return {"id": user.id, "username": user.username}
        else:
            # Create
            username = email.split('@')[0]
            
            # Check username collision
            check = conn.execute(users.select().where(users.c.username == username)).fetchone()
            if check: 
                username = f"{username}_{int(datetime.datetime.now().timestamp())}"
            
            # Insert
            ins = users.insert().values(
                username=username,
                email=email,
                google_id=google_id,
                password_hash="GOOGLE_AUTH_NO_PASS"
            )
            res = conn.execute(ins)
            conn.commit()
            
            # Fetch back (res.inserted_primary_key gives ID)
            # Different drivers behave differently. Safer to fetch ID.
            # Or use res.inserted_primary_key[0]
            new_id = res.inserted_primary_key[0]
            
            return {"id": new_id, "username": username}

# --- SESSIONS ---
import uuid

def create_session(user_id):
    token = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(sessions.insert().values(token=token, user_id=user_id))
        conn.commit()
    return token

def get_user_by_session(token):
    with engine.connect() as conn:
        # Join
        j = sessions.join(users, sessions.c.user_id == users.c.id)
        stmt = sqlalchemy.select(users.c.id, users.c.username, users.c.email).select_from(j).where(sessions.c.token == token)
        user = conn.execute(stmt).fetchone()
        
    if user:
        return {"id": user.id, "username": user.username}
    return None

def delete_session(token):
    with engine.connect() as conn:
        conn.execute(sessions.delete().where(sessions.c.token == token))
        conn.commit()

def delete_all_user_sessions(user_id):
    try:
        with engine.connect() as conn:
            conn.execute(sessions.delete().where(sessions.c.user_id == user_id))
            conn.commit()
    except: pass

# --- WALLET ---

def get_portfolio(user_id):
    # Pandas read_sql works with Engine
    try:
        # Avoid pandas reading entire table if possible, filter in SQL
        # We need query
        query = portfolio.select().where(portfolio.c.user_id == user_id)
        # pd.read_sql requires connection/engine
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        print(f"Error reading portfolio: {e}")
        return pd.DataFrame()

def add_to_wallet(user_id, ticker, quantity, price):
    with engine.connect() as conn:
        try:
            # Check existing
            stmt = portfolio.select().where(
                (portfolio.c.user_id == user_id) & (portfolio.c.ticker == ticker)
            )
            row = conn.execute(stmt).fetchone()
            
            if row:
                old_qty = row.quantity
                old_avg = row.avg_price
                new_qty = old_qty + quantity
                
                if new_qty > 0:
                    new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
                else:
                    new_avg = 0
                    
                upd = portfolio.update().where(
                    (portfolio.c.user_id == user_id) & (portfolio.c.ticker == ticker)
                ).values(
                    quantity=new_qty,
                    avg_price=new_avg,
                    last_updated_at=datetime.datetime.now()
                )
                conn.execute(upd)
            else:
                ins = portfolio.insert().values(
                    user_id=user_id,
                    ticker=ticker,
                    quantity=quantity,
                    avg_price=price,
                    last_updated_at=datetime.datetime.now()
                )
                conn.execute(ins)
            
            # Log Transaction
            tr_type = "BUY" if quantity > 0 else "SELL"
            conn.execute(transactions.insert().values(
                user_id=user_id,
                ticker=ticker,
                quantity=quantity,
                price=price,
                type=tr_type,
                date=datetime.datetime.now()
            ))
            
            conn.commit()
            return True, "Carteira atualizada!"
        except Exception as e:
            return False, f"Erro DB: {str(e)}"

def update_wallet_item(user_id, ticker, new_qty, new_price):
    try:
        with engine.connect() as conn:
            upd = portfolio.update().where(
                (portfolio.c.user_id == user_id) & (portfolio.c.ticker == ticker)
            ).values(
                quantity=new_qty,
                avg_price=new_price,
                last_updated_at=datetime.datetime.now()
            )
            conn.execute(upd)
            conn.commit()
        return True, "Atualizado!"
    except Exception as e:
        return False, str(e)

def remove_from_wallet(user_id, ticker):
    try:
        with engine.connect() as conn:
            conn.execute(portfolio.delete().where(
                (portfolio.c.user_id == user_id) & (portfolio.c.ticker == ticker)
            ))
             # Log Transaction
            conn.execute(transactions.insert().values(
                user_id=user_id,
                ticker=ticker,
                quantity=0,
                price=0,
                type="REMOVE",
                date=datetime.datetime.now()
            ))
            conn.commit()
        return True, "Removido!"
    except Exception as e:
        return False, str(e)


# Initialize
init_db()
