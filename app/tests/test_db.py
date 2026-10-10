"""Kiểm tra toàn diện kết nối Database (SQLAlchemy) và API (Supabase Client).

Cách dùng:
    python -m app.tests.test_db
"""
from app.core.supabase import supabase_admin
from app.db.base import engine


def test_connections():
    print("Tiến hành kiểm tra hệ thống...")

    # 1. Kiểm tra kết nối TCP/IPv4 tới PostgreSQL (SQLAlchemy)
    try:
        with engine.connect():
            print("✅ [OK] Kết nối SQLAlchemy (PostgreSQL IPv4) thành công!")
    except Exception as e:
        print(f"❌ [FAIL] Lỗi kết nối SQLAlchemy: {e}")

    # 2. Kiểm tra kết nối REST API (Supabase Client)
    try:
        # Gọi Auth API để xác thực Service Role
        supabase_admin.auth.admin.list_users()
        print("✅ [OK] Kết nối Supabase API (Service Role) thành công!")
    except Exception as e:
        print(f"❌ [FAIL] Lỗi kết nối Supabase API: {e}")

if __name__ == "__main__":
    test_connections()
