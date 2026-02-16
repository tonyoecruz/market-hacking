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
from routes import auth, dashboard, acoes, etfs, elite_mix, fiis, arena, admin, admin_auth, admin_panel
from routes import admin_logs  # Real-time logs

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
app.include_router(admin_auth.router, prefix="/admin", tags=["Admin Auth"])
app.include_router(admin_panel.router, prefix="/admin", tags=["Admin Panel"])
app.include_router(admin_logs.router, prefix="/admin", tags=["Admin Logs"])

# House Flipping Module
from routes import flipping
app.include_router(flipping.router, prefix="/flipping", tags=["House Flipping"])



@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on app startup"""
    logger.info("="*80)
    logger.info("🚀 SCOPE3 APPLICATION STARTING...")
    logger.info("="*80)
    
    # Initialize database
    try:
        logger.info("📊 Initializing database...")
        init_database()
        logger.info("✅ Database initialized successfully")
        
        # Get and log database stats
        stats = db_manager.get_stats()
        logger.info(f"📈 Database Stats:")
        logger.info(f"   - Total Stocks: {stats['stocks_count']}")
        logger.info(f"   - BR Stocks: {stats['stocks_br_count']}")
        logger.info(f"   - US Stocks: {stats['stocks_us_count']}")
        logger.info(f"   - ETFs: {stats['etfs_count']}")
        logger.info(f"   - FIIs: {stats['fiis_count']}")
        logger.info(f"   - Total Updates: {stats['total_updates']}")
        logger.info(f"   - Last Update: {stats['last_update']}")
        
        # Check if database is empty
        if stats['stocks_count'] == 0:
            logger.warning("⚠️  Database is EMPTY - No market data found!")
            logger.info("📊 Scheduler will trigger initial data update...")
        else:
            logger.info("✅ Database contains market data")
        
        # Initialize default settings
        db_manager.init_default_settings()
        db_manager.init_default_investors()
        logger.info("✅ Default settings and investor personas initialized")
            
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
    
    # Start background scheduler
    try:
        logger.info("⏰ Starting background scheduler...")
        start_scheduler()
        logger.info("✅ Background scheduler started successfully")
        logger.info("📅 Scheduled jobs:")
        logger.info("   - Data update: Every hour")
        logger.info("   - Log cleanup: Daily at midnight")
        logger.info("   - Initial update: IMMEDIATE")
    except Exception as e:
        logger.error(f"❌ Scheduler startup error: {e}", exc_info=True)
    
    logger.info("="*80)
    logger.info("✅ SCOPE3 APPLICATION READY")
    logger.info("="*80)

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


# ==================== GLOBAL TTS ENDPOINT ====================
from fastapi.responses import FileResponse
import data_utils as _du

@app.post("/api/tts")
async def text_to_speech(request: Request):
    """Generate TTS audio from text"""
    try:
        body = await request.json()
        text = body.get("text", "")
        key = body.get("key", "general")
        investor_name = body.get("investor", "")

        if not text or len(text) < 5:
            return {"status": "error", "message": "Texto muito curto"}

        # Truncate very long text
        if len(text) > 5000:
            text = text[:5000] + "..."

        # Determine voice from investor persona
        voice_override = None
        if investor_name:
            inv = db_manager.get_investor_by_name(investor_name)
            if inv and inv.get('voice_id'):
                voice_override = inv['voice_id']

        filepath = _du.generate_audio(text, key_suffix=key, voice_override=voice_override)
        
        if filepath and not str(filepath).startswith("ERROR") and os.path.exists(filepath):
            return FileResponse(filepath, media_type="audio/mpeg")
        else:
            return {"status": "error", "message": "Falha ao gerar áudio"}
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ==================== INVESTOR PERSONA API ====================
@app.get("/api/investors")
async def get_investors():
    """Get all available investor personas"""
    try:
        investors = db_manager.get_investors()
        return {"status": "success", "investors": investors}
    except Exception as e:
        return {"status": "error", "message": str(e)}


import os

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
