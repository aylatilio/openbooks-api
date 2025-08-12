from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

# Load local .env if present
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    # Runtime
    ENV: str = os.getenv("ENV", "local")

    # Data source
    DATA_CSV: str = os.getenv("DATA_CSV", str(PROJECT_ROOT / "data" / "raw" / "books.csv"))

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "43200"))

    # Admin credentials
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings (cheap, deterministic)."""
    return Settings()


# Singleton-style convenience
settings = get_settings()
