import os


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./taskly.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_ttl_minutes: int = int(os.getenv("JWT_TTL_MINUTES", "60"))
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    reminder_hour: int = int(os.getenv("REMINDER_HOUR", "8"))


settings = Settings()
