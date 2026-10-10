import json
from pathlib import Path
from app.schemas.analyze import AQICategory
from app.schemas.routing import Coordinates, RoutePlanRequest
from app.services.google_air_quality import AirQualityReading
from app.services.google_routes import RawRouteCandidate
from tests.fixtures.mock_datasets import (
    AIR_QUALITY_PROFILES_3WAY,
    AIR_QUALITY_PROFILES_SMOG_TIE,
    AIR_QUALITY_UNAVAILABLE,
    CANDIDATE_ROUTE_SINGLE,
    CANDIDATE_ROUTES_3WAY,
    CANDIDATE_ROUTES_SMOG_TIE,
    LOCATIONS,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_mock_datasets_python_structures():
    """Verify that all in-memory mock datasets conform strictly to schema classes."""
    for name, loc in LOCATIONS.items():
        assert isinstance(loc, Coordinates)
        assert -90.0 <= loc.latitude <= 90.0
        assert -180.0 <= loc.longitude <= 180.0

    for candidate in CANDIDATE_ROUTES_3WAY + CANDIDATE_ROUTES_SMOG_TIE + CANDIDATE_ROUTE_SINGLE:
        assert isinstance(candidate, RawRouteCandidate)
        assert candidate.duration_seconds > 0
        assert candidate.distance_meters > 0
        assert candidate.route_id != ""

    for route_id, reading in {**AIR_QUALITY_PROFILES_3WAY, **AIR_QUALITY_PROFILES_SMOG_TIE}.items():
        assert isinstance(reading, AirQualityReading)
        assert reading.is_valid is True
        assert reading.aqi is not None and reading.aqi >= 0
        assert reading.category in list(AQICategory)

    assert AIR_QUALITY_UNAVAILABLE.is_valid is False
    assert AIR_QUALITY_UNAVAILABLE.aqi is None


def test_mock_routes_json_fixture():
    """Verify that mock_routes.json loads and matches expected structure."""
    json_path = FIXTURES_DIR / "mock_routes.json"
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("scenarios", {})
    assert "standard_3way" in scenarios
    std = scenarios["standard_3way"]
    req = RoutePlanRequest(
        origin=Coordinates(**std["origin"]),
        destination=Coordinates(**std["destination"]),
    )
    assert req.origin.latitude == 28.6315
    assert len(std["candidates"]) == 3


def test_mock_air_quality_json_fixture():
    """Verify that mock_air_quality.json loads and can be parsed into AirQualityReading objects."""
    json_path = FIXTURES_DIR / "mock_air_quality.json"
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    readings = data.get("synthetic_readings", {})
    assert "clean_air" in readings
    clean = AirQualityReading(**readings["clean_air"])
    assert clean.aqi == 42
    assert clean.category == AQICategory.GOOD
    assert clean.is_valid is True

    unavail = AirQualityReading(**readings["unavailable"])
    assert unavail.is_valid is False
    assert unavail.aqi is None
