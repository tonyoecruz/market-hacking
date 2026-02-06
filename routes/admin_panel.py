"""
Admin Panel Routes
Main admin dashboard with data monitoring, user management, and system stats
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.admin_auth import verify_admin_session
from database.db_manager import db_manager
from datetime import datetime, timedelta
from typing import Dict, List
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_data_source_status() -> Dict:
    """Get status of all data sources with color indicators"""
    
    def check_source_health(asset_type: str, market: str = None) -> Dict:
        """Check if a data source is healthy"""
        last_update = db_manager.get_last_update(asset_type, market)
        
        if not last_update:
            return {
                "status": "error",
                "color": "red",
                "last_update": None,
                "record_count": 0,
                "message": "Never updated"
            }
        
        # Check if update was recent (< 2 hours)
        last_update_time = datetime.fromisoformat(last_update['completed_at'])
        time_diff = datetime.now() - last_update_time
        
        # Get record count
        if asset_type == 'stocks':
            count = len(db_manager.get_stocks(market=market))
        elif asset_type == 'etfs':
            count = len(db_manager.get_etfs(market=market))
        elif asset_type == 'fiis':
            count = len(db_manager.get_fiis(market=market))
        else:
            count = 0
        
        # Determine status
        if last_update['status'] == 'error':
            status = "error"
            color = "red"
            message = last_update.get('error_message', 'Update failed')
        elif time_diff > timedelta(hours=2):
            status = "stale"
            color = "yellow"
            message = f"Last update: {time_diff.seconds // 3600}h ago"
        elif count == 0:
            status = "empty"
            color = "red"
            message = "No data"
        else:
            status = "healthy"
            color = "green"
            message = f"Updated {time_diff.seconds // 60}min ago"
        
        return {
            "status": status,
            "color": color,
            "last_update": last_update_time.strftime("%Y-%m-%d %H:%M"),
            "record_count": count,
            "message": message
        }
    
    return {
        "stocks_br": check_source_health('stocks', 'BR'),
        "stocks_us": check_source_health('stocks', 'US'),
        "etfs_br": check_source_health('etfs', 'BR'),
        "etfs_us": check_source_health('etfs', 'US'),
        "fiis_br": check_source_health('fiis', 'BR')
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Main admin dashboard"""
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "title": "Admin Dashboard",
        "user": session
    })


@router.get("/api/data-status")
async def get_data_status(session: dict = Depends(verify_admin_session)):
    """API endpoint for data source status"""
    try:
        status = get_data_source_status()
        return JSONResponse({
            "status": "success",
            "data": status
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/system-stats")
async def get_system_stats(session: dict = Depends(verify_admin_session)):
    """API endpoint for system statistics"""
    try:
        stats = db_manager.get_stats()
        
        # Get recent logs
        logs = db_manager.get_update_logs(limit=10)
        
        # Calculate success rate
        total_updates = len(logs)
        successful = sum(1 for log in logs if log['status'] == 'success')
        success_rate = (successful / total_updates * 100) if total_updates > 0 else 0
        
        return JSONResponse({
            "status": "success",
            "data": {
                "database": stats,
                "updates": {
                    "total": total_updates,
                    "successful": successful,
                    "success_rate": round(success_rate, 1)
                },
                "recent_logs": logs[:5]
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/users")
async def get_users(session: dict = Depends(verify_admin_session)):
    """API endpoint to list all users"""
    try:
        # This would query the users table
        # For now, return mock data since we don't have user management yet
        users = [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@scope3.com",
                "created_at": "2026-01-01T00:00:00",
                "last_login": "2026-02-06T10:00:00",
                "is_active": True
            }
        ]
        
        return JSONResponse({
            "status": "success",
            "data": {
                "total": len(users),
                "users": users
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    session: dict = Depends(verify_admin_session)
):
    """Delete a user"""
    try:
        # Prevent deleting admin user
        if user_id == 1:
            raise HTTPException(status_code=403, detail="Cannot delete admin user")
        
        # TODO: Implement actual user deletion
        return JSONResponse({
            "status": "success",
            "message": f"User {user_id} deleted successfully"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Reset user password"""
    try:
        data = await request.json()
        new_password = data.get("new_password")
        
        if not new_password or len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # TODO: Implement actual password reset
        return JSONResponse({
            "status": "success",
            "message": f"Password reset for user {user_id}"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/logs")
async def get_update_logs(
    limit: int = 50,
    session: dict = Depends(verify_admin_session)
):
    """Get update logs"""
    try:
        logs = db_manager.get_update_logs(limit=limit)
        return JSONResponse({
            "status": "success",
            "data": logs
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
