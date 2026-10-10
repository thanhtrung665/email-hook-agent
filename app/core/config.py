from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Email Hook Agent"

    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Auth
    MS_CLIENT_ID: str
    MS_CLIENT_SECRET: str
    MS_REDIRECT_URI: str
    MS_TENANT_ID: str
    MS_TARGET_MAILBOX: str = "drilling@psbvn.com"

    AUTH_SCOPE: list[str] = [
        "User.Read",
        "Mail.Read",
        "Mail.Send",
        "Mail.ReadWrite",
        "MailboxSettings.Read"
    ]

    # Bắt buộc phải có Key để Agent hoạt động
    GEMINI_API_KEY: str

    # Cấu hình webhook
    WEBHOOK_BASE_URL: str
    WEBHOOK_SECRET: str = "PSBV16YenThe"

    # Điểm nối sang webapp PSBV (SPEC G2 + P8 Email Gateway BFF)
    WEBAPP_BASE_URL: str = "http://localhost:3000"
    SERVICE_ROLE_SECRET: str = ""

    # ===== Lịch hoạt động của Agent =====
    # Múi giờ dùng để quyết định "mấy giờ là giờ làm" cho hòm thư
    AGENT_TIMEZONE: str = "Asia/Ho_Chi_Minh"
    # Khung giờ hoạt động (HH:MM). Nếu START > END thì coi là khung qua đêm
    # (vd 22:00 -> 06:00 nghĩa là hoạt động từ 22h tới 6h sáng hôm sau).
    AGENT_ACTIVE_START: str = "08:00"
    AGENT_ACTIVE_END: str = "18:00"
    # Các ngày trong tuần được phép chạy, phân cách bằng dấu phẩy
    AGENT_ACTIVE_DAYS: str = "mon,tue,wed,thu,fri,sat,sun"

    # ===== Thu thập email (polling) =====
    INGESTION_ENABLED: bool = True
    # Chu kỳ thăm dò email mới khi đang trong khung giờ hoạt động
    INGESTION_POLL_INTERVAL_SECONDS: int = 60
    # Khi lỗi liên tiếp, chờ bao lâu trước lần thử lại
    INGESTION_ERROR_BACKOFF_SECONDS: int = 300
    # Quét ngược về bao nhiêu ngày khi bắt đầu lại từ đầu (không có cursor)
    INGESTION_CATCHUP_DAYS: int = 7
    # Số email lấy mỗi lần gọi Graph delta
    INGESTION_BATCH_SIZE: int = 25
    # Chặn trên số trang delta gọi liên tiếp trong một vòng
    INGESTION_MAX_PAGES: int = 10
    # Nghỉ giữa các email để không dồn tải lên Gemini
    INGESTION_PER_EMAIL_DELAY_SECONDS: float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
