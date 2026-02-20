"""
SQLAlchemy ORM Models for Market Data
Database tables for stocks, ETFs, FIIs, update tracking, and system settings
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class StockDB(Base):
    """SQLAlchemy model for stocks (Brazilian and US markets)"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False)
    market = Column(String(50), nullable=False)  # 'BR' or 'US'
    empresa = Column(String(200))
    setor = Column(String(100))
    price = Column(Float)
    lpa = Column(Float)
    vpa = Column(Float)
    pl = Column(Float)
    pvp = Column(Float)
    roic = Column(Float)
    ev_ebit = Column(Float)
    dy = Column(Float)
    liquidezmediadiaria = Column(Float)
    div_pat = Column(Float)          # Dívida Líquida / Patrimônio
    valor_justo = Column(Float)
    margem = Column(Float)           # Margem de segurança Graham
    magic_rank = Column(Float)
    cagr_lucros = Column(Float)      # CAGR Lucros 5 anos (lucpidasNet5Years via StatusInvest)
    liq_corrente = Column(Float)     # Liquidez Corrente (liquidezCorrente via StatusInvest)
    # ── NEW: Hybrid Screener V2.0 columns ────────────────────────────────────
    margem_liquida  = Column(Float)  # Margem Líquida %  (margemLiquida via StatusInvest)
    ev_ebitda       = Column(Float)  # EV/EBITDA         (eV_Ebitda via StatusInvest)
    payout          = Column(Float)  # Payout %          (payout via StatusInvest)
    valor_mercado   = Column(Float)  # Valor de Mercado  (valordemercado via StatusInvest)
    div_liq_ebitda  = Column(Float)  # Dív.Líq/EBIT      (dividaLiquidaEbit via StatusInvest)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('ticker', 'market', name='uix_ticker_market'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'ticker': self.ticker,
            'market': self.market,
            'empresa': self.empresa,
            'setor': self.setor,
            'price': self.price,
            'lpa': self.lpa,
            'vpa': self.vpa,
            'pl': self.pl,
            'pvp': self.pvp,
            'roic': self.roic,
            'ev_ebit': self.ev_ebit,
            'dy': self.dy,
            'liquidezmediadiaria': self.liquidezmediadiaria,
            'div_pat': self.div_pat,
            'valor_justo': self.valor_justo,
            'margem': self.margem,
            'magic_rank': self.magic_rank,
            'cagr_lucros': getattr(self, 'cagr_lucros', None),
            'liq_corrente': getattr(self, 'liq_corrente', None),
            'margem_liquida':  getattr(self, 'margem_liquida', None),
            'ev_ebitda':       getattr(self, 'ev_ebitda', None),
            'payout':          getattr(self, 'payout', None),
            'valor_mercado':   getattr(self, 'valor_mercado', None),
            'div_liq_ebitda':  getattr(self, 'div_liq_ebitda', None),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ETFDB(Base):
    """SQLAlchemy model for ETFs"""
    __tablename__ = 'etfs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True)
    market = Column(String(50), nullable=False)
    empresa = Column(String(200))
    price = Column(Float)
    liquidezmediadiaria = Column(Float)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'ticker': self.ticker,
            'market': self.market,
            'empresa': self.empresa,
            'price': self.price,
            'liquidezmediadiaria': self.liquidezmediadiaria,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class FIIDB(Base):
    """SQLAlchemy model for FIIs (Real Estate Investment Funds)"""
    __tablename__ = 'fiis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True)
    market = Column(String(50), nullable=False)
    price = Column(Float)
    dy = Column(Float)
    pvp = Column(Float)
    liquidezmediadiaria = Column(Float)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'ticker': self.ticker,
            'market': self.market,
            'price': self.price,
            'dy': self.dy,
            'pvp': self.pvp,
            'liquidezmediadiaria': self.liquidezmediadiaria,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class UpdateLogDB(Base):
    """SQLAlchemy model for tracking data update operations"""
    __tablename__ = 'update_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_type = Column(String(20), nullable=False)  # 'stocks', 'etfs', 'fiis'
    market = Column(String(50))
    status = Column(String(20), nullable=False)  # 'success', 'error'
    records_updated = Column(Integer)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'asset_type': self.asset_type,
            'market': self.market,
            'status': self.status,
            'records_updated': self.records_updated,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds
        }


class SystemSettingsDB(Base):
    """SQLAlchemy model for persistent system settings"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(String(500), nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class FlippingCityDB(Base):
    """SQLAlchemy model for House Flipping city list"""
    __tablename__ = 'flipping_cities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(200), nullable=False, unique=True)
    state = Column(String(50))
    active = Column(Integer, default=1)  # 1=active, 0=inactive
    added_at = Column(DateTime, default=func.now())
    last_scraped_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'city': self.city,
            'state': self.state,
            'active': bool(self.active),
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'last_scraped_at': self.last_scraped_at.isoformat() if self.last_scraped_at else None
        }


class InvestorPersonaDB(Base):
    """SQLAlchemy model for investor personas (e.g. Warren Buffett, Luiz Barsi)"""
    __tablename__ = 'investor_personas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(String(500))
    style_prompt = Column(Text)  # AI prompt prefix describing the investor's style
    voice_id = Column(String(100), default='pt-BR-AntonioNeural')
    active = Column(Integer, default=1)
    added_at = Column(DateTime, default=func.now())

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'style_prompt': self.style_prompt,
            'voice_id': self.voice_id,
            'active': bool(self.active),
            'added_at': self.added_at.isoformat() if self.added_at else None
        }

