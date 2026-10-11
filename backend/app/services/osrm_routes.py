
import logging
from typing import List, Optional

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.services.google_routes import BaseRoutesProvider, RawRouteCandidate
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


class OSRMRoutesClient(BaseRoutesProvider):
    """Open-source routing client using the public OSRM driving service."""

    ROUTES_API_BASE_URL = "https://router.project-osrm.org/route/v1"

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
        travel_mode: str = "DRIVE",
        compute_alternatives: bool = True,
    ) -> List[RawRouteCandidate]:
        

        profiles = {
            "DRIVE": "driving",
            "WALK": "foot",
            "BICYCLE": "cycling",
        }

        profile = profiles.get(travel_mode.upper())

        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported travel mode: {travel_mode}",
            )


        params = {
            "alternatives": "true" if compute_alternatives else "false",
            "overview": "full",
            "geometries": "polyline",
            "steps": "false",
        }
        url = (
            f"{self.ROUTES_API_BASE_URL}/{profile}/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        )

        try:
            response = await self._get_client().get(
                url,
                params=params,
                timeout=self.settings.ROUTING_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("OSRM request timed out: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The free routing service timed out. Please retry or use Demo mode.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("OSRM returned HTTP %s", exc.response.status_code)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The free routing service is temporarily unavailable. Please retry or use Demo mode.",
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            logger.warning("OSRM request failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not retrieve a route from the free routing service.",
            ) from exc

        if data.get("code") != "Ok":
            if data.get("code") == "NoRoute":
                return []
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The free routing service could not calculate this journey.",
            )

        candidates: List[RawRouteCandidate] = []
        for index, route in enumerate(data.get("routes", [])):
            geometry = route.get("geometry")
            if not geometry:
                continue

            candidates.append(
                RawRouteCandidate(
                    route_id=f"osrm-route-{index + 1}",
                    description="OSRM driving route",
                    distance_meters=round(route.get("distance", 0)),
                    duration_seconds=round(route.get("duration", 0)),
                    polyline_encoded=geometry,
                    warnings=[],
                )
            )

        return candidates
