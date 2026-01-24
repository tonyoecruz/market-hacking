import streamlit as st
import bcrypt
import datetime
import pandas as pd
import uuid
from sqlalchemy import text

# --- DATABASE CONNECTION (Native Streamlit/Supabase) ---

# --- DATABASE CONNECTION (Native Streamlit/Supabase + SQLite Fallback) ---

import sqlite3
import os

DB_FILE = "market_hacking.db"

def get_db_connection():
    """Conecta ao Supabase OU SQLite dependendo da config"""
    # 1. Tenta Supabase se configurado
    if "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
        try:
            return st.connection("postgresql", type="sql")
        except Exception:
            pass
            
    # 2. Fallback SQLite
    return "sqlite"

def init_db():
    conn = get_db_connection()
    if conn == "sqlite":
        # Create Tables if not exist
        try:
            c = sqlite3.connect(DB_FILE)
            cur = c.cursor()
            
            # Users
            cur.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                google_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Sessions
            cur.execute('''CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Portfolio
            cur.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, ticker)
            )''')
            
            # Transactions
            cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                type TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            c.commit()
            c.close()
        except Exception as e:
            st.error(f"Erro init SQLite: {e}")
            
    else:
        # Supabase check
        try:
            with conn.session as session:
                session.execute(text("SELECT 1"))
                session.commit()
        except: pass

from sqlalchemy.exc import OperationalError

def run_query(query, params=None):
    """Função genérica (Supabase ou SQLite)"""
    conn = get_db_connection()
    
    if conn == "sqlite":
        try:
            # Adapt SQL (Postgres vs SQLite syntax differences if any)
            # Replace :param with ? or named style depending on driver. 
            # SQLite3 supports :name style.
            
            c = sqlite3.connect(DB_FILE)
            return pd.read_sql_query(query, c, params=params)
        except Exception as e:
            st.error(f"Erro SQLite Query: {e}")
            return pd.DataFrame()
            
    # Postgres
    try:
        if params:
            return conn.query(query, params=params, ttl=0)
        return conn.query(query, ttl=0)
    except OperationalError as e:
        # Fallback friendly message
        st.error("Erro Conexão DB Cloud.")
        raise e

def run_transaction(query, params=None):
    """Função auxiliar para ESCRITA"""
    conn = get_db_connection()
    
    if conn == "sqlite":
        try:
            c = sqlite3.connect(DB_FILE)
            cur = c.cursor()
            cur.execute(query, params if params else {})
            c.commit()
            c.close()
            return True, None
        except Exception as e:
            return False, str(e)

    # Postgres
    try:
        with conn.session as session:
            session.execute(text(query), params if params else {})
            session.commit()
        return True, None
    except Exception as e:
        return False, str(e)

# --- WALLET MANAGEMENT ---

def create_wallet(user_id, name):
    sql = "INSERT INTO wallets (user_id, name) VALUES (:u, :n)"
    success, err = run_transaction(sql, {"u": user_id, "n": name})
    if success:
        return True, "Carteira criada!"
    if "unique constraint" in str(err).lower():
         return False, "Nome de carteira já existe!"
    return False, err

def get_wallets(user_id):
    sql = "SELECT id, name FROM wallets WHERE user_id = :u ORDER BY created_at"
    df = run_query(sql, {"u": user_id})
    return df


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
             # Fetch ID back for wallet creation
             df_new = run_query("SELECT id FROM users WHERE username = :u", {"u": username})
             if not df_new.empty:
                 new_user_id = int(df_new.iloc[0]['id'])
                 create_wallet(new_user_id, "Carteira Principal")
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
                 uid = int(df_new.iloc[0]['id'])
                 create_wallet(uid, "Carteira Principal")
                 return {"id": uid, "username": username}
        else:
            st.error(f"Erro ao criar usuário no banco: {err}")
            print(f"DB Error: {err}")
        
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

def get_portfolio(user_id, wallet_id=None):
    if wallet_id and str(wallet_id).lower() != 'all' and str(wallet_id).lower() != 'todas':
         wallet_id = int(wallet_id)
         sql = """
            SELECT p.ticker, p.quantity, p.avg_price, p.last_updated_at, w.name as wallet_name, p.wallet_id
            FROM portfolio p
            LEFT JOIN wallets w ON p.wallet_id = w.id
            WHERE p.user_id = :u AND p.wallet_id = :w
         """
         params = {"u": user_id, "w": wallet_id}
    else:
         # AGGREGATED VIEW (ALL WALLETS)
         # We can return individual rows (so user sees "AAPL in Carteira A" and "AAPL in Carteira B")
         # OR we can aggregate unique tickers.
         # Requirement: "mostrar todos os ativod de todas as carteiras juntas"
         # Usually dashboard lists items. If I have AAPL in two wallets, showing them separate is better for detail, 
         # but showing aggregated is better for "Total Portfolio".
         # Let's return ALL rows with wallet info first, and frontend can group if needed or show list.
         sql = """
            SELECT p.ticker, p.quantity, p.avg_price, p.last_updated_at, w.name as wallet_name, p.wallet_id
            FROM portfolio p
            LEFT JOIN wallets w ON p.wallet_id = w.id
            WHERE p.user_id = :u
         """
         params = {"u": user_id}

    df = run_query(sql, params)
    return df

