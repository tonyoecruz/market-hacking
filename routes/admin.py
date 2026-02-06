"""
Admin Routes - Monitoring and status endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from database.db_manager import db_manager
from scheduler import get_scheduler_status

router = APIRouter()


@router.get("/status")
async def get_system_status():
    """Get system status including database stats and scheduler info"""
    try:
        # Get database stats
        db_stats = db_manager.get_stats()
        
        # Get scheduler status
        scheduler_status = get_scheduler_status()
        
        # Get last updates
        last_updates = {
            'stocks_br': db_manager.get_last_update('stocks', 'BR'),
            'stocks_us': db_manager.get_last_update('stocks', 'US'),
            'etfs': db_manager.get_last_update('etfs', 'ALL'),
            'fiis': db_manager.get_last_update('fiis', 'BR')
        }
        
        return JSONResponse({
            'status': 'healthy',
            'database': db_stats,
            'scheduler': scheduler_status,
            'last_updates': last_updates
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_update_logs(limit: int = 20):
    """Get recent update logs"""
    try:
        logs = db_manager.get_update_logs(limit=limit)
        return JSONResponse({
            'status': 'success',
            'logs': logs
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
