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

# Import routes
from routes import auth, dashboard, acoes, etfs, elite_mix, fiis, arena

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
