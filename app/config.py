"""Application configuration — all values from environment variables."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/str_feasibility"

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

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # App
    debug: bool = False
    environment: str = "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
