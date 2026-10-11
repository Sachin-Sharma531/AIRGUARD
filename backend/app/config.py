import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings validated using Pydantic.
    Loads values from environment variables or a local .env file.
    """
    APP_NAME: str = "AIRGUARD"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",
    ]


    # Google APIs Configuration
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_ROUTES_API_KEY: Optional[str] = None
    GOOGLE_AIR_QUALITY_API_KEY: Optional[str] = None
    GOOGLE_GEOCODING_API_KEY: Optional[str] = None

    # Geocoding Configuration (OpenStreetMap Nominatim)
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
    NOMINATIM_USER_AGENT: str = "AIRGUARD/0.1.0 (AirGuard Clean Route Navigator; contact: https://github.com/airguard/airguard)"
    GEOCODING_TIMEOUT_SECONDS: float = 10.0

    # Routing Service Configuration
    ROUTING_TIMEOUT_SECONDS: float = 10.0
    ROUTING_MAX_SAMPLE_POINTS: int = 8

    # Route Scoring Weights: (time_weight, pollution_weight)
    ROUTING_WEIGHT_FASTER_TIME: float = 0.85
    ROUTING_WEIGHT_FASTER_POLLUTION: float = 0.15
    ROUTING_WEIGHT_BALANCED_TIME: float = 0.50
    ROUTING_WEIGHT_BALANCED_POLLUTION: float = 0.50
    ROUTING_WEIGHT_CLEANER_TIME: float = 0.15
    ROUTING_WEIGHT_CLEANER_POLLUTION: float = 0.85

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[List[str], str]) -> List[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def get_routes_api_key(self) -> Optional[str]:
        """Returns the specific Routes API key, falling back to the general Maps API key."""
        return self.GOOGLE_ROUTES_API_KEY or self.GOOGLE_MAPS_API_KEY

    def get_air_quality_api_key(self) -> Optional[str]:
        """Returns the specific Air Quality API key, falling back to the general Maps API key."""
        return self.GOOGLE_AIR_QUALITY_API_KEY or self.GOOGLE_MAPS_API_KEY

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the settings so the .env file is only parsed once.
    """
    return Settings()

