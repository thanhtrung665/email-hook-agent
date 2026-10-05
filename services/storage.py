import abc
import os
from pathlib import Path

class StorageProvider(abc.ABC):
    """Interface trừu tượng mọi thao tác lưu trữ file"""
    @abc.abstractmethod
    async def save_file(self, filename: str, data: bytes) -> str:
        pass

    @abc.abstractmethod
    def get_file(self, file_path: str) -> bytes:
        pass


# Implementation V1 Lưu local
class LocalStorage(StorageProvider):
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename: str, data: bytes) -> str:
        file_path = self.base_dir / filename
        file_path.write_bytes(data)
        return str(file_path)

    def get_file(self, file_path: str) -> bytes:
        return Path(file_path).read_bytes()


# Dêpndency Injection function
def get_storage() -> StorageProvider:
    return LocalStorage() # Chỉ cần đổi dòng này thành S3Storage()