from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VP_", env_file=".env", extra="ignore")
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: PostgresDsn | None = None
    cookie_secure: bool = True
    ocr_language: str = "eng"
    extraction_provider: Literal["offline"] = "offline"
    storage_root: Path = Path.home() / ".vendorproof" / "objects"

    @field_validator("cors_origins")
    @classmethod
    def exact_origins(cls, origins):
        for origin in origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or "*" in origin
                or parts.username
                or parts.password
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("Configure exact HTTP(S) origins")
        return origins
