"""
Pydantic Models for Data Validation - SCOPE3 (FastAPI Optimized)
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class User(UserBase):
    """User model with database fields"""
    id: int
    google_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class WalletBase(BaseModel):
    """Base wallet model"""
    name: str = Field(..., min_length=1, max_length=100)


class WalletCreate(WalletBase):
    """Wallet creation model"""
    user_id: int


class Wallet(WalletBase):
    """Wallet model with database fields"""
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AssetBase(BaseModel):
    """Base asset model"""
    ticker: str
    quantity: Decimal
    avg_price: Decimal
    asset_type: str  # stock_br, stock_us, fii, etf

    @field_validator('ticker')
    @classmethod
    def ticker_uppercase(cls, v):
        return v.upper().strip()


class AssetCreate(AssetBase):
    """Asset creation model"""
    wallet_id: int


class AssetUpdate(BaseModel):
    """Asset update model"""
    quantity: Optional[Decimal] = Field(None, gt=0)
    avg_price: Optional[Decimal] = Field(None, gt=0)


class Asset(AssetBase):
    """Asset model with database fields"""
    id: int
    wallet_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TransactionBase(BaseModel):
    """Base transaction model"""
    ticker: str
    quantity: Decimal
    price: Decimal
    # CORREÇÃO: Usando pattern em vez de regex para compatibilidade com Pydantic v2
    transaction_type: str = Field(..., pattern="^(buy|sell)$")


class TransactionCreate(TransactionBase):
    """Transaction creation model"""
    wallet_id: int


class Transaction(TransactionBase):
    """Transaction model with database fields"""
    id: int
    wallet_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """JWT token data"""
    user_id: int
    username: str
    exp: datetime


class StockAnalysis(BaseModel):
    """Stock analysis response model"""
    ticker: str
    analysis: str
    recommendation: str
    updated_at: datetime