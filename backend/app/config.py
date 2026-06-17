from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://contentos:password@localhost:5432/contentos"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "contentos_admin"
    minio_secret_key: str = "password"
    minio_bucket: str = "contentos"
    minio_secure: bool = False

    # AI
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    whisper_mode: str = "api"  # "api" | "local"
    whisper_local_model: str = "base"

    # TikTok OAuth
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    # Google / YouTube OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # LinkedIn OAuth
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # X (Twitter) OAuth 2.0
    x_client_id: str = ""
    x_client_secret: str = ""

    # Auth
    api_secret_token: str = "dev-token"

    # Encryption key для токенов соцсетей (Fernet)
    encryption_key: str = ""

    # Frontend
    frontend_url: str = "http://localhost:3000"


settings = Settings()
