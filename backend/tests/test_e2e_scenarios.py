from fastapi.testclient import TestClient
from app.main import app
from app.schemas.routing import ExposureStatus, RoutePlanResponse
from app.services.route_optimizer import RouteOptimizerService, get_route_optimizer
from tests.fixtures.mock_datasets import LOCATIONS


def test_e2e_scenario_faster_preference(test_client: TestClient, standard_3way_optimizer: RouteOptimizerService):
    """
    Scenario: User prioritizes travel time over air quality.
    Expected: NH-24 Expressway (1200s) is recommended despite having the worst air quality (AQI 210).
    """
    app.dependency_overrides[get_route_optimizer] = lambda: standard_3way_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "faster",
        "travel_mode": "DRIVE",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    assert validated.recommended_route.route_id == "route-1-fast-expressway"
    assert validated.recommended_route.duration_seconds == 1200
    assert validated.recommended_route.is_recommended is True
    assert len(validated.alternative_routes) == 2
    assert "fastest candidate" in validated.summary or "saving" in validated.summary


def test_e2e_scenario_cleaner_preference(test_client: TestClient, standard_3way_optimizer: RouteOptimizerService):
    """
    Scenario: User prioritizes cleanest air over travel duration.
    Expected: Green Belt Parkway (AQI 42, exposure ~19.6) is recommended despite taking 28 mins (1680s).
    """
    app.dependency_overrides[get_route_optimizer] = lambda: standard_3way_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "cleaner",
        "travel_mode": "DRIVE",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    assert validated.recommended_route.route_id == "route-3-clean-parkway"
    assert validated.recommended_route.average_aqi == 42.0
    assert validated.recommended_route.exposure_status == ExposureStatus.ESTIMATED
    assert "reduces estimated pollution exposure" in validated.summary


def test_e2e_scenario_balanced_preference(test_client: TestClient, standard_3way_optimizer: RouteOptimizerService):
    """
    Scenario: User selects balanced trade-off between time and pollution.
    Expected: Multi-criteria algorithm ranks candidate routes and generates comparative summary.
    """
    app.dependency_overrides[get_route_optimizer] = lambda: standard_3way_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "balanced",
        "travel_mode": "DRIVE",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    assert validated.recommended_route is not None
    assert validated.preference.value == "balanced"
    assert len(validated.alternative_routes) == 2
    assert validated.recommended_route.score is not None
    assert 0.0 <= validated.recommended_route.score <= 1.0


def test_e2e_scenario_smog_tie_break(test_client: TestClient, smog_tie_optimizer: RouteOptimizerService):
    """
    Scenario: Route 1 is 900s with Hazardous AQI 320; Route 2 is 960s (only 60s extra) with Moderate AQI 55.
    Expected: Under balanced mode, the relative trade-off tie-breaker awards the selection to the cleaner route.
    """
    app.dependency_overrides[get_route_optimizer] = lambda: smog_tie_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "balanced",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    assert validated.recommended_route.route_id == "route-clean-suburban"
    assert validated.recommended_route.duration_seconds == 960
    assert validated.recommended_route.average_aqi == 55.0


def test_e2e_scenario_single_route(test_client: TestClient, single_route_optimizer: RouteOptimizerService):
    """
    Scenario: Only one candidate route is returned by provider.
    Expected: Selected with 0 alternatives and a clear summary explaining single-route availability.
    """
    app.dependency_overrides[get_route_optimizer] = lambda: single_route_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "balanced",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    assert validated.recommended_route.route_id == "route-only-artery"
    assert len(validated.alternative_routes) == 0
    assert "Only one candidate route was available" in validated.summary


def test_e2e_scenario_unavailable_air_quality(test_client: TestClient, unavailable_aqi_optimizer: RouteOptimizerService):
    """
    Scenario: Environmental provider has no coverage for route area.
    Expected: No fabricated 0.0; exposure_status is UNAVAILABLE; falls back to travel time ranking with limitation warning.
    """
    app.dependency_overrides[get_route_optimizer] = lambda: unavailable_aqi_optimizer

    payload = {
        "origin": LOCATIONS["delhi_connaught_place"].model_dump(),
        "destination": LOCATIONS["noida_sector_62"].model_dump(),
        "preference": "cleaner",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = RoutePlanResponse(**data)

    # Must NOT claim clean air when data is missing
    assert validated.recommended_route.exposure_status == ExposureStatus.UNAVAILABLE
    assert validated.recommended_route.estimated_exposure_score is None
    # Falls back to shortest travel time
    assert validated.recommended_route.route_id == "route-1-fast-expressway"
    assert len(validated.data_limitations) > 0
    assert "Reliable air quality data was unavailable" in validated.summary


def test_e2e_full_response_contract_types(test_client: TestClient, standard_3way_optimizer: RouteOptimizerService):
    """Verify all response fields match expected types and value bounds."""
    app.dependency_overrides[get_route_optimizer] = lambda: standard_3way_optimizer

    payload = {
        "origin": {"latitude": 28.6315, "longitude": 77.2167},
        "destination": {"latitude": 28.6280, "longitude": 77.3649},
        "preference": "balanced",
    }

    response = test_client.post("/routes/pollution-aware", json=payload)
    assert response.status_code == 200
    data = response.json()

    rec = data["recommended_route"]
    assert isinstance(rec["route_id"], str)
    assert isinstance(rec["distance_meters"], int)
    assert isinstance(rec["duration_seconds"], int)
    assert isinstance(rec["distance_formatted"], str)
    assert isinstance(rec["duration_formatted"], str)
    assert isinstance(rec["estimated_exposure_score"], (float, int))
    assert isinstance(rec["average_aqi"], (float, int))
    assert isinstance(rec["is_recommended"], bool) and rec["is_recommended"] is True
    assert isinstance(data["data_limitations"], list)
    assert isinstance(data["summary"], str)
