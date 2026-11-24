from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        hide_input_in_errors=True, env_prefix="VP_", env_file=".env", extra="ignore"
    )
    environment: Literal["development", "testing", "production"] = "development"
    scanner_socket: Path | None = None
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

    @model_validator(mode="after")
    def production_requirements(self):
        if self.environment != "production":
            return self
        required = {"database_url", "cors_origins", "storage_root", "scanner_socket"}
        if (
            not required <= self.model_fields_set
            or not self.database_url
            or not self.scanner_socket
        ):
            raise ValueError(
                "Explicit production database, storage, origins and scanner required"
            )
        if (
            not self.cookie_secure
            or not self.cors_origins
            or any(not o.startswith("https://") for o in self.cors_origins)
        ):
            raise ValueError("Production requires HTTPS origins and secure cookies")
        for origin in self.cors_origins:
            host = urlsplit(origin).hostname
            if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(
                (".invalid", ".localhost")
            ):
                raise ValueError("Configure the approved production hostname")
        url = urlsplit(str(self.database_url))
        params = parse_qs(url.query)
        if set(params) - {"host", "port", "sslmode", "sslrootcert"} or any(
            len(values) != 1 for values in params.values()
        ):
            raise ValueError("Use a single verified PostgreSQL endpoint")
        local_socket = (
            len(params.get("host", [])) == 1
            and params["host"][0].startswith("/")
            and "," not in params["host"][0]
            and "hostaddr" not in params
        )
        if not local_socket and params.get("sslmode") != ["verify-full"]:
            raise ValueError("Use a private PostgreSQL socket or verify-full TLS")
        if (
            not self.storage_root.is_absolute()
            or not self.storage_root.is_dir()
            or self.storage_root.stat().st_mode & 0o077
        ):
            raise ValueError(
                "Pre-create a private absolute storage directory with mode 0700"
            )
        if (
            not self.scanner_socket.is_absolute()
            or not Path("/usr/bin/bwrap").is_file()
        ):
            raise ValueError(
                "Production requires an absolute scanner socket and Linux bubblewrap"
            )
        return self
