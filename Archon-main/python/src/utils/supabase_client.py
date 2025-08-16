import os
from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Initializes and returns the Supabase client."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase URL and service key must be set in environment variables.")
    return create_client(supabase_url, supabase_key)
