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
        
        # MIGRATION ON THE FLY (Self-Healing)
        # Check if wallet_id column exists, if not add it (Postgres specific but robust enough)
        try:
             # Fast check if column exists is hard without specific catalog query.
             # We can just try to insert with wallet_id or alter table blindly if we handle error?
             # Better: Use the column in the INSERT. If it fails, we assume valid column needs to be added?
             # Actually, let's just run an insensitive ALTER TABLE ADD IF NOT EXISTS or similar.
             # Postgres `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` is standard from v9.6+.
             run_transaction("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS wallet_id BIGINT")
        except: pass
        
        log_sql = """
            INSERT INTO transactions (user_id, ticker, quantity, price, type, date, wallet_id)
            VALUES (:u, :t, :q, :p, :tp, :d, :w)
        """
        run_transaction(log_sql, {
            "u": user_id, "t": ticker, "q": int(quantity), 
            "p": float(price), "tp": tr_type, "d": timestamp, "w": wallet_id
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

def ensure_migrations():
    """Garante que a estrutura do banco esteja atualizada"""
    conn = get_db_connection()
    try:
        # Check if column exists by selecting it (limit 0)
        # This is db-agnostic enough for our needs
        conn.query("SELECT wallet_id FROM transactions LIMIT 1", ttl=0)
        return True
    except Exception:
        # Dictionary query failed, likely column missing. Try adding it.
        print("Migrating: Adding wallet_id to transactions...")
        try:
             # Force a raw connection execute if possible, or use run_transaction
             # Using run_transaction which wraps session
             run_transaction("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS wallet_id BIGINT")
             return True
        except Exception as e2:
             st.error(f"FATAL DB MIGRATION ERROR: {e2}")
             return False

def get_transactions(user_id):
    ensure_migrations() # Attempt migration
    
    # Try the full query
    try:
        sql = "SELECT ticker, quantity, price, type, date, wallet_id FROM transactions WHERE user_id = :u ORDER BY date ASC"
        return run_query(sql, {"u": user_id})
    except Exception:
        # Fallback for when migration completely fails (avoids app crash)
        # Return without wallet_id
        sql_fallback = "SELECT ticker, quantity, price, type, date FROM transactions WHERE user_id = :u ORDER BY date ASC"
        df = run_query(sql_fallback, {"u": user_id})
        if not df.empty:
            df['wallet_id'] = None # Manually add column so app.py logic doesn't break
        return df

# Initialize (Optional now as we don't create tables in code, but good validation)
# init_db()
