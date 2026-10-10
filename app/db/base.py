from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# Đảm bảo dùng driver psycopg3 (psycopg) thay vì psycopg2
db_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+psycopg://", 1
).replace(
    "postgres://", "postgresql+psycopg://", 1
)

# Khởi tạo engine kết nối Supabase
engine = create_engine(db_url, pool_pre_ping=True)

# Tạo session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class all Models sau này
class Base(DeclarativeBase):
    pass

# Dependency Injection dùng cho FastAPI Routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


