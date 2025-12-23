import sqlite3
import bcrypt
import datetime
import pandas as pd
import os

DB_NAME = "market_hacking.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            google_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de Sessões (Cookies)
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Tabela de Carteira (Portfolio)
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, ticker)
        )
    ''')
    
    # Tabela de Transações (Histórico)
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            type TEXT NOT NULL, -- BUY, SELL
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# --- AUTENTICAÇÃO ---
def create_user(username, password, email=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)", 
                  (username, hashed, email))
        conn.commit()
        return True, "Usuário criado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Usuário já existe!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
        return {"id": user[0], "username": user[1]}
    return None

def login_google_user(email, google_id):
    """Loga ou cria usuário via Google"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Verifica se já existe por email
        c.execute("SELECT id, username FROM users WHERE email = ? OR google_id = ?", (email, google_id))
        user = c.fetchone()
        
        if user:
            # Atualiza google_id se não tiver
            c.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user[0]))
            conn.commit()
            return {"id": user[0], "username": user[1]}
        else:
            # Cria novo
            username = email.split('@')[0]
            # Adiciona sufixo se username já existir
            c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if c.fetchone(): username = f"{username}_{int(datetime.datetime.now().timestamp())}"
            
            c.execute("INSERT INTO users (username, email, google_id, password_hash) VALUES (?, ?, ?, ?)", 
                      (username, email, google_id, "GOOGLE_AUTH_NO_PASS"))
            user_id = c.lastrowid
            conn.commit()
            return {"id": user_id, "username": username}
    except Exception as e:
        print(f"Erro DB Google: {e}")
        return None
    finally:
        conn.close()

# --- SESSÃO (COOKIES) ---
def create_session(user_id):
    """Cria uma sessão persistente"""
    import uuid
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    token = str(uuid.uuid4())
    try:
        c.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        conn.commit()
        return token
    except Exception as e:
        print(f"Erro Session: {e}")
        return None
    finally:
        conn.close()

def get_user_by_session(token):
    """Valida sessão"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT u.id, u.username, u.email 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    ''', (token,))
    user = c.fetchone()
    conn.close()
    if user:
        return {"id": user[0], "username": user[1]}
    return None

def delete_session(token):
    """Logout"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def delete_all_user_sessions(user_id):
    """Logout Nuclear: Remove todas as sessões do usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Erro ao deletar sessõe: {e}")
    finally:
        conn.close()

# --- CARTEIRA ---
def get_portfolio(user_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM portfolio WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def add_to_wallet(user_id, ticker, quantity, price):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Verificar se já existe
        c.execute("SELECT quantity, avg_price FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        row = c.fetchone()
        
        if row:
            # Atualizar Preço Médio
            old_qty, old_avg = row
            new_qty = old_qty + quantity
            if new_qty > 0:
                new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
            else:
                new_avg = 0 # Zerou posição
            
            c.execute("UPDATE portfolio SET quantity = ?, avg_price = ?, last_updated_at = ? WHERE user_id = ? AND ticker = ?",
                      (new_qty, new_avg, datetime.datetime.now(), user_id, ticker))
        else:
            # Novo item
            c.execute("INSERT INTO portfolio (user_id, ticker, quantity, avg_price) VALUES (?, ?, ?, ?)",
                      (user_id, ticker, quantity, price))
        
        # Registrar Transação
        c.execute("INSERT INTO transactions (user_id, ticker, quantity, price, type) VALUES (?, ?, ?, ?, ?)",
                  (user_id, ticker, quantity, price, "BUY" if quantity > 0 else "SELL"))
        
        conn.commit()
        return True, "Carteira atualizada!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_wallet_item(user_id, ticker, new_qty, new_price):
    """Edição Manual (Lápis) - Substitui valores"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE portfolio SET quantity = ?, avg_price = ?, last_updated_at = ? WHERE user_id = ? AND ticker = ?",
                  (new_qty, new_price, datetime.datetime.now(), user_id, ticker))
        conn.commit()
        return True, "Item atualizado manualmente!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remove_from_wallet(user_id, ticker):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        
        # Registrar Transação de Saída (opcional, só para constar)
        c.execute("INSERT INTO transactions (user_id, ticker, quantity, price, type) VALUES (?, ?, ?, ?, ?)",
                  (user_id, ticker, 0, 0, "REMOVE"))
                  
        conn.commit()
        return True, "Item removido da carteira!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# Inicializa ao importar se não existir
# Inicializa ao importar (Safe com IF NOT EXISTS)
init_db()
