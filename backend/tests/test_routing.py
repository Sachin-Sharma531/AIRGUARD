import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from pydantic import ValidationError
import httpx

from app.main import app
from app.config import Settings
from app.schemas.analyze import AQICategory
from app.schemas.routing import (
    Coordinates,
    ExposureStatus,
    RoutePlanRequest,
    RoutePreference,
)
from app.services.google_air_quality import AirQualityReading, BaseAirQualityProvider
from app.services.google_routes import BaseRoutesProvider, GoogleRoutesClient, RawRouteCandidate
from app.services.polyline import decode_polyline, haversine_distance, sample_polyline_coordinates
from app.services.route_optimizer import RouteOptimizerService, get_route_optimizer

client = TestClient(app)


# ---------------------------------------------------------
# Test Mocks
# ---------------------------------------------------------

class MockRoutesProvider(BaseRoutesProvider):
    def __init__(self, candidates=None):
        self.candidates = candidates or []

    async def get_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        compute_alternatives: bool = True,
    ):
        return self.candidates


class MockAirQualityProvider(BaseAirQualityProvider):
    def __init__(self, readings_by_coord=None, default_reading=None):
        self.readings_by_coord = readings_by_coord or {}
        self.default_reading = default_reading or AirQualityReading(
            aqi=50,
            category=AQICategory.GOOD,
            dominant_pollutant="PM2.5",
            pollutants={"pm25": 12.0, "pm10": 25.0},
            is_valid=True,
        )

    async def get_air_quality(self, lat: float, lng: float):
        key = (round(lat, 3), round(lng, 3))
        return self.readings_by_coord.get(key, self.default_reading)


# ---------------------------------------------------------
# Unit Tests: Polyline & Sampling
# ---------------------------------------------------------

def test_haversine_distance():
    # Distance between New Delhi (28.6139, 77.2090) and Noida (28.5355, 77.3910) is ~19-20 km
    dist = haversine_distance(28.6139, 77.2090, 28.5355, 77.3910)
    assert 18000 < dist < 22000


def test_polyline_decoder_and_sampler():
    # Sample polyline: (38.5, -120.2), (40.7, -120.95), (43.252, -126.453)
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    coords = decode_polyline(encoded)
    assert len(coords) >= 3
    assert abs(coords[0][0] - 38.5) < 0.01
    assert abs(coords[0][1] - (-120.2)) < 0.01

    # Test sampling
    sampled = sample_polyline_coordinates(coords, max_samples=2)
    assert len(sampled) == 2
    assert sampled[0] == coords[0]
    assert sampled[-1] == coords[-1]


# ---------------------------------------------------------
# Unit Tests: Pydantic Validation
# ---------------------------------------------------------

def test_route_plan_request_valid():
    req = RoutePlanRequest(
        origin=Coordinates(latitude=28.6139, longitude=77.2090),
        destination=Coordinates(latitude=28.5355, longitude=77.3910),
        preference=RoutePreference.BALANCED,
    )
    assert req.preference == RoutePreference.BALANCED
    assert req.travel_mode.value == "DRIVE"
    assert req.compute_alternatives is True


def test_route_plan_request_rejects_out_of_bounds_coordinates():
    with pytest.raises(ValidationError):
        RoutePlanRequest(
            origin=Coordinates(latitude=95.0, longitude=77.0),
            destination=Coordinates(latitude=28.0, longitude=77.0),
        )

    with pytest.raises(ValidationError):
        RoutePlanRequest(
            origin=Coordinates(latitude=28.0, longitude=-190.0),
            destination=Coordinates(latitude=28.0, longitude=77.0),
        )


def test_route_plan_request_rejects_identical_coordinates():
    with pytest.raises(ValidationError):
        RoutePlanRequest(
            origin=Coordinates(latitude=28.6139, longitude=77.2090),
            destination=Coordinates(latitude=28.6139, longitude=77.2090),
        )


def test_cors_origins_parsing():
    s1 = Settings(CORS_ORIGINS='["http://example.com", "http://test.com"]')
    assert s1.CORS_ORIGINS == ["http://example.com", "http://test.com"]

    s2 = Settings(CORS_ORIGINS="http://example.com, http://test.com")
    assert s2.CORS_ORIGINS == ["http://example.com", "http://test.com"]


