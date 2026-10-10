from abc import ABC, abstractmethod
import logging
from typing import List, Optional
from pydantic import BaseModel
import httpx
from fastapi import HTTPException, status
from app.config import Settings, get_settings
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


class RawRouteCandidate(BaseModel):
    """Normalized route candidate data from routing provider."""
    route_id: str
    description: Optional[str] = None
    distance_meters: int
    duration_seconds: int
    polyline_encoded: Optional[str] = None
    warnings: List[str] = []


class BaseRoutesProvider(ABC):
    """
    Abstract interface for route calculation providers.
    Allows easy unit testing, mocking, and provider substitution.
    """

    @abstractmethod
    async def get_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        compute_alternatives: bool = True,
    ) -> List[RawRouteCandidate]:
        """Fetch candidate routes between origin and destination."""
        pass


class GoogleRoutesClient(BaseRoutesProvider):
    """
    Integration client for the Google Routes API (Directions v2).
    """
    ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.client = client

    def _get_client(self) -> httpx.AsyncClient:
        return self.client or get_http_client(timeout=self.settings.ROUTING_TIMEOUT_SECONDS)

    @staticmethod
    def _parse_duration_seconds(duration_str: Optional[str]) -> int:
        if not duration_str:
            return 0
        cleaned = duration_str.strip().rstrip("s")
        try:
            return int(float(cleaned))
        except ValueError:
            return 0

    async def get_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        compute_alternatives: bool = True,
    ) -> List[RawRouteCandidate]:
        api_key = self.settings.get_routes_api_key()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Routes API key is not configured. Set GOOGLE_MAPS_API_KEY or GOOGLE_ROUTES_API_KEY in the environment.",
            )

        # Mapping travel mode according to Google Routes API specs
        mode_mapping = {
            "DRIVE": "DRIVE",
            "WALK": "WALK",
            "BICYCLE": "BICYCLE",
            "TWO_WHEELER": "TWO_WHEELER",
        }
        mapped_mode = mode_mapping.get(travel_mode.upper(), "DRIVE")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "routes.duration,"
                "routes.distanceMeters,"
                "routes.polyline.encodedPolyline,"
                "routes.description,"
                "routes.warnings"
            ),
        }

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin_lat,
                        "longitude": origin_lng,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": dest_lat,
                        "longitude": dest_lng,
                    }
                }
            },
            "travelMode": mapped_mode,
            "computeAlternativeRoutes": compute_alternatives,
        }
        # Google Routes only permits routingPreference for DRIVE and TWO_WHEELER.
        # Supplying ROUTING_PREFERENCE_UNSPECIFIED for WALK or BICYCLE is still
        # an invalid request, so leave the field out for those travel modes.
        if mapped_mode in {"DRIVE", "TWO_WHEELER"}:
            payload["routingPreference"] = "TRAFFIC_AWARE"

        client = self._get_client()
        try:
            response = await client.post(
                self.ROUTES_API_URL,
                json=payload,
                headers=headers,
                timeout=self.settings.ROUTING_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.error("Google Routes API request timed out: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Upstream Google Routes service timed out. Please try again shortly.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Google Routes API returned HTTP error: %s - %s", exc.response.status_code, exc.response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream Google Routes service error (HTTP {exc.response.status_code}).",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Google Routes API network request failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to Google Routes service.",
            ) from exc

        routes = data.get("routes", [])
        if not routes:
            return []

        candidates: List[RawRouteCandidate] = []
        for idx, route in enumerate(routes):
            polyline = route.get("polyline", {}).get("encodedPolyline")
            distance = route.get("distanceMeters", 0)
            duration = self._parse_duration_seconds(route.get("duration"))
            desc = route.get("description")
            warnings = route.get("warnings", [])

            candidates.append(
                RawRouteCandidate(
                    route_id=f"route-{idx + 1}",
                    description=desc,
                    distance_meters=distance,
                    duration_seconds=duration,
                    polyline_encoded=polyline,
                    warnings=warnings if isinstance(warnings, list) else [],
                )
            )

        return candidates
