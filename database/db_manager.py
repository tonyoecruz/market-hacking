"""
Database Manager for Market Data
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


# Database URL - SQLite for local, PostgreSQL for production
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./market_data.db')

# CORREÇÃO: Forçar driver postgresql para compatibilidade com SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
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
    
    # ==================== STOCKS ====================
    
    def save_stocks(self, df: pd.DataFrame, market: str) -> int:
        """
        Save or update stocks from DataFrame
        Returns: number of records saved
        """
        db = self.SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                stock = db.query(StockDB).filter(
                    and_(StockDB.ticker == row['ticker'], StockDB.market == market)
                ).first()
                
                if stock:
                    # Update existing
                    for key, value in row.items():
                        if key == 'MagicRank':
                            setattr(stock, 'magic_rank', value)
                        elif hasattr(stock, key):
                            setattr(stock, key, value)
                    stock.updated_at = datetime.now()
                else:
                    # Create new
                    stock_data = row.to_dict()
                    if 'MagicRank' in stock_data:
                        stock_data['magic_rank'] = stock_data.pop('MagicRank')
                    stock_data['market'] = market
                    stock = StockDB(**stock_data)
                    db.add(stock)
                
                count += 1
            
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_stocks(self, market: Optional[str] = None, min_liq: Optional[float] = None) -> List[Dict]:
        """Get stocks from database"""
        db = self.SessionLocal()
        try:
            query = db.query(StockDB)
            
            if market:
                query = query.filter(StockDB.market == market)
            
            if min_liq:
                query = query.filter(StockDB.liquidezmediadiaria >= min_liq)
            
            stocks = query.all()
            return [stock.to_dict() for stock in stocks]
        finally:
            db.close()
    
    def get_stock_by_ticker(self, ticker: str, market: str) -> Optional[Dict]:
        """Get single stock by ticker"""
        db = self.SessionLocal()
        try:
            stock = db.query(StockDB).filter(
                and_(StockDB.ticker == ticker, StockDB.market == market)
            ).first()
            return stock.to_dict() if stock else None
        finally:
            db.close()
    
    # ==================== ETFs ====================
    
    def save_etfs(self, df: pd.DataFrame, market: str) -> int:
        """Save or update ETFs from DataFrame"""
        db = self.SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                etf = db.query(ETFDB).filter(ETFDB.ticker == row['ticker']).first()
                
                if etf:
                    # Update existing
                    for key, value in row.items():
                        if hasattr(etf, key):
                            setattr(etf, key, value)
                    etf.updated_at = datetime.now()
                else:
                    # Create new
                    etf_data = row.to_dict()
                    etf_data['market'] = market
                    etf = ETFDB(**etf_data)
                    db.add(etf)
                
                count += 1
            
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_etfs(self, market: Optional[str] = None) -> List[Dict]:
        """Get ETFs from database"""
        db = self.SessionLocal()
        try:
            query = db.query(ETFDB)
            
            if market:
                query = query.filter(ETFDB.market == market)
            
            etfs = query.all()
            return [etf.to_dict() for etf in etfs]
        finally:
            db.close()
    
    # ==================== FIIs ====================
    
    def save_fiis(self, df: pd.DataFrame, market: str) -> int:
        """Save or update FIIs from DataFrame"""
        db = self.SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                fii = db.query(FIIDB).filter(FIIDB.ticker == row['ticker']).first()
                
                if fii:
                    # Update existing
                    for key, value in row.items():
                        if hasattr(fii, key):
                            setattr(fii, key, value)
                    fii.updated_at = datetime.now()
                else:
                    # Create new
                    fii_data = row.to_dict()
                    fii_data['market'] = market
                    fii = FIIDB(**fii_data)
                    db.add(fii)
                
                count += 1
            
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_fiis(self, market: Optional[str] = None, min_dy: Optional[float] = None) -> List[Dict]:
        """Get FIIs from database"""
        db = self.SessionLocal()
        try:
            query = db.query(FIIDB)
            
            if market:
                query = query.filter(FIIDB.market == market)
            
            if min_dy:
                query = query.filter(FIIDB.dy >= min_dy)
            
            fiis = query.all()
            return [fii.to_dict() for fii in fiis]
        finally:
            db.close()
    
    # ==================== UPDATE LOGS ====================
    
    def log_update(
        self,
        asset_type: str,
        market: str,
        status: str,
        records_updated: int = 0,
        error_message: str = None,
        started_at: datetime = None,
        completed_at: datetime = None
    ) -> int:
        """Log an update operation"""
        db = self.SessionLocal()
        try:
            duration = None
            if started_at and completed_at:
                duration = int((completed_at - started_at).total_seconds())
            
            log = UpdateLogDB(
                asset_type=asset_type,
                market=market,
                status=status,
                records_updated=records_updated,
                error_message=error_message,
                started_at=started_at or datetime.now(),
                completed_at=completed_at or datetime.now(),
                duration_seconds=duration
            )
            
            db.add(log)
            db.commit()
            return log.id
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_last_update(self, asset_type: str, market: Optional[str] = None) -> Optional[Dict]:
        """Get last successful update for asset type"""
        db = self.SessionLocal()
        try:
            query = db.query(UpdateLogDB).filter(
                and_(
                    UpdateLogDB.asset_type == asset_type,
                    UpdateLogDB.status == 'success'
                )
            )
            
            if market:
                query = query.filter(UpdateLogDB.market == market)
            
            log = query.order_by(UpdateLogDB.completed_at.desc()).first()
            return log.to_dict() if log else None
        finally:
            db.close()
    
    def get_update_logs(self, limit: int = 50) -> List[Dict]:
        """Get recent update logs"""
        db = self.SessionLocal()
        try:
            logs = db.query(UpdateLogDB).order_by(
                UpdateLogDB.completed_at.desc()
            ).limit(limit).all()
            return [log.to_dict() for log in logs]
        finally:
            db.close()
    
    # ==================== UTILITY ====================
    
    def cleanup_old_data(self, days: int = 7):
        """Remove data older than specified days"""
        db = self.SessionLocal()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Delete old logs
            db.query(UpdateLogDB).filter(
                UpdateLogDB.completed_at < cutoff_date
            ).delete()
            
            db.commit()
            print(f"✅ Cleaned up data older than {days} days")
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        db = self.SessionLocal()
        try:
            stats = {
                'stocks_count': db.query(StockDB).count(),
                'stocks_br_count': db.query(StockDB).filter(StockDB.market == 'BR').count(),
                'stocks_us_count': db.query(StockDB).filter(StockDB.market == 'US').count(),
                'etfs_count': db.query(ETFDB).count(),
                'fiis_count': db.query(FIIDB).count(),
                'total_updates': db.query(UpdateLogDB).count(),
                'last_update': None
            }
            
            # Get most recent update
            last_log = db.query(UpdateLogDB).order_by(
                UpdateLogDB.completed_at.desc()
            ).first()
            
            if last_log:
                stats['last_update'] = last_log.completed_at.isoformat()
            
            return stats
        finally:
            db.close()


# Global instance
db_manager = DatabaseManager()