import streamlit as st
import bcrypt
import datetime
import pandas as pd
import uuid
from sqlalchemy import text

# --- DATABASE CONNECTION (Native Streamlit/Supabase) ---

def get_db_connection():
    """Conecta ao Supabase usando a configuração [connections.postgresql] do secrets.toml"""
    try:
        # ttl=0 garante que não cacheie a conexão incorretamente
        conn = st.connection("postgresql", type="sql")
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def init_db():
    """Função para inicializar/verificar o banco"""
    conn = get_db_connection()
    if conn is None:
        return
    
    # Teste simples de conexão
    try:
        with conn.session as session:
            session.execute(text("SELECT 1"))
            session.commit()
    except Exception as e:
        st.error(f"Erro ao verificar o banco de dados: {e}")

from sqlalchemy.exc import OperationalError

def run_query(query, params=None):
    """Função genérica para rodar comandos SQL de LEITURA (Retorna DataFrame)"""
    conn = get_db_connection()
    try:
        # ttl=0 desativa cache global para evitar dados obsoletos
        if params:
            return conn.query(query, params=params, ttl=0)
        return conn.query(query, ttl=0)
    except OperationalError as e:
        st.error("🔴 ERRO DE CONEXÃO COM SUPABASE")
        st.warning(
            "Dica: O Streamlit Cloud usa IPv4. O Supabase direto (porta 5432) pode ser IPv6-only.\n"
            "Solução: Use a URL do 'Connection Pooler' (porta 6543) no Supabase Settings > Database.\n"
            "E certifique-se de usar 'postgresql://' em vez de 'postgres://'."
        )
        raise e

def run_transaction(query, params=None):
    """Função auxiliar para ESCRITA (INSERT/UPDATE/DELETE)"""
    conn = get_db_connection()
    try:
        with conn.session as session:
            session.execute(text(query), params if params else {})
            session.commit()
        return True, None
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
        
        return None

# --- SESSIONS ---

def create_session(user_id):
    token = str(uuid.uuid4())
    sql = "INSERT INTO sessions (token, user_id) VALUES (:t, :u)"
    run_transaction(sql, {"t": token, "u": user_id})
    return token

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
# init_db()
