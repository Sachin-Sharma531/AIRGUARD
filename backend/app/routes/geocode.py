import asyncio
import logging
import time
from typing import Dict, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.schemas.geocode import GeocodeRequest, GeocodeResponse
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Geocoding"])

DEFAULT_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "AIRGUARD/0.1.0 (AirGuard Clean Route Navigator; https://github.com/airguard/airguard)"
CACHE_TTL_SECONDS = 86400.0  # 24-hour cache TTL
MAX_CACHE_SIZE = 1024

# In-memory query cache: normalized query string -> (GeocodeResponse, expiry_timestamp)
_geocode_cache: Dict[str, Tuple[GeocodeResponse, float]] = {}
_geocode_lock = asyncio.Lock()


def clear_geocode_cache() -> None:
    """Utility to clear the geocode cache (used in tests and maintenance)."""
    _geocode_cache.clear()


@router.post(
    "/geocode",
    response_model=GeocodeResponse,
    summary="Resolve an address or place name to coordinates",
    description=(
        "Converts a human-readable address to latitude/longitude for the route planner "
        "using OpenStreetMap Nominatim. "
        "Known demo places can be resolved by the frontend without this endpoint."
    ),
    responses={
        404: {"description": "No matching address was found."},
        502: {"description": "Nominatim API returned an upstream error or invalid response."},
        504: {"description": "The Nominatim API request timed out."},
    },
)
async def geocode_address(
    payload: GeocodeRequest,
    settings: Settings = Depends(get_settings),
) -> GeocodeResponse:
    query = payload.address.strip()
    cache_key = query.lower()
    now = time.monotonic()

    # Fast cache check before acquiring serialization lock
    if cache_key in _geocode_cache:
        cached_resp, expires_at = _geocode_cache[cache_key]
        if now < expires_at:
            logger.debug("Geocode cache hit for '%s'", query)
            return cached_resp
        del _geocode_cache[cache_key]

    url = getattr(settings, "NOMINATIM_URL", DEFAULT_NOMINATIM_URL)
    user_agent = getattr(settings, "NOMINATIM_USER_AGENT", DEFAULT_USER_AGENT)
    timeout = getattr(
        settings,
        "GEOCODING_TIMEOUT_SECONDS",
        getattr(settings, "ROUTING_TIMEOUT_SECONDS", 10.0),
    )

    # Serialize Nominatim requests to strictly respect usage policy (no concurrent requests)
    async with _geocode_lock:
        now = time.monotonic()
        # Double-check cache inside lock
        if cache_key in _geocode_cache:
            cached_resp, expires_at = _geocode_cache[cache_key]
            if now < expires_at:
                return cached_resp
            del _geocode_cache[cache_key]

        client = get_http_client(timeout=timeout)
        headers = {"User-Agent": user_agent}
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
        }

        try:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Nominatim API request timed out for '%s'", query)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Nominatim Geocoding API timed out. Please try again.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Nominatim API returned HTTP %s for '%s'", exc.response.status_code, query)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Nominatim Geocoding API returned HTTP {exc.response.status_code}.",
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Could not connect to Nominatim API: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to Nominatim Geocoding API.",
            ) from exc
        except Exception as exc:
            logger.warning("Invalid JSON response from Nominatim API for '%s': %s", query, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API returned an invalid response.",
            ) from exc

        if not isinstance(data, list):
            logger.warning("Nominatim API returned non-list response for '%s': %s", query, type(data))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API returned an invalid response structure.",
            )

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'No location was found for "{payload.address}". Try adding the city or region.',
            )

        first = data[0]
        if not isinstance(first, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API returned an invalid result format.",
            )

        lat_val = first.get("lat")
        lon_val = first.get("lon") if "lon" in first else first.get("lng")
        if lat_val is None or lon_val is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API response missing coordinate fields.",
            )

        try:
            latitude = float(lat_val)
            longitude = float(lon_val)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API returned invalid coordinates.",
            ) from exc

        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nominatim Geocoding API returned out-of-range coordinates.",
            )

        formatted_address = first.get("display_name") or payload.address

        result = GeocodeResponse(
            formatted_address=str(formatted_address),
            latitude=latitude,
            longitude=longitude,
        )

        # Store in cache with eviction if limit exceeded
        if len(_geocode_cache) >= MAX_CACHE_SIZE:
            expired_keys = [k for k, (_, exp) in _geocode_cache.items() if now >= exp]
            for k in expired_keys:
                del _geocode_cache[k]
            if len(_geocode_cache) >= MAX_CACHE_SIZE:
                oldest_key = next(iter(_geocode_cache))
                del _geocode_cache[oldest_key]

        _geocode_cache[cache_key] = (result, now + CACHE_TTL_SECONDS)
        return result
