from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{BASE_DIR / 'app.db'}",
        )
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret")
        if self.environment == "production":
            if self.jwt_secret_key in {
                "dev-only-change-this-secret",
                "change-this-to-a-long-random-secret",
            }:
                raise ValueError("JWT_SECRET_KEY must be configured in production")
            if not os.getenv("FRONTEND_ORIGINS", "").strip():
                raise ValueError("FRONTEND_ORIGINS must contain exact production origins")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        raw_origins = os.getenv(
            "FRONTEND_ORIGINS",
            (
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:8080,http://127.0.0.1:8080,"
                "http://localhost:3000,http://127.0.0.1:3000,"
                "http://localhost:5500,http://127.0.0.1:5500,"
                "http://localhost:8000,http://127.0.0.1:8000,"
                "http://localhost,http://127.0.0.1"
            ),
        )
        self.frontend_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        if self.environment == "production" and any(
            origin == "null" or not origin.startswith("https://")
            for origin in self.frontend_origins
        ):
            raise ValueError("Production FRONTEND_ORIGINS must contain HTTPS origins only")
        # Browsers send Origin: null for file:// pages; allow that only in
        # development. Production must list exact HTTPS origins explicitly.
        if self.environment != "production" and "null" not in self.frontend_origins:
            self.frontend_origins.append("null")
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "8"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
