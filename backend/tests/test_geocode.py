from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.main import app
import app.routes.geocode as geocode_routes


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": "OK",
            "results": [{
                "formatted_address": "Delhi Technological University, Shahbad Daulatpur, Delhi, India",
                "geometry": {"location": {"lat": 28.7501, "lng": 77.1177}},
            }],
        }


class FakeClient:
    async def get(self, url, *, params, timeout):
        assert params["address"] == "DTU, Delhi"
        assert params["key"] == "test-key"
        assert timeout > 0
        return FakeResponse()


def test_geocode_requires_api_key():
    app.dependency_overrides[get_settings] = lambda: Settings(
        GOOGLE_MAPS_API_KEY=None,
        GOOGLE_GEOCODING_API_KEY=None,
    )
    response = TestClient(app).post("/geocode", json={"address": "DTU, Delhi"})
    assert response.status_code == 503
    assert "Geocoding API key is not configured" in response.json()["detail"]


def test_geocode_rejects_blank_address():
    response = TestClient(app).post("/geocode", json={"address": "  "})
    assert response.status_code == 422


def test_geocode_returns_coordinates(monkeypatch):
    app.dependency_overrides[get_settings] = lambda: Settings(
        GOOGLE_MAPS_API_KEY=None,
        GOOGLE_GEOCODING_API_KEY="test-key",
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: FakeClient())
    response = TestClient(app).post("/geocode", json={"address": "DTU, Delhi"})
    assert response.status_code == 200
    assert response.json() == {
        "formatted_address": "Delhi Technological University, Shahbad Daulatpur, Delhi, India",
        "latitude": 28.7501,
        "longitude": 77.1177,
    }
