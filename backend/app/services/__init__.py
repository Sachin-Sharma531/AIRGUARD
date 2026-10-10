"""Services package for external API integrations and routing optimization."""

from app.services.google_air_quality import (
    AirQualityReading,
    BaseAirQualityProvider,
    GoogleAirQualityClient,
)
from app.services.google_routes import (
    BaseRoutesProvider,
    GoogleRoutesClient,
    RawRouteCandidate,
)
from app.services.http_client import close_http_client, get_http_client
from app.services.polyline import (
    decode_polyline,
    haversine_distance,
    sample_polyline_coordinates,
)
from app.services.route_optimizer import (
    RouteOptimizerService,
    format_distance,
    format_duration,
    get_route_optimizer,
    map_aqi_to_category,
)

__all__ = [
    "AirQualityReading",
    "BaseAirQualityProvider",
    "BaseRoutesProvider",
    "GoogleAirQualityClient",
    "GoogleRoutesClient",
    "RawRouteCandidate",
    "RouteOptimizerService",
    "close_http_client",
    "decode_polyline",
    "format_distance",
    "format_duration",
    "get_http_client",
    "get_route_optimizer",
    "haversine_distance",
    "map_aqi_to_category",
    "sample_polyline_coordinates",
]
