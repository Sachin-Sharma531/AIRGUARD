"""Pydantic schemas for data validation and API serialization."""

from app.schemas.analyze import AQICategory, AnalyzeRequest, AnalyzeResponse
from app.schemas.forecast import ForecastResponse, StationsResponse
from app.schemas.geocode import GeocodeRequest, GeocodeResponse
from app.schemas.routing import (
    Coordinates,
    ExposureStatus,
    RouteDetails,
    RoutePlanRequest,
    RoutePlanResponse,
    RoutePreference,
    TravelMode,
)

__all__ = [
    "AQICategory",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "Coordinates",
    "ExposureStatus",
    "ForecastResponse",
    "GeocodeRequest",
    "GeocodeResponse",
    "RouteDetails",
    "RoutePlanRequest",
    "RoutePlanResponse",
    "RoutePreference",
    "StationsResponse",
    "TravelMode",
]

