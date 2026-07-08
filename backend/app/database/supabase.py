from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_admin_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_user_client(access_token: str) -> Client:
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
