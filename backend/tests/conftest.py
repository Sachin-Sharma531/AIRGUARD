from typing import Dict, List, Optional
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.google_air_quality import AirQualityReading, BaseAirQualityProvider
from app.services.google_routes import BaseRoutesProvider, RawRouteCandidate
from app.services.route_optimizer import RouteOptimizerService
from tests.fixtures.mock_datasets import (
    AIR_QUALITY_PROFILES_3WAY,
    AIR_QUALITY_PROFILES_SMOG_TIE,
    AIR_QUALITY_UNAVAILABLE,
    CANDIDATE_ROUTE_SINGLE,
    CANDIDATE_ROUTES_3WAY,
    CANDIDATE_ROUTES_SMOG_TIE,
)



class ScenarioRoutesProvider(BaseRoutesProvider):
    """Configurable mock routes provider for pytest tests."""

    def __init__(self, candidates: Optional[List[RawRouteCandidate]] = None):
        self.candidates = candidates or []
        self.call_count = 0
        self.last_query = {}

    async def get_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        compute_alternatives: bool = True,
    ) -> List[RawRouteCandidate]:
        self.call_count += 1
        self.last_query = {
            "origin": (origin_lat, origin_lng),
            "dest": (dest_lat, dest_lng),
            "travel_mode": travel_mode,
            "alternatives": compute_alternatives,
        }
        return self.candidates


class ScenarioAirQualityProvider(BaseAirQualityProvider):
    """Configurable mock air quality provider returning sequential or mapped readings."""

    def __init__(
        self,
        readings_map: Optional[Dict[str, AirQualityReading]] = None,
        default_reading: Optional[AirQualityReading] = None,
    ):
        self.readings_map = readings_map or {}
        self.default_reading = default_reading or AirQualityReading(aqi=50, is_valid=True)
        self.batch_call_count = 0
        self.readings_list: List[AirQualityReading] = []

    def set_sequence(self, readings: List[AirQualityReading]):
        self.readings_list = readings
        self.batch_call_count = 0

    async def get_air_quality(self, lat: float, lng: float) -> AirQualityReading:
        return self.default_reading

    async def get_air_quality_batch(self, locations):
        idx = self.batch_call_count
        self.batch_call_count += 1
        if self.readings_list:
            reading = self.readings_list[idx % len(self.readings_list)]
            return [reading for _ in locations]
        return [self.default_reading for _ in locations]


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure any FastAPI dependency overrides are cleanly reset after every test."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def test_client() -> TestClient:
    """Returns a fresh FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def standard_3way_optimizer() -> RouteOptimizerService:
    """Optimizer wired to the standard 3-way route candidates and distinct AQI profiles."""
    routes_prov = ScenarioRoutesProvider(CANDIDATE_ROUTES_3WAY)
    aqi_prov = ScenarioAirQualityProvider()

    # Sequence matches the 3 route candidates: fast/dirty, balanced, clean
    readings = [
        AIR_QUALITY_PROFILES_3WAY["route-1-fast-expressway"],
        AIR_QUALITY_PROFILES_3WAY["route-2-balanced-bypass"],
        AIR_QUALITY_PROFILES_3WAY["route-3-clean-parkway"],
    ]
    aqi_prov.set_sequence(readings)

    return RouteOptimizerService(
        routes_provider=routes_prov,
        air_quality_provider=aqi_prov,
    )


@pytest.fixture
def single_route_optimizer() -> RouteOptimizerService:
    """Optimizer wired to a single candidate route."""
    routes_prov = ScenarioRoutesProvider(CANDIDATE_ROUTE_SINGLE)
    aqi_prov = ScenarioAirQualityProvider(
        default_reading=AIR_QUALITY_PROFILES_3WAY["route-2-balanced-bypass"]
    )
    return RouteOptimizerService(
        routes_provider=routes_prov,
        air_quality_provider=aqi_prov,
    )


@pytest.fixture
def smog_tie_optimizer() -> RouteOptimizerService:
    """Optimizer wired to the smog alert tie-break scenario."""
    routes_prov = ScenarioRoutesProvider(CANDIDATE_ROUTES_SMOG_TIE)
    aqi_prov = ScenarioAirQualityProvider()
    aqi_prov.set_sequence([
        AIR_QUALITY_PROFILES_SMOG_TIE["route-smog-choked"],
        AIR_QUALITY_PROFILES_SMOG_TIE["route-clean-suburban"],
    ])
    return RouteOptimizerService(
        routes_provider=routes_prov,
        air_quality_provider=aqi_prov,
    )


@pytest.fixture
def unavailable_aqi_optimizer() -> RouteOptimizerService:
    """Optimizer where environmental coverage is completely unavailable."""
    routes_prov = ScenarioRoutesProvider(CANDIDATE_ROUTES_3WAY)
    aqi_prov = ScenarioAirQualityProvider(default_reading=AIR_QUALITY_UNAVAILABLE)
    return RouteOptimizerService(
        routes_provider=routes_prov,
        air_quality_provider=aqi_prov,
    )
