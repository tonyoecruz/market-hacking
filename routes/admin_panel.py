"""
Admin Panel Routes
Main admin dashboard with data monitoring, user management, and system stats
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from routes.admin_auth import verify_admin_session
from database.db_manager import db_manager
from database.connection import get_supabase_client
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


@router.get("/api/users/stats")
async def get_user_stats(session: dict = Depends(verify_admin_session)):
    """API endpoint for user statistics"""
    try:
        supabase = get_supabase_client()
        response = supabase.table('users').select('*').execute()
        users = response.data
        
        total_users = len(users)
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        new_this_week = sum(1 for u in users if u.get('created_at') and datetime.fromisoformat(u['created_at'].replace('Z', '+00:00')) > week_ago)
        active_users = sum(1 for u in users if u.get('last_login') and datetime.fromisoformat(u['last_login'].replace('Z', '+00:00')) > week_ago)
        total_logins = sum(u.get('login_count', 0) for u in users)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "total_users": total_users,
                "new_this_week": new_this_week,
                "active_users": active_users,
                "total_logins": total_logins
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/users")
async def get_users(session: dict = Depends(verify_admin_session)):
    """API endpoint to list all users"""
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query users table
        response = supabase.table('users').select('*').order('created_at', desc=True).execute()
        
        users = []
        for user in response.data:
            users.append({
                "id": user.get('id'),
                "username": user.get('username'),
                "email": user.get('email'),
                "created_at": user.get('created_at'),
                "last_login": user.get('last_login'),
                "is_active": user.get('is_active', True),
                "login_count": user.get('login_count', 0)
            })
        
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
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Check if user exists
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent deleting admin user (you can adjust this logic)
        user = user_response.data[0]
        if user.get('username') == 'admin':
            raise HTTPException(status_code=403, detail="Cannot delete admin user")
        
        # Delete user
        supabase.table('users').delete().eq('id', user_id).execute()
        
        return JSONResponse({
            "status": "success",
            "message": f"User {user.get('username')} deleted successfully"
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
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Check if user exists
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Hash the new password
        import bcrypt
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Update password
        supabase.table('users').update({
            'password_hash': password_hash
        }).eq('id', user_id).execute()
        
        return JSONResponse({
            "status": "success",
            "message": f"Password reset for user {user_response.data[0].get('username')}"
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


@router.post("/api/trigger-update")
async def trigger_manual_update(session: dict = Depends(verify_admin_session)):
    """Manually trigger data update"""
    try:
        from scheduler.data_updater import update_all_data
        import threading
        
        # Run update in background thread to avoid blocking
        thread = threading.Thread(target=update_all_data)
        thread.start()
        
        return JSONResponse({
            "status": "success",
            "message": "Data update triggered successfully. This may take a few minutes."
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
