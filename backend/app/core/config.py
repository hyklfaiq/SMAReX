"""Application settings, loaded from the environment.

Every secret in SMAReX lives here and nowhere else. Values are read from
process environment variables or a local ``.env`` file that is never committed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over the environment. Import via ``get_settings()``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- application ---------------------------------------------------------
    app_name: str = "SMAReX API"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    # Comma separated list of browser origins allowed to call this API.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # -- database ------------------------------------------------------------
    # Supabase PostgreSQL connection string. Use the *pooler* URL on IPv4-only
    # hosts or Supabase free/pro plans: postgresql://...@...:6543/postgres
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="SQLAlchemy async URL for Supabase PostgreSQL.",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # -- Supabase ------------------------------------------------------------
    supabase_url: str = Field(default="https://your-project.supabase.co")
    supabase_anon_key: str = Field(default="")
    # Service-role key: SERVER SIDE ONLY. Grants access to every table and
    # storage object and therefore bypasses RLS. Never expose it to the browser.
    supabase_service_role_key: str = Field(default="")
    supabase_jwt_secret: str = Field(
        default="",
        description=(
            "Legacy HS256 shared secret, used to verify access tokens locally. "
            "Leave EMPTY for projects using asymmetric signing (the modern "
            "Supabase default) -- the JWKS path handles those instead."
        ),
    )
    jwks_cache_seconds: int = Field(
        default=3600,
        ge=60,
        description="How long Supabase's signing keys are cached before refetching.",
    )
    auth_verify_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    storage_bucket: str = "resources"
    signed_url_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    # -- authentication / IIUM Live ------------------------------------------
    # The authoritative copy of this list lives in the table
    # public.allowed_email_domains; this setting is the second check.
    # Only the IIUM Live domain is accepted.
    allowed_email_domains: str = "live.iium.edu.my"
    iium_sso_provider_id: str = Field(
        default="",
        description="Optional Supabase SSO provider id for 'Sign in with IIUM Live'.",
    )

    # -- uploads -------------------------------------------------------------
    max_upload_mb: int = Field(default=25, ge=1, le=200)
    pdf_mime_types: str = "application/pdf,application/x-pdf"
    upload_pipeline_mode: Literal["sync", "background"] = "sync"

    # -- VirusTotal ----------------------------------------------------------
    virustotal_api_key: str = Field(default="")
    virustotal_base_url: str = "https://www.virustotal.com/api/v3"
    virustotal_max_file_mb: int = Field(
        default=25,
        description="VirusTotal's own file upload ceiling (32 MB on the free tier).",
    )
    virustotal_poll_interval_seconds: float = Field(default=2.0, ge=0.5, le=30.0)
    virustotal_poll_max_attempts: int = Field(default=15, ge=1, le=60)
    # A file is withheld when this many engines report it as malicious.
    virustotal_reject_on_malicious: int = Field(default=1, ge=1)
    # A file is withheld for admin review when this many engines flag it as
    # merely suspicious. Set to a very large number to allow suspicious files.
    virustotal_reject_on_suspicious: int = Field(default=1, ge=1)
# -- AI summarisation ----------------------------------------------------
    ai_enabled: bool = True
    ai_model: str = "facebook/bart-large-cnn"
    huggingface_api_key: str = Field(default="")
    huggingface_api_url: str = "https://api-inference.huggingface.co/models"
    huggingface_timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)
    ai_max_input_chars: int = Field(
        default=12_000,
        description="Characters of text fed to the model per chunk.",
    )
    ai_chunk_overlap_chars: int = Field(default=150, ge=0, le=2000)
    ai_max_chunks: int = Field(default=4, ge=1, le=20)
    ai_min_text_chars: int = Field(
        default=200,
        description="Below this extracted length the PDF is treated as unscannable.",
    )
    ai_max_keywords: int = Field(default=10, ge=3, le=30)
    ai_local_device: Literal["cpu", "cuda"] = "cpu"

    # -- logging -------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = False

    # ------------------------------------------------------------------ #
    # Validators and derived helpers
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _normalise_database_url(self) -> "Settings":
        """Force the asyncpg driver.

        Supabase's dashboard happily hands out a plain ``postgresql://`` URL.
        SQLAlchemy then reaches for psycopg, which is not a dependency here, and
        the failure surfaces as a confusing ``No module named 'psycopg'`` at the
        first query rather than as a configuration problem.
        """
        url = self.database_url.strip()
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        self.database_url = url
        return self

    @field_validator("allowed_email_domains")
    @classmethod
    def _normalise_domains(cls, value: str) -> str:
        parts = [d.strip().lower().lstrip("@") for d in value.split(",") if d.strip()]
        return ",".join(parts)

    @model_validator(mode="after")
    def _require_secrets_in_production(self) -> "Settings":
        if self.environment != "production":
            return self
        missing = [
            name
            for name, value in (
                ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
                ("SUPABASE_JWT_SECRET", self.supabase_jwt_secret),
                ("VIRUSTOTAL_API_KEY", self.virustotal_api_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Refusing to start in production without: " + ", ".join(missing)
            )
        return self

    # ------------------------------------------------------------------ #
    # Derived properties
    # ------------------------------------------------------------------ #
    @property
    def allowed_domain_list(self) -> list[str]:
        return [d for d in self.allowed_email_domains.split(",") if d]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def virustotal_max_file_bytes(self) -> int:
        return self.virustotal_max_file_mb * 1024 * 1024

    @property
    def allowed_pdf_mime_types(self) -> tuple[str, ...]:
        return tuple(m.strip() for m in self.pdf_mime_types.split(",") if m.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so the environment is parsed exactly once per process."""
    return Settings()