-- Create tables for Market Hacking application
-- Run this in Supabase SQL Editor

-- Table: stocks
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(50) NOT NULL,
    empresa VARCHAR(200),
    setor VARCHAR(100),
    price FLOAT,
    lpa FLOAT,
    vpa FLOAT,
    pl FLOAT,
    pvp FLOAT,
    roic FLOAT,
    ev_ebit FLOAT,
    liquidezmediadiaria FLOAT,
    valor_justo FLOAT,
    margem FLOAT,
    magic_rank FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_ticker_market UNIQUE (ticker, market)
);

-- Table: etfs
CREATE TABLE IF NOT EXISTS etfs (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    market VARCHAR(50) NOT NULL,
    empresa VARCHAR(200),
    price FLOAT,
    liquidezmediadiaria FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: fiis
CREATE TABLE IF NOT EXISTS fiis (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    market VARCHAR(50) NOT NULL,
    price FLOAT,
    dy FLOAT,
    pvp FLOAT,
    liquidezmediadiaria FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: update_logs
CREATE TABLE IF NOT EXISTS update_logs (
    id SERIAL PRIMARY KEY,
    asset_type VARCHAR(20) NOT NULL,
    market VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    records_updated INTEGER,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
CREATE INDEX IF NOT EXISTS idx_update_logs_status ON update_logs(status);
