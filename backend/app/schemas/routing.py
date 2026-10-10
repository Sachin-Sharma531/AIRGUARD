from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.analyze import AQICategory


class RoutePreference(str, Enum):
    FASTER = "faster"
    BALANCED = "balanced"
    CLEANER = "cleaner"


class TravelMode(str, Enum):
    DRIVE = "DRIVE"
    WALK = "WALK"
    BICYCLE = "BICYCLE"
    TWO_WHEELER = "TWO_WHEELER"


class ExposureStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNAVAILABLE = "UNAVAILABLE"


class Coordinates(BaseModel):
    """Geographic coordinates with validation."""
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (-90.0 to 90.0)",
        examples=[28.6139],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (-180.0 to 180.0)",
        examples=[77.2090],
    )


class RoutePlanRequest(BaseModel):
    """
    Input schema for requesting a pollution-aware route plan.
    """
    origin: Coordinates = Field(
        ...,
        description="Starting location coordinates",
    )
    destination: Coordinates = Field(
        ...,
        description="Destination location coordinates",
    )
    preference: RoutePreference = Field(
        default=RoutePreference.BALANCED,
        description="Routing trade-off preference: 'faster', 'balanced', or 'cleaner'",
    )
    travel_mode: TravelMode = Field(
        default=TravelMode.DRIVE,
        description="Mode of travel: DRIVE, WALK, BICYCLE, or TWO_WHEELER",
    )
    compute_alternatives: bool = Field(
        default=True,
        description="Whether to request alternative routes from routing provider",
    )

    @model_validator(mode="after")
    def validate_endpoints_differ(self) -> "RoutePlanRequest":
        if (
            abs(self.origin.latitude - self.destination.latitude) < 1e-6
            and abs(self.origin.longitude - self.destination.longitude) < 1e-6
        ):
            raise ValueError("Origin and destination coordinates must be distinct locations.")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "origin": {"latitude": 28.6139, "longitude": 77.2090},
                "destination": {"latitude": 28.5355, "longitude": 77.3910},
                "preference": "balanced",
                "travel_mode": "DRIVE",
                "compute_alternatives": True,
            }
        }
    }


class RouteDetails(BaseModel):
    """
    Detailed metrics for a candidate or recommended route.
    """
    route_id: str = Field(..., description="Unique identifier for candidate route")
    description: Optional[str] = Field(None, description="Summary or primary highway / road of route")
    distance_meters: int = Field(..., ge=0, description="Total travel distance in meters")
    duration_seconds: int = Field(..., ge=0, description="Total estimated travel duration in seconds")
    distance_formatted: str = Field(..., description="Human-readable distance (e.g. '15.4 km')")
    duration_formatted: str = Field(..., description="Human-readable duration (e.g. '24 mins')")
    estimated_exposure_score: Optional[float] = Field(
        None,
        ge=0.0,
        description="Estimated cumulative pollution exposure index along route",
    )
    average_aqi: Optional[float] = Field(
        None,
        ge=0.0,
        description="Time-weighted average AQI along route path",
    )
    air_quality_category: Optional[AQICategory] = Field(
        None,
        description="Dominant or average air quality health category along route",
    )
    exposure_status: ExposureStatus = Field(
        default=ExposureStatus.UNAVAILABLE,
        description="Status of exposure evaluation: ESTIMATED, INSUFFICIENT_DATA, or UNAVAILABLE",
    )
    polyline: Optional[str] = Field(
        None,
        description="Encoded polyline representation of route path for map visualization",
    )
    waypoints_sampled: int = Field(
        default=0,
        description="Number of geographic checkpoints sampled for air quality evaluation",
    )
    score: Optional[float] = Field(
        None,
        description="Normalized combined objective score (lower is better)",
    )
    normalized_time: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Normalized travel time index between 0.0 (fastest) and 1.0 (slowest)",
    )
    normalized_exposure: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Normalized exposure index between 0.0 (cleanest) and 1.0 (most polluted)",
    )
    is_recommended: bool = Field(
        default=False,
        description="True if this route is selected as the recommended option",
    )


class RoutePlanResponse(BaseModel):
    """
    Response schema returning the optimal route alongside evaluated alternatives.
    """
    recommended_route: RouteDetails = Field(..., description="Recommended optimal route")
    alternative_routes: List[RouteDetails] = Field(
        default_factory=list,
        description="Alternative routes evaluated during selection",
    )
    preference: RoutePreference = Field(..., description="Trade-off preference applied")
    summary: str = Field(..., description="Explanation of the trade-off and selection rationale")
    data_limitations: List[str] = Field(
        default_factory=list,
        description="Disclaimers, data freshness observations, or coverage limits",
    )
