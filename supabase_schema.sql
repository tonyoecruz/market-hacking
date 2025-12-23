-- RODE ESTE SCRIPT NO "SQL EDITOR" DO SEU PAINEL SUPABASE
-- Ele cria as tabelas necessárias para o Scope3 Ultimate

-- 1. TABELA DE USUÁRIOS
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    google_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. TABELA DE SESSÕES (Login persistente)
CREATE TABLE IF NOT EXISTS sessions (
    token VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. TABELA DE PORTFÓLIO (Carteira atual)
CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price FLOAT NOT NULL,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_ticker UNIQUE (user_id, ticker)
);

-- 4. TABELA DE TRANSAÇÕES (Histórico)
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    price FLOAT NOT NULL,
    type VARCHAR(10) NOT NULL, -- 'BUY', 'SELL', 'REMOVE'
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices úteis para performance
CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
