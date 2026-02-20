"""
Database Manager for Market Data
Handles all database operations for stocks, ETFs, FIIs
"""
import os
import logging
from sqlalchemy import create_engine, and_, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd
import numpy as np

from database.orm_models import Base, StockDB, ETFDB, FIIDB, UpdateLogDB, SystemSettingsDB, FlippingCityDB, InvestorPersonaDB

logger = logging.getLogger(__name__)


# Database URL - SQLite for local, PostgreSQL for production
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./market_data.db')

# CORREÇÃO: Forçar driver postgresql para compatibilidade com SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Logging database connection
if 'sqlite' in DATABASE_URL:
    logger.warning("⚠️  USING LOCAL SQLITE DATABASE - Data will not persist on Render!")
    logger.info(f"📂 Database file: {DATABASE_URL}")
    
    # Warn if running in likely cloud environment
    if os.getenv('RENDER') or os.getenv('PORT'):
        logger.error("❌ CLOUD ENVIRONMENT DETECTED WITHOUT 'DATABASE_URL'!")
        logger.error("👉 Please set DATABASE_URL (PostgreSQL) in Render Environment Variables.")
else:
    logger.info("🔌 Connecting to PostgreSQL database...")
    # Mask password for security
    safe_url = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '***'
    logger.info(f"🔗 Host: {safe_url}")

# Database Connection Configuration
connect_args = {}
engine_args = {
    "echo": False,
    "pool_pre_ping": True
}

# Check if using Supavisor (Transaction Mode) - Port 6543
if ':6543' in DATABASE_URL:
    logger.info("⚡ Using Supabase Connection Pooler (Transaction Mode)")
    from sqlalchemy.pool import NullPool
    engine_args["poolclass"] = NullPool
    # Reduce overhead for pooler connection
    engine_args["pool_pre_ping"] = False

