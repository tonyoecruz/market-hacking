"""
Supabase Database Connection Module
Provides async client for PostgreSQL operations
"""
import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Get or create Supabase client instance (singleton pattern)
    
    Returns:
        Client: Supabase client instance, or None if credentials not set
    """
    global _supabase_client
    
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            # Return None in local development mode
            return None
        
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    return _supabase_client


# Convenience function for quick access
supabase = get_supabase_client
