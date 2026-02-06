"""
Async Database Queries for Supabase
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from .connection import get_supabase_client
from .models import User, UserCreate, Wallet, WalletCreate, Asset, AssetCreate, AssetUpdate
import bcrypt


class UserQueries:
    """User-related database operations"""
    
    @staticmethod
    def create_user(user_data: UserCreate) -> tuple[bool, str]:
        """
        Create a new user
        
        Args:
            user_data: UserCreate model with username, email, password
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            supabase = get_supabase_client()
            
            # Check if username already exists
            existing_username = supabase.table('users').select('id').eq('username', user_data.username).execute()
            if existing_username.data:
                return False, "Nome de usuário já está em uso"
            
            # Check if email already exists
            existing_email = supabase.table('users').select('id').eq('email', user_data.email).execute()
            if existing_email.data:
                return False, "Email já está cadastrado"
            
            # Hash password
            hashed_password = bcrypt.hashpw(
                user_data.password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Insert user
            result = supabase.table('users').insert({
                'username': user_data.username,
                'email': user_data.email,
                'password_hash': hashed_password,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            return True, "Usuário criado com sucesso"
        except Exception as e:
            error_msg = str(e)
            
            # Parse Supabase errors
            if 'duplicate key' in error_msg.lower():
                if 'users_email_key' in error_msg:
                    return False, "Email já está cadastrado"
                elif 'users_username_key' in error_msg:
                    return False, "Nome de usuário já está em uso"
                else:
                    return False, "Usuário ou email já existe"
            
            return False, f"Erro ao criar usuário: {error_msg}"
    
    @staticmethod
    def verify_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify user credentials (accepts username OR email)
        
        Args:
            username_or_email: Username or email
            password: Plain text password
            
        Returns:
            User dict if valid, None otherwise
        """
        try:
            supabase = get_supabase_client()
            
            # Try to find user by username OR email
            result = supabase.table('users').select('*').or_(
                f'username.eq.{username_or_email},email.eq.{username_or_email}'
            ).execute()
            
            if not result.data:
                return None
            
            user = result.data[0]
            
            # Check if user has password_hash (local auth)
            if not user.get('password_hash'):
                return None
            
            # Verify password
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return user
            
            return None
        except Exception as e:
            print(f"Error verifying user: {e}")
            return None
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            supabase = get_supabase_client()
            result = supabase.table('users').select('*').eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    @staticmethod
    def login_google_user(email: str, google_id: str) -> Optional[Dict[str, Any]]:
        """
        Login or create user via Google OAuth
        
        Args:
            email: Google email
            google_id: Google user ID
            
        Returns:
            User dict
        """
        try:
            supabase = get_supabase_client()
            
            # Check if user exists
            result = supabase.table('users').select('*').eq('google_id', google_id).execute()
            
            if result.data:
                return result.data[0]
            
            # Create new user
            username = email.split('@')[0]
            result = supabase.table('users').insert({
                'username': username,
                'email': email,
                'google_id': google_id,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error with Google login: {e}")
            return None


class WalletQueries:
    """Wallet-related database operations"""
    
    @staticmethod
    def get_wallets(user_id: int) -> List[Dict[str, Any]]:
        """Get all wallets for a user"""
        try:
            supabase = get_supabase_client()
            result = supabase.table('wallets').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting wallets: {e}")
            return []
    
    @staticmethod
    def create_wallet(user_id: int, name: str) -> tuple[bool, str]:
        """Create a new wallet"""
        try:
            supabase = get_supabase_client()
            
            result = supabase.table('wallets').insert({
                'user_id': user_id,
                'name': name,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            return True, "Carteira criada com sucesso"
        except Exception as e:
            return False, f"Erro ao criar carteira: {str(e)}"


class AssetQueries:
    """Asset-related database operations"""
    
    @staticmethod
    def get_portfolio(user_id: int, wallet_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get user's portfolio
        
        Args:
            user_id: User ID
            wallet_id: Optional wallet ID to filter
            
        Returns:
            List of assets with wallet info
        """
        try:
            supabase = get_supabase_client()
            
            query = supabase.table('assets').select(
                '*, wallets!inner(user_id, name)'
            ).eq('wallets.user_id', user_id)
            
            if wallet_id:
                query = query.eq('wallet_id', wallet_id)
            
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting portfolio: {e}")
            return []
    
    @staticmethod
    def add_to_wallet(user_id: int, ticker: str, quantity: float, price: float, wallet_id: int) -> tuple[bool, str]:
        """Add or update asset in wallet"""
        try:
            supabase = get_supabase_client()
            
            # Check if asset already exists
            result = supabase.table('assets').select('*').eq('wallet_id', wallet_id).eq('ticker', ticker).execute()
            
            if result.data:
                # Update existing asset (average price calculation)
                existing = result.data[0]
                old_qty = float(existing['quantity'])
                old_price = float(existing['avg_price'])
                
                new_qty = old_qty + quantity
                new_avg_price = ((old_qty * old_price) + (quantity * price)) / new_qty
                
                supabase.table('assets').update({
                    'quantity': new_qty,
                    'avg_price': new_avg_price,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', existing['id']).execute()
                
                return True, f"{ticker} atualizado na carteira"
            else:
                # Insert new asset
                supabase.table('assets').insert({
                    'wallet_id': wallet_id,
                    'ticker': ticker.upper(),
                    'quantity': quantity,
                    'avg_price': price,
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }).execute()
                
                return True, f"{ticker} adicionado à carteira"
        except Exception as e:
            return False, f"Erro ao adicionar ativo: {str(e)}"
    
    @staticmethod
    def update_asset(user_id: int, ticker: str, quantity: float, price: float) -> tuple[bool, str]:
        """Update asset in wallet"""
        try:
            supabase = get_supabase_client()
            
            # Find asset
            result = supabase.table('assets').select(
                '*, wallets!inner(user_id)'
            ).eq('wallets.user_id', user_id).eq('ticker', ticker).execute()
            
            if not result.data:
                return False, "Ativo não encontrado"
            
            asset = result.data[0]
            
            supabase.table('assets').update({
                'quantity': quantity,
                'avg_price': price,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', asset['id']).execute()
            
            return True, f"{ticker} atualizado"
        except Exception as e:
            return False, f"Erro ao atualizar ativo: {str(e)}"
    
    @staticmethod
    def remove_asset(user_id: int, ticker: str) -> tuple[bool, str]:
        """Remove asset from wallet"""
        try:
            supabase = get_supabase_client()
            
            # Find and delete asset
            result = supabase.table('assets').select(
                '*, wallets!inner(user_id)'
            ).eq('wallets.user_id', user_id).eq('ticker', ticker).execute()
            
            if not result.data:
                return False, "Ativo não encontrado"
            
            asset = result.data[0]
            
            supabase.table('assets').delete().eq('id', asset['id']).execute()
            
            return True, f"{ticker} removido da carteira"
        except Exception as e:
            return False, f"Erro ao remover ativo: {str(e)}"
