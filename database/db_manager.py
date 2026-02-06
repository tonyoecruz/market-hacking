"""
Database Manager for Market Data - SCOPE3
Handles all database operations for stocks, ETFs, FIIs
"""
import os
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd

from database.orm_models import Base, StockDB, ETFDB, FIIDB, UpdateLogDB


# Database URL - SQLite para local, PostgreSQL para produção (Render/Supabase)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./market_data.db')

# CORREÇÃO TÉCNICA: O SQLAlchemy exige que a URL comece com postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Manager class for all database operations"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def save_stock(self, stock_data: Dict):
        """Save or update stock data"""
        db = self.SessionLocal()
        try:
            ticker = stock_data['ticker'].upper()
            existing = db.query(StockDB).filter(StockDB.ticker == ticker).first()
            
            if existing:
                for key, value in stock_data.items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.now()
            else:
                new_stock = StockDB(**stock_data)
                db.add(new_stock)
            
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def get_all_stocks(self, market: Optional[str] = None) -> List[StockDB]:
        """Get all stocks from database"""
        db = self.SessionLocal()
        try:
            query = db.query(StockDB)
            if market:
                query = query.filter(StockDB.market == market)
            return query.all()
        finally:
            db.close()