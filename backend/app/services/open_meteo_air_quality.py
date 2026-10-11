
import logging
from typing import Dict, Optional

import httpx

from app.config import Settings, get_settings
from app.schemas.analyze import AQICategory
from app.services.google_air_quality import (
    AirQualityReading,
    BaseAirQualityProvider,
)
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


class OpenMeteoAirQualityClient(BaseAirQualityProvider):
    """Fetch model-based air-quality estimates from Open-Meteo."""

    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.client = client

    def _get_client(self) -> httpx.AsyncClient:
        return self.client or get_http_client(
            timeout=self.settings.ROUTING_TIMEOUT_SECONDS
        )

    @staticmethod
    def _category(aqi: Optional[int]) -> Optional[AQICategory]:
        if aqi is None:
            return None
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

    async def get_air_quality(self, lat: float, lng: float) -> AirQualityReading:
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": "pm2_5,pm10,us_aqi",
        }

        try:
            response = await self._get_client().get(
                self.BASE_URL,
                params=params,
                timeout=self.settings.ROUTING_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Open-Meteo air-quality request failed: %s", exc)
            return AirQualityReading(is_valid=False)

        current = data.get("current") or {}
        aqi_value = current.get("us_aqi")
        if aqi_value is None:
            return AirQualityReading(is_valid=False)

        try:
            aqi = int(round(float(aqi_value)))
            pollutants: Dict[str, float] = {}
            for key in ("pm2_5", "pm10"):
                value = current.get(key)
                if value is not None:
                    pollutants[key] = float(value)
        except (TypeError, ValueError):
            return AirQualityReading(is_valid=False)

        return AirQualityReading(
            aqi=aqi,
            category=self._category(aqi),
            dominant_pollutant=None,
            pollutants=pollutants,
            is_valid=True,
            timestamp=current.get("time"),
        )
