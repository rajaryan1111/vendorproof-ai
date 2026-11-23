from pathlib import Path
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VP_", env_file=".env", extra="ignore")
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: PostgresDsn | None = None
    cookie_secure: bool = True
    storage_root: Path = Path.home() / ".vendorproof" / "objects"
