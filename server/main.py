from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import db
import asyncio

app = FastAPI(title="Scope3 API", version="15.0")

# CORS (Allow Next.js frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class PortfolioItem(BaseModel):
    ticker: str
    quantity: int
    price: float

class SessionToken(BaseModel):
    token: str

# --- AUTH ENDPOINTS ---

@app.post("/auth/login")
def login(user_data: UserLogin):
    user = db.verify_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    
    token, err = db.create_session(user['id'])
    if not token:
        raise HTTPException(status_code=500, detail=f"Session Error: {err}")
    
    return {"token": token, "user": user}

@app.post("/auth/register")
def register(user_data: UserRegister):
    success, msg = db.create_user(user_data.username, user_data.password, user_data.email)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "User created successfully"}

@app.get("/auth/me")
def get_current_user(token: str):
    user = db.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or Expired Token")
    return user

@app.post("/auth/logout")
def logout(payload: SessionToken):
    db.delete_session(payload.token)
    return {"message": "Logged out"}

# --- PORTFOLIO ENDPOINTS ---

def get_user_from_header(token: str):
    user = db.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Token")
    return user

@app.get("/portfolio")
def get_portfolio(token: str):
    user = get_user_from_header(token)
    df = db.get_portfolio(user['id'])
    if df.empty:
        return []
    return df.to_dict(orient="records")

@app.post("/portfolio/add")
def add_asset(item: PortfolioItem, token: str):
    user = get_user_from_header(token)
    success, msg = db.add_to_wallet(user['id'], item.ticker, item.quantity, item.price)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "Asset added"}

@app.delete("/portfolio/{ticker}")
def remove_asset(ticker: str, token: str):
    user = get_user_from_header(token)
    success, msg = db.remove_from_wallet(user['id'], ticker)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "Asset removed"}

@app.get("/")
def health_check():
    return {"status": "online", "system": "Scope3 V15 API"}
