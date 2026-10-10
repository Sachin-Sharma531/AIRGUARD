import asyncio
import time
from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import httpx
from app.config import Settings, get_settings
from app.schemas.analyze import AQICategory
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


class AirQualityReading(BaseModel):
    """Normalized snapshot of air quality measurements for a geographic point."""
    aqi: Optional[int] = Field(None, description="Reported AQI value (0-500+ or 0-100 UAQI)")
    category: Optional[AQICategory] = Field(None, description="Categorical air quality impact level")
    dominant_pollutant: Optional[str] = Field(None, description="Dominant pollutant driving index")
    pollutants: Dict[str, float] = Field(
        default_factory=dict,
        description="Observed pollutant concentrations mapped by code (e.g. pm25, pm10)",
    )
    is_valid: bool = Field(True, description="False if provider has no data or point is outside coverage")
    timestamp: Optional[str] = Field(None, description="Observation timestamp from data provider")


class BaseAirQualityProvider(ABC):
    """
    Abstract interface for air quality data providers.
    Enables isolated unit testing, mocking, and provider alternatives.
    """

    @abstractmethod
    async def get_air_quality(self, lat: float, lng: float) -> AirQualityReading:
        """Fetch air quality observation for a single coordinate."""
        pass

    async def get_air_quality_batch(
        self,
        locations: List[Tuple[float, float]],
    ) -> List[AirQualityReading]:
        """Fetch air quality observations concurrently for a series of coordinates."""
        if not locations:
            return []
        tasks = [self.get_air_quality(lat, lng) for lat, lng in locations]
        results = await asyncio.gather(*tasks)
        return list(results)


class GoogleAirQualityClient(BaseAirQualityProvider):
    """
    Client for Google Air Quality API (currentConditions:lookup) with time-bounded in-memory caching.
    """
    BASE_URL = "https://airquality.googleapis.com/v1/currentConditions:lookup"
    DEFAULT_CACHE_TTL_SECONDS = 1800.0  # 30-minute validity window for ambient air data

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.settings = settings or get_settings()
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        # Maps (rounded_lat, rounded_lng) -> (AirQualityReading, expires_at_monotonic)
        self._cache: Dict[Tuple[float, float], Tuple[AirQualityReading, float]] = {}
        self._logged_missing_key: bool = False

    def _get_client(self) -> httpx.AsyncClient:
        return self.client or get_http_client(timeout=self.settings.ROUTING_TIMEOUT_SECONDS)

    @staticmethod
    def _map_category(cat_str: Optional[str], aqi: Optional[int]) -> Optional[AQICategory]:
        if not cat_str and aqi is None:
            return None
        text = (cat_str or "").lower()
        if "good" in text:
            return AQICategory.GOOD
        if "moderate" in text:
            return AQICategory.MODERATE
        if "sensitive" in text:
            return AQICategory.UNHEALTHY_SENSITIVE
        if "very unhealthy" in text:
            return AQICategory.VERY_UNHEALTHY
        if "unhealthy" in text:
            return AQICategory.UNHEALTHY
        if "hazardous" in text:
            return AQICategory.HAZARDOUS

        # Fallback to AQI scale if category text was unrecognized
        if aqi is not None:
            if aqi <= 50:
                return AQICategory.GOOD
            if aqi <= 100:
                return AQICategory.MODERATE
            if aqi <= 150:
                return AQICategory.UNHEALTHY_SENSITIVE
            if aqi <= 200:
                return AQICategory.UNHEALTHY
            if aqi <= 300:
                return AQICategory.VERY_UNHEALTHY
            return AQICategory.HAZARDOUS
        return None

    async def get_air_quality(self, lat: float, lng: float) -> AirQualityReading:
        # Cache key rounded to ~110m resolution (3 decimals) to deduplicate overlapping route points
        cache_key = (round(lat, 3), round(lng, 3))
        now = time.monotonic()

        if cache_key in self._cache:
            cached_reading, expires_at = self._cache[cache_key]
            if now < expires_at:
                return cached_reading
            del self._cache[cache_key]

        api_key = self.settings.get_air_quality_api_key()
        if not api_key:
            if not self._logged_missing_key:
                logger.warning("Google Air Quality API key is not configured. Returning invalid reading.")
                self._logged_missing_key = True
            return AirQualityReading(is_valid=False)

        payload = {
            "location": {
                "latitude": lat,
                "longitude": lng,
            },
            "extraComputations": [
                "POLLUTANT_ADDITIONAL_INFO",
                "LOCAL_AQI",
            ],
        }

        client = self._get_client()
        try:
            response = await client.post(
                f"{self.BASE_URL}?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.settings.ROUTING_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                logger.warning(
                    "Google Air Quality API responded with status %s for (%f, %f): %s",
                    response.status_code,
                    lat,
                    lng,
                    response.text,
                )
                # Transient errors are NOT cached to avoid poison caching
                return AirQualityReading(is_valid=False)

            data = response.json()
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Google Air Quality API request error for (%f, %f): %s", lat, lng, exc)
            return AirQualityReading(is_valid=False)

        # Parse indexes
        indexes = data.get("indexes", [])
        chosen_index = None
        for idx in indexes:
            # Prefer local AQI if present, otherwise UAQI
            if idx.get("code") != "uaqi":
                chosen_index = idx
                break
        if not chosen_index and indexes:
            chosen_index = indexes[0]

        aqi_val = chosen_index.get("aqi") if chosen_index else None
        cat_str = chosen_index.get("category") if chosen_index else None
        dominant_pollutant = chosen_index.get("dominantPollutant") if chosen_index else None
        category = self._map_category(cat_str, aqi_val)
        timestamp = data.get("dateTime")

        # Parse pollutants
        pollutants_map: Dict[str, float] = {}
        for p in data.get("pollutants", []):
            code = p.get("code", "").lower()
            conc = p.get("concentration", {}).get("value")
            if code and conc is not None:
                try:
                    pollutants_map[code] = float(conc)
                except (ValueError, TypeError):
                    pass

        reading = AirQualityReading(
            aqi=aqi_val,
            category=category,
            dominant_pollutant=dominant_pollutant,
            pollutants=pollutants_map,
            is_valid=aqi_val is not None,
            timestamp=timestamp,
        )

        if reading.is_valid:
            self._cache[cache_key] = (reading, now + self.cache_ttl_seconds)

        return reading
