"""
Admin Routes - Monitoring and status endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from database.db_manager import DatabaseManager
from scheduler.scheduler import get_scheduler_status
from routes.auth import get_optional_user

router = APIRouter()
db = DatabaseManager()

@router.get("/status")
async def get_system_status(user: dict = Depends(get_optional_user)):
    """Status do sistema e estatísticas do banco"""
    try:
        db_stats = db.get_stats()
        scheduler_status = get_scheduler_status()
        
        return JSONResponse({
            'status': 'healthy',
            'database': db_stats,
            'scheduler': scheduler_status
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_update_logs(limit: int = 20, user: dict = Depends(get_optional_user)):
    """Logs das últimas atualizações automáticas"""
    try:
        logs = db.get_update_logs(limit=limit)
        return JSONResponse({'status': 'success', 'logs': logs})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))