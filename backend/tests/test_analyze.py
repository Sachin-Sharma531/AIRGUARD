from fastapi.testclient import TestClient
from app.main import app
from app.ml.inference import BasePredictor, get_predictor
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, AQICategory

client = TestClient(app)


def test_analyze_success_with_valid_data():
    """Verify that a valid POST request to /analyze returns 200 and expected response structure."""
    payload = {
        "pm25": 45.0,
        "pm10": 85.0,
        "no2": 20.0,
        "so2": 10.0,
        "co": 0.8,
        "o3": 30.0,
        "temperature": 25.0,
        "humidity": 60.0
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["aqi"], int)
    assert data["category"] in [c.value for c in AQICategory]
    assert data["dominant_pollutant"] in ["PM2.5", "PM10"]
    assert isinstance(data["health_advisory"], str)
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0
    assert data["is_mock"] is True


def test_analyze_missing_required_pollutants_returns_422():
    """Verify that omitting required pollutant fields produces an HTTP 422 Unprocessable Entity."""
    # Omit pm25
    payload = {"pm10": 80.0}
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422

    # Omit pm10
    payload = {"pm25": 40.0}
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422


def test_analyze_out_of_bounds_input_returns_422():
    """Verify that negative or extreme values fail Pydantic validation with HTTP 422."""
    # Negative PM2.5
    response = client.post("/analyze", json={"pm25": -15.0, "pm10": 50.0})
    assert response.status_code == 422

    # Excessive humidity (> 100)
    response = client.post("/analyze", json={"pm25": 20.0, "pm10": 40.0, "humidity": 120.0})
    assert response.status_code == 422


def test_analyze_custom_predictor_dependency_injection():
    """Verify that FastAPI dependency injection allows swapping predictors seamlessly."""
    class DummyPredictor(BasePredictor):
        def predict(self, data: AnalyzeRequest) -> AnalyzeResponse:
            return AnalyzeResponse(
                aqi=42,
                category=AQICategory.GOOD,
                dominant_pollutant="PM2.5",
                health_advisory="Special test advisory",
                recommendations=["Breathe freely"],
                is_mock=False
            )

    app.dependency_overrides[get_predictor] = lambda: DummyPredictor()

    try:
        response = client.post("/analyze", json={"pm25": 10.0, "pm10": 20.0})
        assert response.status_code == 200
        data = response.json()
        assert data["aqi"] == 42
        assert data["health_advisory"] == "Special test advisory"
        assert data["is_mock"] is False
    finally:
        app.dependency_overrides.clear()


def test_analyze_internal_error_returns_500():
    """Verify that unexpected predictor failures return a clean HTTP 500 without leaking stack traces."""
    class FailingPredictor(BasePredictor):
        def predict(self, data: AnalyzeRequest) -> AnalyzeResponse:
            raise RuntimeError("Unexpected model failure")

    app.dependency_overrides[get_predictor] = lambda: FailingPredictor()

    try:
        response = client.post("/analyze", json={"pm25": 10.0, "pm10": 20.0})
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "An error occurred while analyzing the air quality metrics."
    finally:
        app.dependency_overrides.clear()
