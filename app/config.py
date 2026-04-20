"""Application configuration — all values from environment variables."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database — resolved in priority order:
    # 1. DATABASE_URL env var (explicit)
    # 2. Constructed from SUPABASE_URL + SUPABASE_DB_PASSWORD
    # 3. SQLite fallback for local dev
    database_url: str = ""  # Resolved via get_database_url()

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_access_token: Optional[str] = None
    supabase_db_password: Optional[str] = None  # DB password from Supabase dashboard

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # External APIs
    airdna_api_key: Optional[str] = None
    walkscore_api_key: Optional[str] = None
    google_geocoding_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # AirROI / Nominatim
    airroi_api_url: str = "https://www.airroi.com"
    nominatim_url: str = "https://nominatim.openstreetmap.org"

    # Analysis defaults
    comp_search_radius_km: float = 5.0
    comp_min_count: int = 5
    mc_simulations: int = 2000

    # CORS — accepts JSON list string or comma-separated string from env
    cors_origins: str = "http://localhost:3000,https://str-feasibility-calculator.vercel.app,https://frontend-qbxwjzzcm-live-luxe.vercel.app"

    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS as either JSON list or comma-separated string."""
        import json
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # App
    debug: bool = False
    environment: str = "production"

    def get_database_url(self) -> str:
        """
        Resolve database URL in priority order:
        1. Explicit DATABASE_URL (if not SQLite default and not empty)
        2. Supabase URL + DB password → asyncpg connection string
        3. SQLite fallback
        """
        # If DATABASE_URL is explicitly set to something non-SQLite, use it
        if self.database_url and "sqlite" not in self.database_url:
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url

        # Construct from Supabase URL + password
        if self.supabase_url and self.supabase_db_password:
            # Extract project ref from URL: https://[ref].supabase.co
            ref = self.supabase_url.replace("https://", "").split(".")[0]
            return (
                f"postgresql+asyncpg://postgres:{self.supabase_db_password}"
                f"@db.{ref}.supabase.co:5432/postgres"
            )

        # SQLite fallback — use /tmp on serverless (read-only filesystem)
        import os, tempfile
        if os.environ.get("VERCEL") or not os.access(".", os.W_OK):
            return f"sqlite+aiosqlite:///{os.path.join(tempfile.gettempdir(), 'str_feasibility.db')}"
        return "sqlite+aiosqlite:///./str_feasibility_dev.db"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
