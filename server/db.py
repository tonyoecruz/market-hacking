import os
import sqlite3
import pandas as pd
import bcrypt
import datetime
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()

DB_FILE = "market_hacking.db"

# --- DATABASE ENGINE SETUP ---
# Detects if using Postgres (Supabase) or fallback SQLite
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Postgres
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    print("🔌 Conectado ao PostgreSQL (Supabase)")
else:
    # SQLite
    print("⚠️ DATABASE_URL não encontrada. Usando SQLite local.")
    engine = None
    SessionLocal = None

def get_db_connection():
    """Retorna uma conexão ativa (SQLAlchemy Session ou SQLite Connection)"""
    if engine:
        return SessionLocal()
    else:
        # SQLite Connection
        conn = sqlite3.connect(DB_FILE)
        return conn

def init_db():
    """Inicializa tabelas se nao existirem"""
    if not engine: # SQLite Init
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        
        # Copied Schema from original
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            google_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, ticker)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            type TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
    else:
        # We assume tables exist in cloud for now, or use migration tool like Alembic later
        pass

def run_query(query, params=None):
    """Executa SELECT e retorna DataFrame"""
    try:
        conn = get_db_connection()
        
        if engine: # SQLAlchemy
            try:
                result = conn.execute(text(query), params if params else {})
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                conn.close()
                return df
            except Exception as e:
                conn.close()
                print(f"SQL Error: {e}")
                return pd.DataFrame()
        else: # SQLite
            try:
                df = pd.read_sql_query(query, conn, params=params)
                conn.close()
                return df
            except Exception as e:
                conn.close()
                print(f"SQLite Error: {e}")
                return pd.DataFrame()
    except Exception as e:
        print(f"DB Conn Error: {e}")
        return pd.DataFrame()

def run_transaction(query, params=None):
    """Executa INSERT/UPDATE/DELETE"""
    try:
        conn = get_db_connection()
        
        if engine: # SQLAlchemy
            try:
                conn.execute(text(query), params if params else {})
                conn.commit()
                conn.close()
                return True, None
            except Exception as e:
                conn.rollback()
                conn.close()
                return False, str(e)
        else: # SQLite
            try:
                cur = conn.cursor()
                cur.execute(query, params if params else {})
                conn.commit()
                conn.close()
                return True, None
            except Exception as e:
                conn.close()
                return False, str(e)
    except Exception as e:
        return False, str(e)

# --- AUTHENTICATION ---

def create_user(username, password, email=None):
    try:
        if isinstance(password, str): 
            password = password.encode('utf-8')
            
        hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8') # Store as string
        
        sql = """
            INSERT INTO users (username, password_hash, email) 
            VALUES (:u, :p, :e)
        """
        success, error = run_transaction(sql, {"u": username, "p": hashed, "e": email})
        
        if success:
            return True, "Usuário criado com sucesso!"
        
        # Check integrity error manually from error string (simple approach) or re-raise
        if "unique constraint" in str(error).lower():
            return False, "Usuário já existe!"
        return False, str(error)

    except Exception as e:
        return False, str(e)

def verify_user(username, password):
    sql = "SELECT id, username, password_hash FROM users WHERE username = :u"
    df = run_query(sql, {"u": username})
    
    if not df.empty:
        user = df.iloc[0]
        stored_hash = user['password_hash']
        if isinstance(stored_hash, str): stored_hash = stored_hash.encode('utf-8')
        
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return {"id": int(user['id']), "username": user['username']}
    return None

def login_google_user(email, google_id):
    """Loga ou cria usuário via Google"""
    # 1. Check user exists
    sql_check = "SELECT id, username, google_id FROM users WHERE email = :e OR google_id = :g"
    df = run_query(sql_check, {"e": email, "g": google_id})
    
    if not df.empty:
        user = df.iloc[0]
        user_id = int(user['id'])
        
        # Update Google ID if missing
        if not user['google_id']:
            upd_sql = "UPDATE users SET google_id = :g WHERE id = :i"
            run_transaction(upd_sql, {"g": google_id, "i": user_id})
            
        return {"id": user_id, "username": user['username']}
    else:
        # Create User
        username = email.split('@')[0]
        
        # Collision Check
        collision_check = "SELECT id FROM users WHERE username = :u"
        if not run_query(collision_check, {"u": username}).empty:
            username = f"{username}_{int(datetime.datetime.now().timestamp())}"
        
        ins_sql = """
            INSERT INTO users (username, email, google_id, password_hash)
            VALUES (:u, :e, :g, 'GOOGLE_AUTH_NO_PASS')
        """
        success, err = run_transaction(ins_sql, {"u": username, "e": email, "g": google_id})
        
        if success:
             # Fetch ID back
             df_new = run_query("SELECT id FROM users WHERE username = :u", {"u": username})
             if not df_new.empty:
                 return {"id": int(df_new.iloc[0]['id']), "username": username}
        else:
            print(f"Erro ao criar usuário no banco: {err}")
        
        return None