# ---------------------------------------------------------
# Unit Tests: Route Scoring & Preferences
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_cleaner_preference_favors_lower_exposure():
    # Route 1: 15 minutes (900s), but extremely polluted (AQI 200, exp = 50.0)
    # Route 2: 18 minutes (1080s), but clean (AQI 40, exp = 12.0)
    candidates = [
        RawRouteCandidate(
            route_id="route-1-fast-dirty",
            description="Highway Express",
            distance_meters=12000,
            duration_seconds=900,
        ),
        RawRouteCandidate(
            route_id="route-2-slow-clean",
            description="Parkway Bypass",
            distance_meters=14000,
            duration_seconds=1080,
        ),
    ]

    class SequenceAQIProvider(MockAirQualityProvider):
        def __init__(self):
            super().__init__()
            self.count = 0
            self.readings = [
                AirQualityReading(aqi=200, category=AQICategory.UNHEALTHY, is_valid=True),
                AirQualityReading(aqi=40, category=AQICategory.GOOD, is_valid=True),
            ]

        async def get_air_quality_batch(self, locations):
            res = [self.readings[self.count % 2]]
            self.count += 1
            return res

    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(candidates),
        air_quality_provider=SequenceAQIProvider(),
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
        preference=RoutePreference.CLEANER,
    )

    response = await service.plan_route(request)

    # Under cleaner preference, route-2 should be recommended
    assert response.recommended_route.route_id == "route-2-slow-clean"
    assert response.recommended_route.is_recommended is True
    assert "reduces estimated pollution exposure" in response.summary


@pytest.mark.anyio
async def test_faster_preference_favors_travel_time():
    candidates = [
        RawRouteCandidate(
            route_id="route-1-fast-dirty",
            description="Highway Express",
            distance_meters=12000,
            duration_seconds=900,
        ),
        RawRouteCandidate(
            route_id="route-2-slow-clean",
            description="Parkway Bypass",
            distance_meters=14000,
            duration_seconds=1080,
        ),
    ]

    class SequenceAQIProvider(MockAirQualityProvider):
        def __init__(self):
            super().__init__()
            self.count = 0
            self.readings = [
                AirQualityReading(aqi=200, category=AQICategory.UNHEALTHY, is_valid=True),
                AirQualityReading(aqi=40, category=AQICategory.GOOD, is_valid=True),
            ]

        async def get_air_quality_batch(self, locations):
            res = [self.readings[self.count % 2]]
            self.count += 1
            return res

    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(candidates),
        air_quality_provider=SequenceAQIProvider(),
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
        preference=RoutePreference.FASTER,
    )

    response = await service.plan_route(request)

    # Under faster preference, route-1 should be recommended despite higher AQI
    assert response.recommended_route.route_id == "route-1-fast-dirty"
    assert response.recommended_route.is_recommended is True


@pytest.mark.anyio
async def test_balanced_preference_evaluates_tradeoff():
    # Route 1: 15 minutes (900s), AQI 250 (hazardous)
    # Route 2: 16 minutes (960s), AQI 40 (good)
    # Balanced should clearly prefer 1 extra minute for vastly cleaner air
    candidates = [
        RawRouteCandidate(
            route_id="route-1-extreme-pollution",
            description="Smog Alley",
            distance_meters=10000,
            duration_seconds=900,
        ),
        RawRouteCandidate(
            route_id="route-2-clean-slightly-slower",
            description="Clean Parkway",
            distance_meters=11000,
            duration_seconds=960,
        ),
    ]

    class SequenceAQIProvider(MockAirQualityProvider):
        def __init__(self):
            super().__init__()
            self.count = 0
            self.readings = [
                AirQualityReading(aqi=250, category=AQICategory.VERY_UNHEALTHY, is_valid=True),
                AirQualityReading(aqi=40, category=AQICategory.GOOD, is_valid=True),
            ]

        async def get_air_quality_batch(self, locations):
            res = [self.readings[self.count % 2]]
            self.count += 1
            return res

    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(candidates),
        air_quality_provider=SequenceAQIProvider(),
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
        preference=RoutePreference.BALANCED,
    )

    response = await service.plan_route(request)
    assert response.recommended_route.route_id == "route-2-clean-slightly-slower"


@pytest.mark.anyio
async def test_single_route_scenario():
    single_candidate = [
        RawRouteCandidate(
            route_id="route-only",
            description="Only Road",
            distance_meters=8000,
            duration_seconds=600,
        )
    ]

    aqi_provider = MockAirQualityProvider()
    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(single_candidate),
        air_quality_provider=aqi_provider,
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
        preference=RoutePreference.BALANCED,
    )

    response = await service.plan_route(request)
    assert response.recommended_route.route_id == "route-only"
    assert len(response.alternative_routes) == 0
    assert "Only one candidate route was available" in response.summary


@pytest.mark.anyio
async def test_missing_pollution_data_does_not_claim_clean_route():
    candidates = [
        RawRouteCandidate(
            route_id="route-1",
            description="Route 1",
            distance_meters=10000,
            duration_seconds=800,
        ),
        RawRouteCandidate(
            route_id="route-2",
            description="Route 2",
            distance_meters=12000,
            duration_seconds=1000,
        ),
    ]

    # Air quality provider returns invalid readings (no coverage)
    aqi_provider = MockAirQualityProvider(
        default_reading=AirQualityReading(is_valid=False, aqi=None)
    )

    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(candidates),
        air_quality_provider=aqi_provider,
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
        preference=RoutePreference.CLEANER,
    )

    response = await service.plan_route(request)
    # Must NOT fabricate 0 or claim it is a clean route
    assert response.recommended_route.exposure_status == ExposureStatus.UNAVAILABLE
    assert response.recommended_route.estimated_exposure_score is None
    # Falls back to duration ranking
    assert response.recommended_route.route_id == "route-1"
    assert "Reliable air quality data was unavailable" in response.summary
    assert len(response.data_limitations) > 0


