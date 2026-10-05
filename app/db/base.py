from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings
from app.core.config import settings
# Khởi tạo engine kết nối Supabase
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

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