# --- SESSIONS ---

def create_session(user_id):
    token = str(uuid.uuid4())
    sql = "INSERT INTO sessions (token, user_id) VALUES (:t, :u)"
    success, err = run_transaction(sql, {"t": token, "u": user_id})
    if success:
        return token, None
    return None, err

def get_user_by_session(token):
    sql = """
        SELECT u.id, u.username, u.email 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = :t
    """
    df = run_query(sql, {"t": token})
    if not df.empty:
        r = df.iloc[0]
        return {"id": int(r['id']), "username": r['username']}
    return None

def delete_session(token):
    sql = "DELETE FROM sessions WHERE token = :t"
    run_transaction(sql, {"t": token})

def delete_all_user_sessions(user_id):
    sql = "DELETE FROM sessions WHERE user_id = :u"
    run_transaction(sql, {"u": user_id})

# --- WALLET ---

def get_portfolio(user_id):
    sql = "SELECT ticker, quantity, avg_price, last_updated_at FROM portfolio WHERE user_id = :u"
    df = run_query(sql, {"u": user_id})
    return df # Returns empty DF if no rows, which is correct

def add_to_wallet(user_id, ticker, quantity, price):
    # 1. Check existing
    sql_check = "SELECT quantity, avg_price FROM portfolio WHERE user_id = :u AND ticker = :t"
    df = run_query(sql_check, {"u": user_id, "t": ticker})
    
    timestamp = datetime.datetime.now()
    
    if not df.empty:
        # Update
        row = df.iloc[0]
        old_qty = row['quantity']
        old_avg = row['avg_price']
        new_qty = old_qty + quantity
        
        if new_qty > 0:
            new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
        else:
            new_avg = 0
            
        upd_sql = """
            UPDATE portfolio 
            SET quantity = :q, avg_price = :p, last_updated_at = :d 
            WHERE user_id = :u AND ticker = :t
        """
        success, msg = run_transaction(upd_sql, {
            "q": int(new_qty), "p": float(new_avg), "d": timestamp, "u": user_id, "t": ticker
        })
    else:
        # Insert
        ins_sql = """
            INSERT INTO portfolio (user_id, ticker, quantity, avg_price, last_updated_at)
            VALUES (:u, :t, :q, :p, :d)
        """
        success, msg = run_transaction(ins_sql, {
            "u": user_id, "t": ticker, "q": int(quantity), "p": float(price), "d": timestamp
        })
        
    if success:
        # Log Transaction
        tr_type = "BUY" if quantity > 0 else "SELL"
        log_sql = """
            INSERT INTO transactions (user_id, ticker, quantity, price, type, date)
            VALUES (:u, :t, :q, :p, :tp, :d)
        """
        run_transaction(log_sql, {
            "u": user_id, "t": ticker, "q": int(quantity), 
            "p": float(price), "tp": tr_type, "d": timestamp
        })
        return True, "Carteira atualizada!"
    else:
        return False, f"Erro DB: {msg}"

def update_wallet_item(user_id, ticker, new_qty, new_price):
    sql = """
        UPDATE portfolio 
        SET quantity = :q, avg_price = :p, last_updated_at = :d 
        WHERE user_id = :u AND ticker = :t
    """
    success, msg = run_transaction(sql, {
        "q": int(new_qty), "p": float(new_price), 
        "d": datetime.datetime.now(), "u": user_id, "t": ticker
    })
    if success: return True, "Atualizado!"
    return False, msg

def remove_from_wallet(user_id, ticker):
    sql = "DELETE FROM portfolio WHERE user_id = :u AND ticker = :t"
    success, msg = run_transaction(sql, {"u": user_id, "t": ticker})
    
    if success:
        # Log Removal
        log_sql = """
            INSERT INTO transactions (user_id, ticker, quantity, price, type, date)
            VALUES (:u, :t, 0, 0, 'REMOVE', :d)
        """
        run_transaction(log_sql, {"u": user_id, "t": ticker, "d": datetime.datetime.now()})
        return True, "Removido!"
    return False, msg

# Initialize (Optional now as we don't create tables in code, but good validation)
# Initialize (Auto-create tables for SQLite)
init_db()