# Create engine
engine = create_engine(
    DATABASE_URL,
    **engine_args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database():
    """Initialize database tables and run migrations for new columns"""
    Base.metadata.create_all(bind=engine)

    # Migrate existing tables: add columns that may not exist yet
    _migrate_columns = [
        ("stocks", "dy", "FLOAT"),
        ("stocks", "div_pat", "FLOAT"),
        ("stocks", "roe_si", "FLOAT"),          # ROE direto do StatusInvest
        ("stocks", "cagr_lucros", "FLOAT"),     # CAGR Lucros 5 anos
        ("stocks", "liq_corrente", "FLOAT"),    # Liquidez Corrente
        ("investor_personas", "voice_id", "VARCHAR(100) DEFAULT 'pt-BR-AntonioNeural'"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in _migrate_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                print(f"  + Added column {table}.{column}")
            except Exception:
                # Column already exists
                pass

    print("Database initialized successfully")


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
        Save or update stocks from DataFrame using optimized batch processing
        Returns: number of records saved
        """
        db = self.SessionLocal()
        try:
            # 1. Sanitize Data (CRITICAL: Replace NaN with None)
            df = df.replace({pd.NA: None, float('nan'): None, np.nan: None})
            
            # Remove duplicate tickers
            df = df.drop_duplicates(subset=['ticker'], keep='first')
            
            # Valid columns
            valid_columns = [
                'ticker', 'market', 'empresa', 'setor', 'price', 'lpa', 'vpa',
                'pl', 'pvp', 'roic', 'ev_ebit', 'dy', 'liquidezmediadiaria', 'div_pat',
                'valor_justo', 'margem', 'magic_rank',
                'roe_si', 'cagr_lucros', 'liq_corrente',  # new fields from StatusInvest
                'ValorJusto', 'Margem', 'MagicRank'
            ]
            
            # 2. Get existing tickers for this market (Bulk Query)
            existing_tickers = set(
                x[0] for x in db.query(StockDB.ticker).filter(StockDB.market == market).all()
            )
            
            new_objects = []
            count = 0
            
            for _, row in df.iterrows():
                ticker = str(row['ticker']).strip().upper()
                
                # Filter valid columns
                stock_data = {k: v for k, v in row.to_dict().items() if k in valid_columns}
                
                # Remap columns
                if 'MagicRank' in stock_data: stock_data['magic_rank'] = stock_data.pop('MagicRank')
                if 'ValorJusto' in stock_data: stock_data['valor_justo'] = stock_data.pop('ValorJusto')
                if 'Margem' in stock_data: stock_data['margem'] = stock_data.pop('Margem')
                
                stock_data['ticker'] = ticker
                stock_data['market'] = market
                stock_data['updated_at'] = datetime.now()
                
                if ticker in existing_tickers:
                    # UPDATE (Use update statement if possible, but ORM update is fine for now)
                    # For massive updates, bulk_update_mappings is better, but this loop is safer for now
                    db.query(StockDB).filter(and_(StockDB.ticker == ticker, StockDB.market == market)).update(stock_data)
                else:
                    # INSERT (Collect for bulk insert)
                    new_objects.append(StockDB(**stock_data))
                
                count += 1
                
                # Commit updates in chunks to avoid timeout
                if count % 200 == 0:
                    db.commit()
            
            # Bulk Insert New Records
            if new_objects:
                db.bulk_save_objects(new_objects)
            
            db.commit()
            logger.info(f"Successfully saved {count} {market} stocks ({len(new_objects)} new)")
            return count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in save_stocks ({market}): {str(e)}", exc_info=True)
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
    
    def search_assets(self, query: str, limit: int = 20) -> List[Dict]:
        """Search stocks, ETFs, and FIIs by ticker across all markets"""
        db = self.SessionLocal()
        try:
            pattern = f"%{query.upper()}%"
            results = []
            
            # Search stocks
            stocks = db.query(StockDB).filter(
                StockDB.ticker.ilike(pattern)
            ).limit(limit).all()
            for s in stocks:
                d = s.to_dict()
                d['asset_type'] = 'stock'
                results.append(d)
            
            # Search ETFs
            etfs = db.query(ETFDB).filter(
                ETFDB.ticker.ilike(pattern)
            ).limit(limit).all()
            for e in etfs:
                d = e.to_dict()
                d['asset_type'] = 'etf'
                results.append(d)
            
            # Search FIIs
            fiis = db.query(FIIDB).filter(
                FIIDB.ticker.ilike(pattern)
            ).limit(limit).all()
            for f in fiis:
                d = f.to_dict()
                d['asset_type'] = 'fii'
                results.append(d)
            
            return results[:limit]
        finally:
            db.close()
    
    # ==================== ETFs ====================
    
    def save_etfs(self, df: pd.DataFrame, market: str) -> int:
        """Save or update ETFs using optimized batch processing"""
        db = self.SessionLocal()
        try:
            # Sanitize Data
            df = df.replace({pd.NA: None, float('nan'): None, np.nan: None})
            
            valid_columns = ['ticker', 'market', 'empresa', 'price', 'liquidezmediadiaria']
            
            # Bulk Query Existing
            existing_tickers = set(
                x[0] for x in db.query(ETFDB.ticker).filter(ETFDB.market == market).all()
            )
            
            new_objects = []
            count = 0
            
            for _, row in df.iterrows():
                ticker = row['ticker']
                etf_data = {k: v for k, v in row.to_dict().items() if k in valid_columns}
                if 'market' not in etf_data: etf_data['market'] = market
                
                if ticker in existing_tickers:
                    # Update
                    etf_data['updated_at'] = datetime.now()
                    db.query(ETFDB).filter(ETFDB.ticker == ticker).update(etf_data)
                else:
                    # Insert
                    new_objects.append(ETFDB(**etf_data))
                count += 1
            
            if new_objects:
                db.bulk_save_objects(new_objects)
            
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
        """Save or update FIIs using optimized batch processing"""
        db = self.SessionLocal()
        try:
            # Sanitize Data
            df = df.replace({pd.NA: None, float('nan'): None, np.nan: None})

            # Remove duplicate tickers (StatusInvest may return duplicates)
            df = df.drop_duplicates(subset=['ticker'], keep='first')

            valid_columns = ['ticker', 'market', 'price', 'dy', 'pvp', 'liquidezmediadiaria']

            # Query ALL existing tickers (unique constraint is on ticker alone, not ticker+market)
            existing_tickers = set(
                x[0] for x in db.query(FIIDB.ticker).all()
            )

            new_objects = []
            count = 0
            seen_tickers = set()

            for _, row in df.iterrows():
                ticker = str(row['ticker']).strip().upper()
                if ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)

                fii_data = {k: v for k, v in row.to_dict().items() if k in valid_columns}
                fii_data['ticker'] = ticker
                if 'market' not in fii_data: fii_data['market'] = market

                if ticker in existing_tickers:
                    # Update
                    fii_data['updated_at'] = datetime.now()
                    db.query(FIIDB).filter(FIIDB.ticker == ticker).update(fii_data)
                else:
                    # Insert
                    new_objects.append(FIIDB(**fii_data))
                    existing_tickers.add(ticker)  # Prevent duplicate inserts
                count += 1

                # Commit in chunks
                if count % 200 == 0:
                    db.commit()

            if new_objects:
                db.bulk_save_objects(new_objects)

            db.commit()
            logger.info(f"Successfully saved {count} FIIs ({len(new_objects)} new)")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Error in save_fiis: {str(e)}", exc_info=True)
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
    
    def cleanup_logs(self, days: int = 7):
        """Alias for cleanup_old_data - Remove old update logs"""
        self.cleanup_old_data(days=days)
    
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
    
    # ==================== SYSTEM SETTINGS ====================
    
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a system setting by key"""
        db = self.SessionLocal()
        try:
            setting = db.query(SystemSettingsDB).filter(
                SystemSettingsDB.key == key
            ).first()
            return setting.value if setting else default
        finally:
            db.close()
    
    def set_setting(self, key: str, value: str, description: str = None):
        """Set a system setting (create or update)"""
        db = self.SessionLocal()
        try:
            existing = db.query(SystemSettingsDB).filter(
                SystemSettingsDB.key == key
            ).first()
            
            if existing:
                existing.value = value
                if description:
                    existing.description = description
                existing.updated_at = datetime.now()
            else:
                setting = SystemSettingsDB(
                    key=key,
                    value=value,
                    description=description or key,
                    updated_at=datetime.now()
                )
                db.add(setting)
            
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_all_settings(self) -> List[Dict]:
        """Get all system settings"""
        db = self.SessionLocal()
        try:
            settings = db.query(SystemSettingsDB).all()
            return [s.to_dict() for s in settings]
        finally:
            db.close()
    
    def init_default_settings(self):
        """Initialize default system settings if they don't exist"""
        defaults = {
            'market_update_interval_minutes': ('60', 'Intervalo de coleta de dados de mercado (minutos)'),
            'flipping_update_interval_days': ('1', 'Intervalo de coleta de dados imobiliarios (dias)'),
            'auto_update_enabled': ('true', 'Habilitar coleta automatica de dados'),
        }
        
        for key, (value, desc) in defaults.items():
            if self.get_setting(key) is None:
                self.set_setting(key, value, desc)
    
    # ==================== FLIPPING CITIES ====================
    
    def get_flipping_cities(self) -> List[Dict]:
        """Get all configured House Flipping cities"""
        db = self.SessionLocal()
        try:
            cities = db.query(FlippingCityDB).filter(
                FlippingCityDB.active == 1
            ).order_by(FlippingCityDB.city).all()
            return [c.to_dict() for c in cities]
        finally:
            db.close()
    
    def add_flipping_city(self, city: str, state: str = None) -> Dict:
        """Add a city for House Flipping data collection"""
        db = self.SessionLocal()
        try:
            existing = db.query(FlippingCityDB).filter(
                FlippingCityDB.city == city
            ).first()
            
            if existing:
                if not existing.active:
                    existing.active = 1
                    db.commit()
                return existing.to_dict()
            
            new_city = FlippingCityDB(
                city=city,
                state=state,
                active=1,
                added_at=datetime.now()
            )
            db.add(new_city)
            db.commit()
            db.refresh(new_city)
            return new_city.to_dict()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def remove_flipping_city(self, city_id: int) -> bool:
        """Remove a city from House Flipping"""
        db = self.SessionLocal()
        try:
            city = db.query(FlippingCityDB).filter(
                FlippingCityDB.id == city_id
            ).first()
            
            if city:
                db.delete(city)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    # ==================== INVESTOR PERSONAS ====================
    
    def get_investors(self) -> List[Dict]:
        """Get all active investor personas"""
        db = self.SessionLocal()
        try:
            personas = db.query(InvestorPersonaDB).filter(
                InvestorPersonaDB.active == 1
            ).order_by(InvestorPersonaDB.name).all()
            return [p.to_dict() for p in personas]
        finally:
            db.close()
    
    def get_investor_by_name(self, name: str) -> Optional[Dict]:
        """Get a single investor persona by name"""
        db = self.SessionLocal()
        try:
            persona = db.query(InvestorPersonaDB).filter(
                InvestorPersonaDB.name == name,
                InvestorPersonaDB.active == 1
            ).first()
            return persona.to_dict() if persona else None
        finally:
            db.close()

    def get_fii_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Get a single FII by ticker"""
        db = self.SessionLocal()
        try:
            fii = db.query(FIIDB).filter(FIIDB.ticker == ticker).first()
            return fii.to_dict() if fii else None
        finally:
            db.close()

    def get_etf_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Get a single ETF by ticker"""
        db = self.SessionLocal()
        try:
            etf = db.query(ETFDB).filter(ETFDB.ticker == ticker).first()
            return etf.to_dict() if etf else None
        finally:
            db.close()

    def add_investor(self, name: str, description: str = None, style_prompt: str = None, voice_id: str = 'pt-BR-AntonioNeural') -> Dict:
        """Add an investor persona"""
        db = self.SessionLocal()
        try:
            existing = db.query(InvestorPersonaDB).filter(
                InvestorPersonaDB.name == name
            ).first()

            if existing:
                if not existing.active:
                    existing.active = 1
                    db.commit()
                return existing.to_dict()

            new_investor = InvestorPersonaDB(
                name=name,
                description=description,
                style_prompt=style_prompt,
                voice_id=voice_id,
                active=1,
                added_at=datetime.now()
            )
            db.add(new_investor)
            db.commit()
            db.refresh(new_investor)
            return new_investor.to_dict()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def remove_investor(self, investor_id: int) -> bool:
        """Remove an investor persona"""
        db = self.SessionLocal()
        try:
            investor = db.query(InvestorPersonaDB).filter(
                InvestorPersonaDB.id == investor_id
            ).first()
            
            if investor:
                db.delete(investor)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def init_default_investors(self):
        """Initialize default investor personas"""
        defaults = [
            {
                'name': 'Warren Buffett',
                'description': 'O Oraculo de Omaha - Value Investing de longo prazo',
                'style_prompt': 'Atue como Warren Buffett, o mais famoso investidor de valor do mundo. Use sua metodologia: busque empresas com vantagens competitivas duraveis (moats), gestao excelente, e precos abaixo do valor intrinseco. Fale com sabedoria e use suas frases celebres. Priorize o longo prazo e a margem de seguranca. Mencione conceitos como "circulo de competencia", "moat economico" e "compre medo, venda ganancia".',
                'voice_id': 'en-US-GuyNeural'
            },
            {
                'name': 'Luiz Barsi Filho',
                'description': 'O maior investidor individual da B3 - Foco em dividendos',
                'style_prompt': 'Atue como Luiz Barsi Filho, o maior investidor individual da bolsa brasileira. Use sua metodologia: foco absoluto em empresas pagadoras de dividendos consistentes, setores perenes (energia, bancos, saneamento). Fale de forma direta e pratica, como um investidor brasileiro experiente. Use conceitos como "carteira previdenciaria", "projeto de vida", "renda passiva" e "acoes de primeira linha". Alerte sobre especulacao e day-trade.',
                'voice_id': 'pt-BR-AntonioNeural'
            }
        ]
        
        for inv in defaults:
            db = self.SessionLocal()
            try:
                existing = db.query(InvestorPersonaDB).filter(
                    InvestorPersonaDB.name == inv['name']
                ).first()
                if not existing:
                    db.add(InvestorPersonaDB(**inv, active=1, added_at=datetime.now()))
                    db.commit()
            except:
                db.rollback()
            finally:
                db.close()


# Global instance
db_manager = DatabaseManager()