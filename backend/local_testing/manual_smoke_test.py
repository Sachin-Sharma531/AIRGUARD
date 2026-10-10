#!/usr/bin/env python3
"""
AIRGUARD — Local Manual Smoke Test Runner

Runs direct in-process end-to-end checks against the FastAPI backend
using TestClient and the deterministic mock scenarios.

Usage:
    python local_testing/manual_smoke_test.py
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.services.route_optimizer import RouteOptimizerService, get_route_optimizer
from tests.conftest import ScenarioAirQualityProvider, ScenarioRoutesProvider
from tests.fixtures.mock_datasets import (
    AIR_QUALITY_PROFILES_3WAY,
    CANDIDATE_ROUTES_3WAY,
    LOCATIONS,
)


def run_checks():
    client = TestClient(app)
    print("\n" + "=" * 60)
    print("  AIRGUARD — Local Smoke Test & Mock Scenario Runner")
    print("=" * 60)

    # 1. Root & Health Check
    res_root = client.get("/")
    assert res_root.status_code == 200, f"Root failed: {res_root.status_code}"
    print(" [PASS] GET / -> HTTP 200 (Service greeting)")

    res_health = client.get("/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.status_code}"
    print(" [PASS] GET /health -> HTTP 200 (Status: healthy)")

    # 2. POST /analyze
    sensor_payload = {
        "pm25": 45.0,
        "pm10": 85.0,
        "no2": 25.0,
        "so2": 12.0,
        "co": 0.9,
        "o3": 35.0,
        "temperature": 27.5,
        "humidity": 55.0,
    }
    res_analyze = client.post("/analyze", json=sensor_payload)
    assert res_analyze.status_code == 200, f"/analyze failed: {res_analyze.status_code}"
    data_analyze = res_analyze.json()
    print(f" [PASS] POST /analyze -> AQI: {data_analyze['aqi']} ({data_analyze['category']})")

    # 3. GET /forecast/stations & /forecast/pm25
    res_stations = client.get("/forecast/stations")
    assert res_stations.status_code == 200, f"/forecast/stations failed: {res_stations.status_code}"
    data_stations = res_stations.json()
    assert data_stations["count"] > 0, "No stations returned"
    print(f" [PASS] GET /forecast/stations -> HTTP 200 ({data_stations['count']} monitoring stations found)")

    res_forecast = client.get("/forecast/pm25", params={"location": "Delhi - DTU"})
    assert res_forecast.status_code == 200, f"/forecast/pm25 failed: {res_forecast.status_code}"
    data_forecast = res_forecast.json()
    assert data_forecast["is_live_forecast"] is False
    print(f" [PASS] GET /forecast/pm25 ('Delhi - DTU') -> Obs: {data_forecast['current_pm25']} µg/m³, Pred (+3h): {data_forecast['predicted_pm25']} µg/m³ (Model: {data_forecast['model']})")


    # 4. Setup mock optimizer for routing tests
    routes_prov = ScenarioRoutesProvider(CANDIDATE_ROUTES_3WAY)
    aqi_prov = ScenarioAirQualityProvider()
    aqi_prov.set_sequence([
        AIR_QUALITY_PROFILES_3WAY["route-1-fast-expressway"],
        AIR_QUALITY_PROFILES_3WAY["route-2-balanced-bypass"],
        AIR_QUALITY_PROFILES_3WAY["route-3-clean-parkway"],
    ])
    mock_service = RouteOptimizerService(routes_prov, aqi_prov)
    app.dependency_overrides[get_route_optimizer] = lambda: mock_service

    try:
        # Faster preference test
        res_faster = client.post("/routes/pollution-aware", json={
            "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
            "destination": LOCATIONS["noida_sector_62"].model_dump(),
            "preference": "faster",
        })
        assert res_faster.status_code == 200
        faster_route = res_faster.json()["recommended_route"]
        print(f" [PASS] POST /routes/pollution-aware ('faster') -> Recommended: {faster_route['route_id']} ({faster_route['duration_formatted']})")

        # Cleaner preference test
        res_cleaner = client.post("/routes/pollution-aware", json={
            "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
            "destination": LOCATIONS["noida_sector_62"].model_dump(),
            "preference": "cleaner",
        })
        assert res_cleaner.status_code == 200
        cleaner_route = res_cleaner.json()["recommended_route"]
        print(f" [PASS] POST /routes/pollution-aware ('cleaner') -> Recommended: {cleaner_route['route_id']} (Avg AQI: {cleaner_route['average_aqi']})")

        # Balanced preference test
        res_balanced = client.post("/routes/pollution-aware", json={
            "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
            "destination": LOCATIONS["noida_sector_62"].model_dump(),
            "preference": "balanced",
        })
        assert res_balanced.status_code == 200
        balanced_route = res_balanced.json()["recommended_route"]
        print(f" [PASS] POST /routes/pollution-aware ('balanced') -> Recommended: {balanced_route['route_id']} (Score: {balanced_route['score']})")

        # Missing pollution data fallback check
        aqi_prov_empty = ScenarioAirQualityProvider(default_reading=AIR_QUALITY_PROFILES_3WAY["route-1-fast-expressway"])
        # Set all readings to invalid
        from tests.fixtures.mock_datasets import AIR_QUALITY_UNAVAILABLE
        mock_unavail_service = RouteOptimizerService(routes_prov, ScenarioAirQualityProvider(default_reading=AIR_QUALITY_UNAVAILABLE))
        app.dependency_overrides[get_route_optimizer] = lambda: mock_unavail_service
        res_unavail = client.post("/routes/pollution-aware", json={
            "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
            "destination": LOCATIONS["noida_sector_62"].model_dump(),
            "preference": "cleaner",
        })
        assert res_unavail.status_code == 200
        unavail_route = res_unavail.json()["recommended_route"]
        assert unavail_route["exposure_status"] == "UNAVAILABLE"
        assert unavail_route["estimated_exposure_score"] is None
        print(" [PASS] POST /routes/pollution-aware (missing air quality) -> Fallback to duration without false clean claim")

        # Upstream service error propagation check
        from fastapi import HTTPException
        class FailingRoutesProvider(ScenarioRoutesProvider):
            async def get_routes(self, *args, **kwargs):
                raise HTTPException(status_code=504, detail="Upstream Google Routes service timed out.")

        mock_failing_service = RouteOptimizerService(FailingRoutesProvider(), aqi_prov)
        app.dependency_overrides[get_route_optimizer] = lambda: mock_failing_service
        res_timeout = client.post("/routes/pollution-aware", json={
            "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
            "destination": LOCATIONS["noida_sector_62"].model_dump(),
        })
        assert res_timeout.status_code == 504
        print(" [PASS] POST /routes/pollution-aware (upstream timeout) -> Clean HTTP 504 Gateway Timeout")

        # Validation check - Out of range
        res_invalid = client.post("/routes/pollution-aware", json={
            "origin": {"latitude": 99.0, "longitude": 77.0},
            "destination": {"latitude": 28.0, "longitude": 77.0},
        })
        assert res_invalid.status_code == 422
        print(" [PASS] POST /routes/pollution-aware (latitude > 90) -> Rejected HTTP 422")

        # Validation check - Identical origin and destination
        res_identical = client.post("/routes/pollution-aware", json={
            "origin": {"latitude": 28.5, "longitude": 77.0},
            "destination": {"latitude": 28.5, "longitude": 77.0},
        })
        assert res_identical.status_code == 422
        print(" [PASS] POST /routes/pollution-aware (identical origin/dest) -> Rejected HTTP 422")

    finally:
        app.dependency_overrides.clear()

    print("=" * 60)
    print("  All local smoke checks passed successfully!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_checks()