def add_to_wallet(user_id, ticker, quantity, price, wallet_id):
    # 1. Check existing in SPECIFIC WALLET
    wallet_id = int(wallet_id)
    sql_check = "SELECT quantity, avg_price FROM portfolio WHERE user_id = :u AND ticker = :t AND wallet_id = :w"
    df = run_query(sql_check, {"u": user_id, "t": ticker, "w": wallet_id})
    
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
            WHERE user_id = :u AND ticker = :t AND wallet_id = :w
        """
        success, msg = run_transaction(upd_sql, {
            "q": int(new_qty), "p": float(new_avg), "d": timestamp, "u": user_id, "t": ticker, "w": wallet_id
        })
    else:
        # Insert
        ins_sql = """
            INSERT INTO portfolio (user_id, wallet_id, ticker, quantity, avg_price, last_updated_at)
            VALUES (:u, :w, :t, :q, :p, :d)
        """
        success, msg = run_transaction(ins_sql, {
            "u": user_id, "w": wallet_id, "t": ticker, "q": int(quantity), "p": float(price), "d": timestamp
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

def update_wallet_item(user_id, ticker, new_qty, new_price, wallet_id, new_wallet_id=None):
    wallet_id = int(wallet_id)
    if new_wallet_id: new_wallet_id = int(new_wallet_id)
    
    # Logic: If new_wallet_id is provided and different, we are MOVING.
    if new_wallet_id and new_wallet_id != wallet_id:
        # 1. Check if target wallet already has this ticker
        check_sql = "SELECT quantity, avg_price FROM portfolio WHERE user_id = :u AND ticker = :t AND wallet_id = :w"
        target_df = run_query(check_sql, {"u": user_id, "t": ticker, "w": new_wallet_id})
        
        if not target_df.empty:
            # MERGE SCENARIO
            # Target has items. We are "Adding" the edited amount to the target? 
            # Or are we saying "The Moved Item becomes part of the Target"? 
            # Usually strict move: Target = Target + Source(Edited).
            row_t = target_df.iloc[0]
            t_qty = row_t['quantity']
            t_avg = row_t['avg_price']
            
            # Merged Math
            final_qty = t_qty + new_qty
            if final_qty > 0:
                final_avg = ((t_qty * t_avg) + (new_qty * new_price)) / final_qty
            else:
                final_avg = 0
            
            # Transaction: Update Target, Delete Source
            # Note: run_transaction does one statement. We might need specific handling or just do two calls (since we don't have stored procs easily usable)
            # For safety, simplest is 2 calls, small risk of incosistency if crash in between.
            # Ideally verify support for multi-statement in run_transaction or adjust it.
            # Our run_transaction does: `session.execute(text(query))`
            # We can pack multiple statements in one SQL block with SQLAlchemy text.
            
            merge_sql = """
                UPDATE portfolio 
                SET quantity = :q, avg_price = :p, last_updated_at = :d 
                WHERE user_id = :u AND ticker = :t AND wallet_id = :new_w;
                
                DELETE FROM portfolio 
                WHERE user_id = :u AND ticker = :t AND wallet_id = :old_w;
            """
            
            success, msg = run_transaction(merge_sql, {
                "q": int(final_qty), "p": float(final_avg), "d": datetime.datetime.now(),
                "u": user_id, "t": ticker, "new_w": new_wallet_id, "old_w": wallet_id
            })
            if success: return True, "Ativo movido e unificado com sucesso!"
            return False, msg

        else:
            # MOVE SCENARIO (No collision)
            # Just update wallet_id along with other fields
            sql = """
                UPDATE portfolio 
                SET quantity = :q, avg_price = :p, last_updated_at = :d, wallet_id = :new_w
                WHERE user_id = :u AND ticker = :t AND wallet_id = :old_w
            """
            success, msg = run_transaction(sql, {
                "q": int(new_qty), "p": float(new_price), "d": datetime.datetime.now(),
                "u": user_id, "t": ticker, "new_w": new_wallet_id, "old_w": wallet_id
            })
            if success: return True, "Ativo movido de carteira!"
            return False, msg

    else:
        # NORMAL UPDATE (Same Wallet)
        sql = """
            UPDATE portfolio 
            SET quantity = :q, avg_price = :p, last_updated_at = :d 
            WHERE user_id = :u AND ticker = :t AND wallet_id = :w
        """
        success, msg = run_transaction(sql, {
            "q": int(new_qty), "p": float(new_price), 
            "d": datetime.datetime.now(), "u": user_id, "t": ticker, "w": wallet_id
        })
        if success: return True, "Atualizado!"
        return False, msg

def remove_from_wallet(user_id, ticker, wallet_id):
    wallet_id = int(wallet_id)
    sql = "DELETE FROM portfolio WHERE user_id = :u AND ticker = :t AND wallet_id = :w"
    success, msg = run_transaction(sql, {"u": user_id, "t": ticker, "w": wallet_id})
    
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
