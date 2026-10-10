"""Reusable mock fixtures and deterministic datasets for AIRGUARD testing."""

from app.schemas.analyze import AQICategory
from app.schemas.routing import Coordinates
from app.services.google_air_quality import AirQualityReading
from app.services.google_routes import RawRouteCandidate

# Pre-defined test locations (clearly labelled synthetic test coordinates)
LOCATIONS = {
    "delhi_connaught_place": Coordinates(latitude=28.6315, longitude=77.2167),
    "noida_sector_62": Coordinates(latitude=28.6280, longitude=77.3649),
    "gurugram_cyber_city": Coordinates(latitude=28.4950, longitude=77.0895),
    "south_delhi_saket": Coordinates(latitude=28.5245, longitude=77.2066),
}

# Synthetic polyline strings representing distinct roads
POLYLINES = {
    "expressway": "_p~iF~ps|U_ulLnnqC_mqNvxq`@_ulLnnqC_mqNvxq`@",
    "ring_road": "m`ziFwus|UemlLonqCamqNvxq`@gmlLonqCcmqNvxq`@",
    "green_corridor": "k_ziFuvs|UamlLpnqCcmqNwxq`@imlLpnqCemqNwxq`@",
}

# Standard 3-route scenario candidates
CANDIDATE_ROUTES_3WAY = [
    RawRouteCandidate(
        route_id="route-1-fast-expressway",
        description="NH-24 Expressway (Fastest, High Traffic & Smog)",
        distance_meters=16500,
        duration_seconds=1200,  # 20 mins
        polyline_encoded=POLYLINES["expressway"],
        warnings=["Heavy industrial traffic reported"],
    ),
    RawRouteCandidate(
        route_id="route-2-balanced-bypass",
        description="Ring Road Bypass (Balanced Trade-off)",
        distance_meters=18200,
        duration_seconds=1440,  # 24 mins
        polyline_encoded=POLYLINES["ring_road"],
        warnings=[],
    ),
    RawRouteCandidate(
        route_id="route-3-clean-parkway",
        description="Green Belt Parkway (Cleanest Air, Longer)",
        distance_meters=21000,
        duration_seconds=1680,  # 28 mins
        polyline_encoded=POLYLINES["green_corridor"],
        warnings=[],
    ),
]

# Synthetic air quality profiles for the 3 routes
AIR_QUALITY_PROFILES_3WAY = {
    "route-1-fast-expressway": AirQualityReading(
        aqi=210,
        category=AQICategory.VERY_UNHEALTHY,
        dominant_pollutant="PM2.5",
        pollutants={"pm25": 160.0, "pm10": 280.0, "no2": 65.0},
        is_valid=True,
        timestamp="2026-10-09T10:00:00Z",
    ),
    "route-2-balanced-bypass": AirQualityReading(
        aqi=115,
        category=AQICategory.UNHEALTHY_SENSITIVE,
        dominant_pollutant="PM2.5",
        pollutants={"pm25": 41.5, "pm10": 95.0, "no2": 32.0},
        is_valid=True,
        timestamp="2026-10-09T10:00:00Z",
    ),
    "route-3-clean-parkway": AirQualityReading(
        aqi=42,
        category=AQICategory.GOOD,
        dominant_pollutant="O3",
        pollutants={"pm25": 10.2, "pm10": 22.0, "no2": 15.0},
        is_valid=True,
        timestamp="2026-10-09T10:00:00Z",
    ),
}

# Single route candidate
CANDIDATE_ROUTE_SINGLE = [
    RawRouteCandidate(
        route_id="route-only-artery",
        description="Sole Arterial Corridor",
        distance_meters=12500,
        duration_seconds=900,  # 15 mins
        polyline_encoded=POLYLINES["ring_road"],
        warnings=[],
    )
]

# High smog tie-break scenario
CANDIDATE_ROUTES_SMOG_TIE = [
    RawRouteCandidate(
        route_id="route-smog-choked",
        description="Direct Freight Route (Extremely Polluted)",
        distance_meters=10000,
        duration_seconds=900,  # 15 mins
        polyline_encoded=POLYLINES["expressway"],
    ),
    RawRouteCandidate(
        route_id="route-clean-suburban",
        description="Suburban Parkway (60s slower, vastly cleaner)",
        distance_meters=10800,
        duration_seconds=960,  # 16 mins (only 6.6% slower)
        polyline_encoded=POLYLINES["green_corridor"],
    ),
]

AIR_QUALITY_PROFILES_SMOG_TIE = {
    "route-smog-choked": AirQualityReading(
        aqi=320,
        category=AQICategory.HAZARDOUS,
        dominant_pollutant="PM2.5",
        pollutants={"pm25": 270.0, "pm10": 420.0},
        is_valid=True,
    ),
    "route-clean-suburban": AirQualityReading(
        aqi=55,
        category=AQICategory.MODERATE,
        dominant_pollutant="PM2.5",
        pollutants={"pm25": 14.0, "pm10": 30.0},
        is_valid=True,
    ),
}

# Missing pollution observations (provider coverage unavailable)
AIR_QUALITY_UNAVAILABLE = AirQualityReading(
    aqi=None,
    category=None,
    dominant_pollutant=None,
    pollutants={},
    is_valid=False,
    timestamp=None,
)
