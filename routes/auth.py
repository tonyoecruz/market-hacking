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
async def login_page(request: Request):
    """Render login page"""
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request}
    )


@router.post("/login")
async def login(
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
        raise HTTPException(
            status_code=401,
            detail="Credenciais inválidas"
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
async def register_page(request: Request):
    """Render registration page"""
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request}
    )


@router.post("/register")
async def register(
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
        raise HTTPException(
            status_code=400,
            detail="As senhas não coincidem"
        )
    
    # Create user
    user_data = UserCreate(
        username=username,
        email=email,
        password=password
    )
    
    success, message = UserQueries.create_user(user_data)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
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
