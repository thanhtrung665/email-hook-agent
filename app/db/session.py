from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# 1. Khởi tạo Engine kết nối với PostgreSQL
# Sử dụng pool_pre_ping=True để tự động kiểm tra kết nối có bị ngắt không trước khi query
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# 2. Khởi tạo SessionLocal factory để cấp phát các phiên làm việc với DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Base class chuẩn bị cho việc định nghĩa các ORM Models sau này
Base = declarative_base()

# 4. Hàm Dependency để sử dụng trong các API Router của FastAPI (Tiêm DB Session)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
