from unittest.mock import patch
from fastapi.testclient import TestClient


def test_forecast_stations_success(test_client: TestClient):
    """Test that the stations endpoint returns available stations from the historical dataset."""
    response = test_client.get("/forecast/stations")
    assert response.status_code == 200
    data = response.json()
    assert "stations" in data
    assert "count" in data
    assert isinstance(data["stations"], list)
    assert data["count"] == len(data["stations"])
    assert data["count"] > 0
    assert "Delhi - DTU" in data["stations"]


def test_forecast_pm25_success(test_client: TestClient):
    """Test successful 3-hour PM2.5 prediction for Delhi - DTU."""
    response = test_client.get("/forecast/pm25", params={"location": "Delhi - DTU"})
    assert response.status_code == 200
    data = response.json()

    assert data["location"] == "Delhi - DTU"
    assert "current_pm25" in data
    assert isinstance(data["current_pm25"], (int, float))
    assert data["current_pm25"] >= 0

    assert "predicted_pm25" in data
    assert isinstance(data["predicted_pm25"], (int, float))
    assert data["predicted_pm25"] >= 0

    assert data["horizon_minutes"] == 180
    assert data["model"] == "random_forest"
    assert data["data_source"] == "historical_dataset"
    assert data["is_live_forecast"] is False
    assert "observation_time" in data
    assert "prediction_time" in data
    assert "dataset_latest_observation" in data


def test_forecast_pm25_unknown_location(test_client: TestClient):
    """Test error handling when requesting an unknown monitoring station."""
    response = test_client.get("/forecast/pm25", params={"location": "NonExistent_Station_XYZ"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "Insufficient historical observations" in data["detail"]


def test_forecast_pm25_missing_param(test_client: TestClient):
    """Test validation error when location query parameter is omitted."""
    response = test_client.get("/forecast/pm25")
    assert response.status_code == 422


def test_forecast_missing_model_artifact(test_client: TestClient):
    """Test 500 error when model artifact file is missing."""
    with patch("app.ml.forecast_service.MODEL_PATH") as mock_path:
        mock_path.exists.return_value = False
        with patch("app.ml.forecast_service._model", None):
            response = test_client.get("/forecast/pm25", params={"location": "Delhi - DTU"})
            assert response.status_code == 500
            assert "artifact was not found" in response.json()["detail"]
