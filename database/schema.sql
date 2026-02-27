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
    dy FLOAT,
    div_pat FLOAT,
    liquidezmediadiaria FLOAT,
    valor_justo FLOAT,
    margem FLOAT,
    magic_rank FLOAT,
    cagr_lucros FLOAT,
    liq_corrente FLOAT,
    roe FLOAT,
    roa FLOAT,
    margem_liquida FLOAT,
    ev_ebitda FLOAT,
    payout FLOAT,
    valor_mercado FLOAT,
    div_liq_ebitda FLOAT,
    -- NEW: Full StatusInvest API columns (V3.0)
    p_ebit FLOAT,
    p_sr FLOAT,
    peg_ratio FLOAT,
    p_ativo FLOAT,
    p_capital_giro FLOAT,
    p_ativo_circulante FLOAT,
    giro_ativos FLOAT,
    margem_bruta FLOAT,
    margem_ebit FLOAT,
    pl_ativo FLOAT,
    passivo_ativo FLOAT,
    cagr_receitas FLOAT,
    queda_maximo FLOAT,
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

-- Table: flipping_listings (cached property scan results)
CREATE TABLE IF NOT EXISTS flipping_listings (
    id SERIAL PRIMARY KEY,
    city VARCHAR(200) NOT NULL,
    bairro VARCHAR(200),
    tipo VARCHAR(100),
    imobiliaria VARCHAR(300),
    referencia VARCHAR(200),
    area_m2 FLOAT,
    valor_total FLOAT,
    valor_m2 FLOAT,
    media_setor_m2 FLOAT,
    desconto_pct FLOAT,
    link VARCHAR(500),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
CREATE INDEX IF NOT EXISTS idx_update_logs_status ON update_logs(status);
CREATE INDEX IF NOT EXISTS idx_flipping_city ON flipping_listings(city);
