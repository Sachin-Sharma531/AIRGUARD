import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.schemas.geocode import GeocodeRequest, GeocodeResponse
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Geocoding"])
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@router.post(
    "/geocode",
    response_model=GeocodeResponse,
    summary="Resolve an address or place name to coordinates",
    description=(
        "Converts a human-readable address to latitude/longitude for the route planner. "
        "Known demo places can be resolved by the frontend without this endpoint."
    ),
    responses={
        404: {"description": "No matching address was found."},
        502: {"description": "Google Geocoding API rejected the request or returned an upstream error."},
        503: {"description": "Google Geocoding API credentials are not configured."},
        504: {"description": "The Google Geocoding API request timed out."},
    },
)
async def geocode_address(
    payload: GeocodeRequest,
    settings: Settings = Depends(get_settings),
) -> GeocodeResponse:
    api_key = settings.GOOGLE_GEOCODING_API_KEY or settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google Geocoding API key is not configured. Set GOOGLE_GEOCODING_API_KEY "
                "or GOOGLE_MAPS_API_KEY in backend/.env."
            ),
        )

    client = get_http_client(timeout=settings.ROUTING_TIMEOUT_SECONDS)
    try:
        response = await client.get(
            GEOCODING_URL,
            params={"address": payload.address, "key": api_key},
            timeout=settings.ROUTING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        logger.warning("Google Geocoding API request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Geocoding API timed out. Please try again.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Google Geocoding API returned HTTP %s", exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Geocoding API returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("Could not connect to Google Geocoding API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to Google Geocoding API.",
        ) from exc

    provider_status = data.get("status")
    if provider_status == "ZERO_RESULTS":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No location was found for "{payload.address}". Try adding the city or region.',
        )
    if provider_status != "OK" or not data.get("results"):
        if provider_status in {"REQUEST_DENIED", "OVER_DAILY_LIMIT"}:
            detail = (
                "Google Geocoding API denied the request. Enable the Geocoding API in the Google Cloud project, "
                "check key restrictions and billing, then retry."
            )
        else:
            detail = f"Google Geocoding API returned status {provider_status or 'UNKNOWN'}."
        logger.warning("Google Geocoding API provider status: %s", provider_status)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    first = data["results"][0]
    location = first.get("geometry", {}).get("location", {})
    try:
        latitude = float(location["lat"])
        longitude = float(location["lng"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Geocoding API returned an invalid coordinate result.",
        ) from exc

    return GeocodeResponse(
        formatted_address=first.get("formatted_address", payload.address),
        latitude=latitude,
        longitude=longitude,
    )
