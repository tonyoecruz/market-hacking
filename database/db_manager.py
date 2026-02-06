import os
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd
from database.orm_models import Base, StockDB, ETFDB, FIIDB, UpdateLogDB

# CORREÇÃO: Forçar driver postgresql para compatibilidade com SQLAlchemy
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./market_data.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_database():
    Base.metadata.create_all(bind=engine)
    print("✅ Banco de Dados Inicializado")

class DatabaseManager:
    def __init__(self):
        self.SessionLocal = SessionLocal

    def get_stocks(self, market: Optional[str] = None, min_liq: Optional[float] = None) -> List[Dict]:
        db = self.SessionLocal()
        try:
            query = db.query(StockDB)
            if market: query = query.filter(StockDB.market == market)
            if min_liq: query = query.filter(StockDB.liquidezmediadiaria >= min_liq)
            return [stock.to_dict() for stock in query.all()]
        finally:
            db.close()

    def get_stock_by_ticker(self, ticker: str, market: str) -> Optional[Dict]:
        db = self.SessionLocal()
        try:
            stock = db.query(StockDB).filter(and_(StockDB.ticker == ticker, StockDB.market == market)).first()
            return stock.to_dict() if stock else None
        finally:
            db.close()