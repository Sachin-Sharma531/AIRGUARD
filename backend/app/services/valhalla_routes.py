
import logging
from typing import List, Optional

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.services.google_routes import BaseRoutesProvider, RawRouteCandidate
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


class ValhallaRoutesClient(BaseRoutesProvider):
    """Open-source routing client for walking, cycling, and motorcycle routes."""

    ROUTES_API_URL = "https://valhalla1.openstreetmap.de/route"

    COSTING_MODES = {
        "WALK": "pedestrian",
        "BICYCLE": "bicycle",
        "TWO_WHEELER": "motorcycle",
    }

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

    async def get_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "WALK",
        compute_alternatives: bool = True,
    ) -> List[RawRouteCandidate]:
        costing = self.COSTING_MODES.get(travel_mode.upper())

        if costing is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Valhalla does not support travel mode: {travel_mode}",
            )

        
        payload = {
            "locations": [
                {"lat": origin_lat, "lon": origin_lng},
                {"lat": dest_lat, "lon": dest_lng},
            ],
            "costing": costing,
            "units": "kilometers",
            "alternates": 2 if compute_alternatives else 0,
        }


        try:
            response = await self._get_client().post(
                self.ROUTES_API_URL,
                json=payload,
                timeout=self.settings.ROUTING_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Valhalla request timed out: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The free routing service timed out. Please retry or use Demo mode.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Valhalla returned HTTP %s", exc.response.status_code)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The free routing service is temporarily unavailable. Please retry or use Demo mode.",
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            logger.warning("Valhalla request failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not retrieve a route from the free routing service.",
            ) from exc

        trip = data.get("trip") or {}
        summary = trip.get("summary") or {}
        legs = trip.get("legs") or []
        shape = legs[0].get("shape") if legs else trip.get("shape")

        if not shape or not summary:
            if data.get("error"):
                logger.warning("Valhalla could not calculate route: %s", data["error"])
            return []

        distance_km = summary.get("length")
        duration_seconds = summary.get("time")

        if distance_km is None or duration_seconds is None:
            return []

        return [
            RawRouteCandidate(
                route_id=f"valhalla-{travel_mode.lower()}-1",
                description=f"Valhalla {travel_mode.lower()} route",
                distance_meters=round(float(distance_km) * 1000),
                duration_seconds=round(float(duration_seconds)),
                polyline_encoded=shape,
                warnings=[],
            )
        ]
