"""
Authentication Routes - Login, Register, Logout, Google OAuth
"""
from fastapi import APIRouter, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import timedelta

from database.queries import UserQueries
from database.models import UserCreate, UserLogin
from utils.security import create_access_token, decode_access_token, sanitize_input

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Render login page"""
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": error
        }
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Process login form
    
    Returns JWT token in cookie and redirects to dashboard
    """
    # Sanitize inputs
    username = sanitize_input(username, max_length=50)
    
    # Verify credentials
    user = UserQueries.verify_user(username, password)
    
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Credenciais inválidas. Verifique seu usuário e senha.",
                "username": username
            }
        )
    
    # Create access token
    access_token = create_access_token(
        data={"user_id": user["id"], "username": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Set cookie and redirect
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    """Render registration page"""
    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "error": error
        }
    )


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...)
):
    """
    Process registration form
    """
    # Sanitize inputs
    username = sanitize_input(username, max_length=50)
    email = sanitize_input(email, max_length=100)
    
    # Validate password match
    if password != password_confirm:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "As senhas não coincidem",
                "username": username,
                "email": email
            }
        )
    
    # Create user
    user_data = UserCreate(
        username=username,
        email=email,
        password=password
    )
    
    success, message = UserQueries.create_user(user_data)
    
    if not success:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": message,
                "username": username,
                "email": email
            }
        )
    
    # Redirect to login
    return RedirectResponse(url="/auth/login?registered=true", status_code=303)


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing cookie
    """
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """
    Get current authenticated user from token
    """
    # Get token from cookie
    token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    # Decode token
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get user from database
    user = UserQueries.get_user_by_id(payload.get("user_id"))
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"]
    }


# Dependency for protected routes
async def get_current_user_from_cookie(request: Request):
    """
    Dependency to get current user from cookie
    Use in protected routes: user = Depends(get_current_user_from_cookie)
    """
    token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if token.startswith("Bearer "):
        token = token[7:]
    
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = UserQueries.get_user_by_id(payload.get("user_id"))
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


# Optional user dependency (returns None if not authenticated)
async def get_optional_user(request: Request):
    """
    Optional dependency to get current user from cookie
    Returns None if not authenticated instead of raising exception
    Use in pages that work with or without login
    """
    try:
        token = request.cookies.get("access_token")
        
        if not token:
            return None
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        payload = decode_access_token(token)
        
        if not payload:
            return None
        
        user = UserQueries.get_user_by_id(payload.get("user_id"))
        
        return user if user else None
    except:
        return None


# ============================================
# Forgot Password Routes
# ============================================

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Render forgot password page"""
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request}
    )


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...)
):
    """
    Process forgot password form
    
    Note: For now, this is a placeholder that shows a success message.
    In production, this would send a password reset email.
    """
    email = sanitize_input(email, max_length=100)
    
    # Always show success message to prevent email enumeration
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {
            "request": request,
            "success": "Se o email estiver cadastrado, você receberá um link para redefinir sua senha."
        }
    )


# ============================================
# Google OAuth Routes
# ============================================

@router.get("/google/login")
async def google_login(request: Request):
    """
    Initiate Google OAuth flow
    Redirects user to Google's authorization page
    """
    import os
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    
    if not client_id:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Login com Google não está configurado. Configure GOOGLE_CLIENT_ID nas variáveis de ambiente."
            }
        )
    
    # Determine redirect URI based on request
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/google/callback"
    
    # Google OAuth authorization URL
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        "access_type=offline&"
        "prompt=consent"
    )
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str = None, error: str = None):
    """
    Handle Google OAuth callback
    Exchange authorization code for user info and create/login user
    """
    import os
    import httpx
    
    if error or not code:
        return RedirectResponse(url="/auth/login?error=google_auth_failed")
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return RedirectResponse(url="/auth/login?error=google_not_configured")
    
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/google/callback"
    
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                }
            )
            
            if token_response.status_code != 200:
                return RedirectResponse(url="/auth/login?error=google_token_failed")
            
            tokens = token_response.json()
            
            # Get user info
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            
            if user_info_response.status_code != 200:
                return RedirectResponse(url="/auth/login?error=google_userinfo_failed")
            
            user_info = user_info_response.json()
        
        # Login or create user
        email = user_info.get("email")
        google_id = user_info.get("id")
        
        if not email:
            return RedirectResponse(url="/auth/login?error=google_no_email")
        
        user = UserQueries.login_google_user(email=email, google_id=google_id)
        
        if not user:
            return RedirectResponse(url="/auth/login?error=google_login_failed")
        
        # Create JWT token and set cookie
        access_token = create_access_token(
            data={"user_id": user["id"], "username": user.get("username", email)},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Google OAuth error: {e}", exc_info=True)
        return RedirectResponse(url="/auth/login?error=google_auth_error")

