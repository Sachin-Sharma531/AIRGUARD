import pytest
from app.config import Settings
from app.schemas.analyze import AQICategory
from app.schemas.routing import RoutePreference
from app.services.google_air_quality import GoogleAirQualityClient
from app.services.google_routes import GoogleRoutesClient
from app.services.polyline import (
    decode_polyline,
    haversine_distance,
    sample_polyline_coordinates,
)
from app.services.route_optimizer import (
    RouteOptimizerService,
    format_distance,
    format_duration,
    map_aqi_to_category,
)


# ---------------------------------------------------------
# Polyline Service Unit Tests
# ---------------------------------------------------------

def test_haversine_distance_zero():
    """Distance between identical coordinates is 0.0 meters."""
    assert haversine_distance(28.5, 77.2, 28.5, 77.2) == 0.0


def test_decode_polyline_empty():
    """Empty polyline string returns empty list."""
    assert decode_polyline("") == []


def test_sample_polyline_edge_cases():
    """Sampling handles empty, single-element, and small lists."""
    assert sample_polyline_coordinates([]) == []

    single = [(28.5, 77.2)]
    assert sample_polyline_coordinates(single, max_samples=5) == single

    two_points = [(28.5, 77.2), (28.6, 77.3)]
    sampled_two = sample_polyline_coordinates(two_points, max_samples=2)
    assert len(sampled_two) == 2
    assert sampled_two == two_points

    # 1 max_sample
    assert sample_polyline_coordinates(two_points, max_samples=1) == [(28.5, 77.2)]

    # 0 and negative max_samples return empty list
    assert sample_polyline_coordinates(two_points, max_samples=0) == []
    assert sample_polyline_coordinates(two_points, max_samples=-1) == []


# ---------------------------------------------------------
# Google Routes Unit Tests
# ---------------------------------------------------------

def test_parse_duration_seconds():
    """Validates string duration parser used by Google Routes client."""
    assert GoogleRoutesClient._parse_duration_seconds("1200s") == 1200
    assert GoogleRoutesClient._parse_duration_seconds("45.8s") == 45
    assert GoogleRoutesClient._parse_duration_seconds(None) == 0
    assert GoogleRoutesClient._parse_duration_seconds("") == 0
    assert GoogleRoutesClient._parse_duration_seconds("invalid") == 0


# ---------------------------------------------------------
# Google Air Quality Unit Tests
# ---------------------------------------------------------

def test_map_category_strings_and_numbers():
    """Validates EPA and qualitative category mapper in air quality client."""
    assert GoogleAirQualityClient._map_category("Good", None) == AQICategory.GOOD
    assert GoogleAirQualityClient._map_category("Moderate", None) == AQICategory.MODERATE
    assert GoogleAirQualityClient._map_category("Unhealthy for Sensitive Groups", None) == AQICategory.UNHEALTHY_SENSITIVE
    assert GoogleAirQualityClient._map_category("Unhealthy", None) == AQICategory.UNHEALTHY
    assert GoogleAirQualityClient._map_category("Very Unhealthy", None) == AQICategory.VERY_UNHEALTHY
    assert GoogleAirQualityClient._map_category("Hazardous", None) == AQICategory.HAZARDOUS

    # Fallback by numeric AQI when category string is empty
    assert GoogleAirQualityClient._map_category(None, 25) == AQICategory.GOOD
    assert GoogleAirQualityClient._map_category(None, 75) == AQICategory.MODERATE
    assert GoogleAirQualityClient._map_category(None, 125) == AQICategory.UNHEALTHY_SENSITIVE
    assert GoogleAirQualityClient._map_category(None, 175) == AQICategory.UNHEALTHY
    assert GoogleAirQualityClient._map_category(None, 250) == AQICategory.VERY_UNHEALTHY
    assert GoogleAirQualityClient._map_category(None, 350) == AQICategory.HAZARDOUS
    assert GoogleAirQualityClient._map_category(None, None) is None


@pytest.mark.anyio
async def test_air_quality_cache_deduplication():
    """Verify that querying the exact same or near coordinates uses the in-memory cache and respects TTL."""
    import time
    client = GoogleAirQualityClient(settings=Settings(GOOGLE_MAPS_API_KEY=None))

    # Pre-populate cache for testing with valid expiration
    cache_key = (round(28.6139, 3), round(77.2090, 3))
    from app.services.google_air_quality import AirQualityReading
    cached_reading = AirQualityReading(aqi=88, is_valid=True)
    client._cache[cache_key] = (cached_reading, time.monotonic() + 3600)

    # Query with identical coordinates
    result = await client.get_air_quality(28.6139, 77.2090)
    assert result.aqi == 88

    # Query with coordinates within the ~110m 3-decimal threshold
    result_near = await client.get_air_quality(28.61394, 77.20902)
    assert result_near.aqi == 88

    # Test expired entry eviction
    expired_key = (round(28.7, 3), round(77.1, 3))
    client._cache[expired_key] = (AirQualityReading(aqi=99, is_valid=True), time.monotonic() - 10)
    # With expired entry and no API key, entry should be deleted and invalid reading returned
    result_expired = await client.get_air_quality(28.7, 77.1)
    assert result_expired.is_valid is False
    assert expired_key not in client._cache


