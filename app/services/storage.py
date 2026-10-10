import abc
import logging
import mimetypes
from pathlib import Path

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageProvider(abc.ABC):
    """Interface trừu tượng mọi thao tác lưu trữ file"""
    @abc.abstractmethod
    def save_file(self, filename: str, data: bytes) -> str:
        pass

    @abc.abstractmethod
    def get_file(self, file_path: str) -> bytes:
        pass


# Implementation V1: Lưu Local (Dành cho Dev/Test)
class LocalStorage(StorageProvider):
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename: str, data: bytes) -> str:
        file_path = self.base_dir / filename
        # Đảm bảo thư mục cha tồn tại (Vì filename có thể là dạng 'message_id/file.pdf')
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        logger.info(f"Đã lưu local file: {file_path}")
        return str(file_path)

    def get_file(self, file_path: str) -> bytes:
        return Path(file_path).read_bytes()


# Implementation V2: Lưu Cloud Supabase (Dành cho Production)
class SupabaseStorage(StorageProvider):
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        self.bucket_name = "email_attachments"

    def save_file(self, filename: str, data: bytes) -> str:
        try:
            # Đoán MIME type dựa vào đuôi file
            mime_type, _ = mimetypes.guess_type(filename)
            mime_type = mime_type or "application/octet-stream"

            self.supabase.storage.from_(self.bucket_name).upload(
                path=filename,
                file=data,
                file_options={"content-type": mime_type, "upsert": "true"}
            )
            logger.info(f"Đã upload {filename} lên bucket {self.bucket_name}")
            return filename
        except Exception as e:
            logger.error(f"Lỗi upload Supabase Storage ({filename}): {e}")
            raise

    def get_file(self, file_path: str) -> bytes:
        try:
            res = self.supabase.storage.from_(self.bucket_name).download(file_path)
            return res
        except Exception as e:
            logger.error(f"Lỗi tải file Supabase Storage ({file_path}): {e}")
            raise


# Dependency Injection function
def get_storage() -> StorageProvider:
    # Bạn chỉ cần đổi return LocalStorage() thành return SupabaseStorage()
    return SupabaseStorage()
