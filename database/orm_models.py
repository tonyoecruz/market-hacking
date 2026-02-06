"""
SQLAlchemy ORM Models for Market Data
Database tables for stocks, ETFs, FIIs, and update tracking
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
    liquidezmediadiaria = Column(Float)
    valor_justo = Column(Float)
    margem = Column(Float)
    magic_rank = Column(Float)
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
            'liquidezmediadiaria': self.liquidezmediadiaria,
            'valor_justo': self.valor_justo,
            'margem': self.margem,
            'MagicRank': self.magic_rank,
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