# ---------------------------------------------------------
# Route Optimizer Unit Tests
# ---------------------------------------------------------

def test_formatting_utilities():
    """Validates human-readable formatting functions."""
    assert format_duration(45) == "45s"
    assert format_duration(60) == "1 min"
    assert format_duration(120) == "2 mins"
    assert format_duration(3600) == "1 hr"
    assert format_duration(7200) == "2 hrs"
    assert format_duration(5400) == "1h 30m"

    assert format_distance(450) == "450 m"
    assert format_distance(1000) == "1.0 km"
    assert format_distance(15400) == "15.4 km"


def test_map_aqi_to_category_helper():
    """Validates standard AQI breakpoint to category mapping."""
    assert map_aqi_to_category(None) is None
    assert map_aqi_to_category(35.0) == AQICategory.GOOD
    assert map_aqi_to_category(80.0) == AQICategory.MODERATE
    assert map_aqi_to_category(130.0) == AQICategory.UNHEALTHY_SENSITIVE
    assert map_aqi_to_category(180.0) == AQICategory.UNHEALTHY
    assert map_aqi_to_category(250.0) == AQICategory.VERY_UNHEALTHY
    assert map_aqi_to_category(400.0) == AQICategory.HAZARDOUS


def test_preference_weights_retrieval():
    """Verify that optimizer retrieves correct weights for each preference."""
    service = RouteOptimizerService()

    w_time, w_poll = service._get_preference_weights(RoutePreference.FASTER)
    assert w_time > w_poll

    w_time, w_poll = service._get_preference_weights(RoutePreference.CLEANER)
    assert w_poll > w_time

    w_time, w_poll = service._get_preference_weights(RoutePreference.BALANCED)
    assert abs(w_time - w_poll) < 0.1


@pytest.mark.anyio
async def test_air_quality_batch_empty_and_concurrent():
    """Verify get_air_quality_batch handles empty list and concurrent lookups."""
    client = GoogleAirQualityClient(settings=Settings(GOOGLE_MAPS_API_KEY=None))

    # Empty locations returns empty list
    empty_res = await client.get_air_quality_batch([])
    assert empty_res == []

    # Missing API key batch execution returns invalid readings and logs warning once
    res = await client.get_air_quality_batch([(28.5, 77.2), (28.6, 77.3)])
    assert len(res) == 2
    assert res[0].is_valid is False
    assert res[1].is_valid is False
    assert client._logged_missing_key is True



@pytest.mark.anyio
async def test_google_routes_walk_request_omits_routing_preference():
    """Google Routes rejects routingPreference for WALK/BICYCLE; verify the request is validly shaped."""
    request_capture = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": [{"duration": "600s", "distanceMeters": 1200, "polyline": {"encodedPolyline": ""}}]}

    class FakeClient:
        async def post(self, url, *, json, headers, timeout):
            request_capture.update(json)
            return FakeResponse()

    client = GoogleRoutesClient(settings=Settings(GOOGLE_MAPS_API_KEY="test-key"), client=FakeClient())
    routes = await client.get_routes(28.75, 77.11, 28.73, 77.08, travel_mode="WALK")
    assert len(routes) == 1
    assert request_capture["travelMode"] == "WALK"
    assert "routingPreference" not in request_capture


@pytest.mark.anyio
async def test_google_routes_drive_request_uses_traffic_aware_preference():
    request_capture = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": [{"duration": "600s", "distanceMeters": 1200, "polyline": {"encodedPolyline": ""}}]}

    class FakeClient:
        async def post(self, url, *, json, headers, timeout):
            request_capture.update(json)
            return FakeResponse()

    client = GoogleRoutesClient(settings=Settings(GOOGLE_MAPS_API_KEY="test-key"), client=FakeClient())
    routes = await client.get_routes(28.75, 77.11, 28.73, 77.08, travel_mode="DRIVE")
    assert len(routes) == 1
    assert request_capture["travelMode"] == "DRIVE"
    assert request_capture["routingPreference"] == "TRAFFIC_AWARE"
