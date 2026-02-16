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
import logging

router = APIRouter()
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)


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
        logger.info("📊 Fetching system stats...")
        stats = db_manager.get_stats()
        logger.info(f"✅ Stats retrieved: {stats}")
        
        # Get recent logs
        logs = db_manager.get_update_logs(limit=10)
        logger.info(f"📋 Retrieved {len(logs)} update logs")
        
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
        logger.error(f"❌ Error fetching system stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/users/stats")
async def get_user_stats(session: dict = Depends(verify_admin_session)):
    """API endpoint for user statistics"""
    try:
        # Get users from Supabase
        supabase = get_supabase_client()
        if supabase:
            response = supabase.table('users').select('*').execute()
            users = response.data if response.data else []
        else:
            users = []  # Fallback for local development without Supabase
        
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
        # Get users from Supabase
        supabase = get_supabase_client()
        if supabase:
            response = supabase.table('users').select('*').order('created_at', desc=True).execute()
            response_data = response.data if response.data else []
        else:
            response_data = []  # Fallback for local development without Supabase
        
        users = []
        for user in response_data:
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
    """Delete a user and all related data"""
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Get user info first
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_response.data[0]
        
        # Prevent deleting admin user
        if user.get('username') == 'admin':
            raise HTTPException(status_code=403, detail="Cannot delete admin user")
        
        # Delete related data first (cascade delete)
        # Delete portfolio entries
        try:
            supabase.table('portfolio').delete().eq('user_id', user_id).execute()
        except Exception as e:
            logger.warning(f"No portfolio data to delete for user {user_id}: {e}")
        
        # Delete user sessions if exists
        try:
            supabase.table('sessions').delete().eq('user_id', user_id).execute()
        except Exception as e:
            logger.warning(f"No session data to delete for user {user_id}: {e}")
        
        # Delete user transactions if exists
        try:
            supabase.table('transactions').delete().eq('user_id', user_id).execute()
        except Exception as e:
            logger.warning(f"No transaction data to delete for user {user_id}: {e}")
        
        # Now delete the user
        supabase.table('users').delete().eq('id', user_id).execute()
        
        return JSONResponse({
            "status": "success",
            "message": f"User {user.get('username')} and all related data deleted successfully"
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


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
async def trigger_manual_update(
    sync: bool = False,
    session: dict = Depends(verify_admin_session)
):
    """Manually trigger data update"""
    try:
        from scheduler.data_updater import update_all_data
        import threading
        
        if sync:
            logger.info("⚡ TRIGGERING SYNCHRONOUS UPDATE (DEBUG MODE)")
            try:
                # Run directly and capture output
                results = update_all_data()
                return JSONResponse({
                    "status": "success",
                    "message": f"Update completed. Results: {results}",
                    "details": results
                })
            except Exception as e:
                logger.error(f"❌ COMPLETED WITH ERROR: {str(e)}")
                return JSONResponse({
                    "status": "error",
                    "detail": f"Update failed: {str(e)}"
                }, status_code=500)
        
        # Run update in background thread to avoid blocking
        thread = threading.Thread(target=update_all_data)
        thread.start()
        
        return JSONResponse({
            "status": "success",
            "message": "Data update triggered successfully. This may take a few minutes."
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users/create-admin")
async def create_admin_user(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Create a new admin user"""
    try:
        data = await request.json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        
        if not username or not email or not password:
            raise HTTPException(status_code=400, detail="Username, email, and password are required")
        
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Check if username or email already exists
        existing = supabase.table('users').select('*').or_(f"username.eq.{username},email.eq.{email}").execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Hash password
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        supabase.table('users').insert({
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'is_active': True,
            'login_count': 0
        }).execute()
        
        return JSONResponse({
            "status": "success",
            "message": f"Admin user '{username}' created successfully"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/change-password")
async def change_admin_password(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Change logged admin's password"""
    try:
        data = await request.json()
        current_password = data.get("current_password")
        new_password = data.get("new_password")
        
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="Current and new password are required")
        
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        
        # Verify current password (admin uses simple comparison for now)
        if current_password != "caTia.1234":
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # For now, we can't change the hardcoded admin password
        # This would require storing admin in Supabase users table
        return JSONResponse({
            "status": "success",
            "message": "Password change feature coming soon. Admin password is currently hardcoded."
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SETTINGS API ====================

@router.get("/api/settings")
async def get_settings(session: dict = Depends(verify_admin_session)):
    """Get all system settings"""
    try:
        # Initialize defaults if needed
        db_manager.init_default_settings()
        
        settings = db_manager.get_all_settings()
        return JSONResponse({
            "status": "success",
            "settings": settings
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/settings")
async def update_settings(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Update system settings and reschedule jobs"""
    try:
        data = await request.json()
        settings = data.get("settings", {})
        
        for key, value in settings.items():
            db_manager.set_setting(key, str(value))
        
        # Reschedule scheduler jobs if interval changed
        from scheduler import reschedule_jobs
        rescheduled = reschedule_jobs()
        
        return JSONResponse({
            "status": "success",
            "message": "Configuracoes salvas com sucesso",
            "rescheduled": rescheduled
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FLIPPING CITIES API ====================

@router.get("/api/flipping/cities")
async def get_flipping_cities(session: dict = Depends(verify_admin_session)):
    """Get all configured House Flipping cities"""
    try:
        cities = db_manager.get_flipping_cities()
        return JSONResponse({
            "status": "success",
            "cities": cities
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/flipping/cities")
async def add_flipping_city(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Add a city for House Flipping"""
    try:
        data = await request.json()
        city = data.get("city", "").strip()
        state = data.get("state", "").strip() or None
        
        if not city:
            raise HTTPException(status_code=400, detail="City name is required")
        
        result = db_manager.add_flipping_city(city, state)
        return JSONResponse({
            "status": "success",
            "message": f"Cidade '{city}' adicionada",
            "city": result
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/flipping/cities/{city_id}")
async def remove_flipping_city(
    city_id: int,
    session: dict = Depends(verify_admin_session)
):
    """Remove a city from House Flipping"""
    try:
        success = db_manager.remove_flipping_city(city_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="City not found")
        
        return JSONResponse({
            "status": "success",
            "message": "Cidade removida"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INVESTOR PERSONAS API ====================

@router.get("/api/investors")
async def get_investors_admin(session: dict = Depends(verify_admin_session)):
    """Get all investor personas"""
    try:
        investors = db_manager.get_investors()
        return JSONResponse({"status": "success", "investors": investors})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/investors")
async def add_investor(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Add an investor persona"""
    try:
        data = await request.json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        style_prompt = data.get('style_prompt', '').strip()
        voice_id = data.get('voice_id', 'pt-BR-AntonioNeural').strip()

        if not name:
            raise HTTPException(status_code=400, detail="Nome obrigatorio")

        investor = db_manager.add_investor(name, description, style_prompt, voice_id=voice_id)
        return JSONResponse({"status": "success", "investor": investor})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/investors/{investor_id}")
async def remove_investor(
    investor_id: int,
    session: dict = Depends(verify_admin_session)
):
    """Remove an investor persona"""
    try:
        success = db_manager.remove_investor(investor_id)
        if not success:
            raise HTTPException(status_code=404, detail="Investidor nao encontrado")
        return JSONResponse({"status": "success", "message": "Investidor removido"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/investors/generate-style")
async def generate_investor_style(
    request: Request,
    session: dict = Depends(verify_admin_session)
):
    """Use AI to auto-generate a style_prompt for an investor"""
    try:
        data = await request.json()
        name = data.get('name', '').strip()
        if not name:
            raise HTTPException(status_code=400, detail="Nome obrigatorio")

        import data_utils as _du
        prompt = f"""Gere uma instrucao de sistema detalhada (style_prompt) para uma IA que deve atuar como o investidor "{name}".

Inclua:
- Metodologia de investimento dele (value investing, growth, dividendos, etc.)
- Metricas e indicadores que ele prioriza
- Setores e tipos de empresa preferidos
- Nivel de tolerancia a risco
- Frases celebres e estilo de comunicacao
- Conceitos-chave que ele usa

Escreva em portugues brasileiro. A instrucao deve comecar com "Atue como {name}..." e ter no maximo 300 palavras.
Seja especifico e baseado em fatos reais sobre este investidor."""

        style = _du.get_ai_generic_analysis(prompt)
        return JSONResponse({"status": "success", "style_prompt": style})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

