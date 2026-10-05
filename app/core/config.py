from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Email Hook Agent"

    # Database
    DATABASE_URL: str = ""

    # Auth
    MS_CLIENT_ID: str
    MS_CLIENT_SECRET: str
    MS_REDIRECT_URI: str
    MS_TENANT_ID: str = "common"
    AUTH_SCOPE: list[str] = [
        "User.Read",
        "Mail.Read",
        "Mail.Send",
        "Mail.ReadWrite",
        "MailboxSettings.Read"
    ]

    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()