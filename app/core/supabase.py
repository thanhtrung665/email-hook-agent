from supabase import Client, create_client

from app.core.config import settings

supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY
)

# Quyền ẩn danh / cơ bản
supabase_anon: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY
)