@pytest.mark.anyio
async def test_no_routes_found_raises_404():
    service = RouteOptimizerService(
        routes_provider=MockRoutesProvider([]),
        air_quality_provider=MockAirQualityProvider(),
    )

    request = RoutePlanRequest(
        origin=Coordinates(latitude=28.6, longitude=77.2),
        destination=Coordinates(latitude=28.5, longitude=77.3),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.plan_route(request)
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_google_routes_client_missing_key_raises_503():
    test_settings = Settings(GOOGLE_MAPS_API_KEY=None, GOOGLE_ROUTES_API_KEY=None)
    client_instance = GoogleRoutesClient(settings=test_settings)

    with pytest.raises(HTTPException) as exc_info:
        await client_instance.get_routes(
            origin_lat=28.6, origin_lng=77.2, dest_lat=28.5, dest_lng=77.3
        )
    assert exc_info.value.status_code == 503
    assert "Google Routes API key is not configured" in exc_info.value.detail


@pytest.mark.anyio
async def test_google_routes_client_timeout_raises_504():
    test_settings = Settings(GOOGLE_MAPS_API_KEY="dummy-key")

    # Mock an httpx client that times out
    async def timeout_post(*args, **kwargs):
        raise httpx.TimeoutException("Connection timed out")

    mock_http = httpx.AsyncClient()
    mock_http.post = timeout_post

    client_instance = GoogleRoutesClient(settings=test_settings, client=mock_http)

    with pytest.raises(HTTPException) as exc_info:
        await client_instance.get_routes(
            origin_lat=28.6, origin_lng=77.2, dest_lat=28.5, dest_lng=77.3
        )
    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail


@pytest.mark.anyio
async def test_google_routes_client_upstream_error_raises_502():
    test_settings = Settings(GOOGLE_MAPS_API_KEY="dummy-key")

    # Mock an httpx client that returns upstream error
    request = httpx.Request("POST", "https://routes.googleapis.com")
    response = httpx.Response(500, request=request, text="Internal Google Error")

    async def error_post(*args, **kwargs):
        raise httpx.HTTPStatusError("Upstream failure", request=request, response=response)

    mock_http = httpx.AsyncClient()
    mock_http.post = error_post

    client_instance = GoogleRoutesClient(settings=test_settings, client=mock_http)

    with pytest.raises(HTTPException) as exc_info:
        await client_instance.get_routes(
            origin_lat=28.6, origin_lng=77.2, dest_lat=28.5, dest_lng=77.3
        )
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------
# Integration Tests: FastAPI HTTP Endpoints
# ---------------------------------------------------------

def test_api_routes_endpoint_validation_error():
    # Out of range coordinates -> 422
    payload = {
        "origin": {"latitude": 99.0, "longitude": 77.0},
        "destination": {"latitude": 28.0, "longitude": 77.0},
    }
    response = client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 422


def test_api_routes_endpoint_identical_coords_error():
    # Same origin and destination -> 422
    payload = {
        "origin": {"latitude": 28.5, "longitude": 77.0},
        "destination": {"latitude": 28.5, "longitude": 77.0},
    }
    response = client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 422


def test_api_routes_endpoint_e2e_with_dependency_override():
    candidates = [
        RawRouteCandidate(
            route_id="route-1",
            description="Main Expressway",
            distance_meters=15000,
            duration_seconds=1200,
            polyline_encoded="_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        ),
        RawRouteCandidate(
            route_id="route-2",
            description="Green Belt Road",
            distance_meters=16500,
            duration_seconds=1350,
            polyline_encoded="_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        ),
    ]

    mock_service = RouteOptimizerService(
        routes_provider=MockRoutesProvider(candidates),
        air_quality_provider=MockAirQualityProvider(),
    )

    app.dependency_overrides[get_route_optimizer] = lambda: mock_service

    try:
        payload = {
            "origin": {"latitude": 28.6139, "longitude": 77.2090},
            "destination": {"latitude": 28.5355, "longitude": 77.3910},
            "preference": "balanced",
            "travel_mode": "DRIVE",
        }

        # Test primary endpoint
        resp = client.post("/routes/pollution-aware", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_route" in data
        assert data["recommended_route"]["is_recommended"] is True
        assert "alternative_routes" in data
        assert "preference" in data
        assert "summary" in data

        # Test aliases for backward compatibility
        resp_alias1 = client.post("/routes", json=payload)
        assert resp_alias1.status_code == 200
        resp_alias2 = client.post("/routes/plan", json=payload)
        assert resp_alias2.status_code == 200
    finally:
        app.dependency_overrides.clear()
