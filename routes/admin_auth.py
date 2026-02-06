"""
Admin Authentication Module
Handles admin login, session management, and access control
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Admin credentials (hardcoded for now)
ADMIN_CREDENTIALS = {
    "admin": {
        "password_hash": pwd_context.hash("caTia.1234"),
        "role": "super_admin",
        "created_at": datetime.now()
    }
}

# Session storage (in-memory for now, use Redis in production)
admin_sessions = {}

# Session timeout (30 minutes)
SESSION_TIMEOUT = timedelta(minutes=30)


def create_session(username: str) -> str:
    """Create a new admin session"""
    session_id = secrets.token_urlsafe(32)
    admin_sessions[session_id] = {
        "username": username,
        "role": ADMIN_CREDENTIALS[username]["role"],
        "created_at": datetime.now(),
        "last_activity": datetime.now()
    }
    return session_id


def get_session(session_id: str) -> dict:
    """Get session data if valid"""
    if not session_id or session_id not in admin_sessions:
        return None
    
    session = admin_sessions[session_id]
    
    # Check if session expired
    if datetime.now() - session["last_activity"] > SESSION_TIMEOUT:
        del admin_sessions[session_id]
        return None
    
    # Update last activity
    session["last_activity"] = datetime.now()
    return session


def verify_admin_session(request: Request):
    """Dependency to verify admin session"""
    session_id = request.cookies.get("admin_session")
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return session


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    # Check if already logged in
    session_id = request.cookies.get("admin_session")
    if get_session(session_id):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "title": "Admin Login"
    })


@router.post("/login")
async def admin_login(request: Request):
    """Admin login endpoint"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        # Verify credentials
        if username not in ADMIN_CREDENTIALS:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not pwd_context.verify(password, ADMIN_CREDENTIALS[username]["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create session
        session_id = create_session(username)
        
        # Return response with session cookie
        response = JSONResponse({
            "status": "success",
            "message": "Login successful",
            "redirect": "/admin/dashboard"
        })
        
        response.set_cookie(
            key="admin_session",
            value=session_id,
            httponly=True,
            max_age=1800,  # 30 minutes
            samesite="lax"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def admin_logout(request: Request):
    """Admin logout endpoint"""
    session_id = request.cookies.get("admin_session")
    
    if session_id and session_id in admin_sessions:
        del admin_sessions[session_id]
    
    response = JSONResponse({
        "status": "success",
        "message": "Logged out successfully"
    })
    
    response.delete_cookie("admin_session")
    return response


@router.get("/verify")
async def verify_session(session: dict = Depends(verify_admin_session)):
    """Verify if session is valid"""
    return JSONResponse({
        "status": "valid",
        "username": session["username"],
        "role": session["role"]
    })
