"""
Admin Routes - Monitoring and status endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from database.db_manager import DatabaseManager # Alterado para importar a Classe
from scheduler.scheduler import get_scheduler_status
from routes.auth import get_optional_user

router = APIRouter()
db = DatabaseManager() # Instância local para evitar conflitos

@router.get("/status")
async def get_system_status(user: dict = Depends(get_optional_user)):
    """Get system status including database stats and scheduler info"""
    try:
        # Obtém estatísticas do banco de dados
        db_stats = db.get_stats()
        
        # Obtém status do agendador
        scheduler_status = get_scheduler_status()
        
        # Obtém últimas atualizações por categoria
        last_updates = {
            'stocks_br': db.get_last_update('stocks', 'BR'),
            'stocks_us': db.get_last_update('stocks', 'US'),
            'etfs': db.get_last_update('etfs', 'ALL'),
            'fiis': db.get_last_update('fiis', 'BR')
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
async def get_update_logs(limit: int = 20, user: dict = Depends(get_optional_user)):
    """Get recent update logs"""
    try:
        logs = db.get_update_logs(limit=limit)
        return JSONResponse({
            'status': 'success',
            'logs': logs
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))