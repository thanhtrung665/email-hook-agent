from app.db.base import engine

try:
    with engine.connect() as connection:
        print("Kết nối Supabase thành công")
except Exception as e:
    print(f"Lỗi kết nối: {e}")