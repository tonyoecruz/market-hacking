"""
SCOPE3 - FastAPI Main Application
Modern financial analysis platform with modular architecture
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
import logging

# Import routes
from routes import auth, dashboard, acoes, etfs, elite_mix, fiis, arena, admin

# Import database and scheduler
from database.db_manager import init_database, db_manager
from scheduler import start_scheduler, stop_scheduler, get_scheduler_status, update_all_data

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SCOPE3",
    description="Plataforma de Análise Financeira - Graham & Magic Formula",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "https://scope3.com.br",
        "https://scope3.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(acoes.router, prefix="/acoes", tags=["Ações"])
app.include_router(etfs.router, prefix="/etfs", tags=["ETFs"])
app.include_router(elite_mix.router, prefix="/elite-mix", tags=["Elite Mix"])
app.include_router(fiis.router, prefix="/fiis", tags=["FIIs"])
app.include_router(arena.router, prefix="/arena", tags=["Arena"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on app startup"""
    logger.info("🚀 Starting SCOPE3 application...")
    
    # Initialize database
    try:
        init_database()
        logger.info("✅ Database initialized")
        
        # Check if database is empty and run initial update
        stats = db_manager.get_stats()
        if stats['stocks_count'] == 0:
            logger.info("📊 Database is empty, running initial data update...")
            update_all_data()
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
    
    # Start background scheduler
    try:
        start_scheduler()
        logger.info("✅ Background scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop scheduler on app shutdown"""
    logger.info("⏹️  Shutting down SCOPE3 application...")
    stop_scheduler()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Root endpoint - redirects to login or dashboard
    """
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "SCOPE3"
    }


@app.get("/api/info")
async def api_info():
    """API information endpoint"""
    return {
        "name": "SCOPE3 API",
        "version": "2.0.0",
        "description": "Financial Analysis Platform",
        "endpoints": {
            "auth": "/auth",
            "dashboard": "/dashboard",
            "acoes": "/acoes",
            "etfs": "/etfs",
            "elite_mix": "/elite-mix",
            "fiis": "/fiis",
            "arena": "/arena"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
