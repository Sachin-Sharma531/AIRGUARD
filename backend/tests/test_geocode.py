import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
import app.routes.geocode as geocode_routes


@pytest.fixture(autouse=True)
def clean_geocode_cache():
    """Ensure a clean geocode cache and reset dependency overrides before each test."""
    geocode_routes.clear_geocode_cache()
    yield
    geocode_routes.clear_geocode_cache()
    app.dependency_overrides.clear()


class FakeResponse:
    def __init__(self, data, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=response,
            )

    def json(self):
        return self._data


class FakeClient:
    def __init__(self, response_data=None, status_code: int = 200, side_effect=None):
        self.response_data = response_data
        self.status_code = status_code
        self.side_effect = side_effect
        self.call_count = 0
        self.last_url = None
        self.last_params = None
        self.last_headers = None
        self.last_timeout = None

    async def get(self, url, *, params, headers, timeout):
        self.call_count += 1
        self.last_url = url
        self.last_params = params
        self.last_headers = headers
        self.last_timeout = timeout

        if self.side_effect is not None:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            if callable(self.side_effect):
                return self.side_effect(url, params, headers, timeout)

        return FakeResponse(self.response_data, status_code=self.status_code)


def test_geocode_works_without_google_api_keys(monkeypatch):
    """Geocoding must succeed via Nominatim even when no Google API keys are configured."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        GOOGLE_MAPS_API_KEY=None,
        GOOGLE_GEOCODING_API_KEY=None,
        GOOGLE_ROUTES_API_KEY=None,
        GOOGLE_AIR_QUALITY_API_KEY=None,
    )

    fake_client = FakeClient(
        response_data=[
            {
                "place_id": 1001,
                "lat": "28.7501",
                "lon": "77.1177",
                "display_name": "Delhi Technological University, Shahbad Daulatpur, Delhi, 110042, India",
            }
        ]
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Delhi Technological University, Delhi"})

    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == pytest.approx(28.7501)
    assert data["longitude"] == pytest.approx(77.1177)
    assert data["formatted_address"] == "Delhi Technological University, Shahbad Daulatpur, Delhi, 110042, India"

    # Verify query parameters and User-Agent header
    assert fake_client.call_count == 1
    assert fake_client.last_params["q"] == "Delhi Technological University, Delhi"
    assert fake_client.last_params["format"] == "jsonv2"
    assert fake_client.last_params["limit"] == 1
    assert "AIRGUARD" in fake_client.last_headers["User-Agent"]


def test_geocode_successful_address_lookup(monkeypatch):
    """Successful address resolution returns the provider formatted address and float coordinates."""
    fake_client = FakeClient(
        response_data=[
            {
                "place_id": 2002,
                "lat": "28.6315",
                "lon": "77.2167",
                "display_name": "Connaught Place, New Delhi, Delhi, India",
            }
        ]
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Connaught Place, New Delhi"})

    assert response.status_code == 200
    assert response.json() == {
        "formatted_address": "Connaught Place, New Delhi, Delhi, India",
        "latitude": 28.6315,
        "longitude": 77.2167,
    }


def test_geocode_no_matching_result(monkeypatch):
    """When Nominatim returns an empty list, endpoint returns HTTP 404."""
    fake_client = FakeClient(response_data=[])
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Nonexistent Place 999999"})

    assert response.status_code == 404
    assert "No location was found" in response.json()["detail"]


def test_geocode_upstream_http_status_error(monkeypatch):
    """When Nominatim returns an HTTP error status (e.g. 500 or 503), endpoint returns HTTP 502."""
    fake_client = FakeClient(response_data=None, status_code=500)
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 502
    assert "HTTP 500" in response.json()["detail"]


def test_geocode_upstream_connection_error(monkeypatch):
    """When connection to Nominatim fails, endpoint returns HTTP 502."""
    req_err = httpx.ConnectError("Connection refused by upstream host")
    fake_client = FakeClient(side_effect=req_err)
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 502
    assert "Could not connect to Nominatim Geocoding API" in response.json()["detail"]


def test_geocode_upstream_timeout(monkeypatch):
    """When Nominatim times out, endpoint returns HTTP 504 Gateway Timeout."""
    timeout_err = httpx.ReadTimeout("Nominatim timed out after 10s")
    fake_client = FakeClient(side_effect=timeout_err)
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


def test_geocode_invalid_response_structure(monkeypatch):
    """When Nominatim returns an unexpected shape (e.g. a dict error instead of a list), return 502."""
    fake_client = FakeClient(response_data={"error": "Rate limit exceeded"})
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 502
    assert "invalid response structure" in response.json()["detail"]


def test_geocode_invalid_coordinate_types(monkeypatch):
    """Non-numeric coordinate strings in Nominatim response result in HTTP 502 rather than fabricated (0, 0)."""
    fake_client = FakeClient(
        response_data=[{"lat": "not_a_latitude", "lon": "not_a_longitude", "display_name": "Test"}]
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 502
    assert "invalid coordinates" in response.json()["detail"]


def test_geocode_out_of_range_coordinates(monkeypatch):
    """Out-of-range coordinates are rejected with HTTP 502."""
    fake_client = FakeClient(
        response_data=[{"lat": "195.0", "lon": "77.0", "display_name": "Test"}]
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    response = client.post("/geocode", json={"address": "Rohini, Delhi"})

    assert response.status_code == 502
    assert "out-of-range" in response.json()["detail"]


def test_geocode_rejects_blank_address():
    """Addresses with only whitespace are rejected by Pydantic schema with HTTP 422."""
    client = TestClient(app)
    response = client.post("/geocode", json={"address": "   "})
    assert response.status_code == 422


def test_geocode_caches_repeated_query(monkeypatch):
    """Consecutive queries for the same address are served from the cache, preventing redundant upstream calls."""
    fake_client = FakeClient(
        response_data=[
            {
                "lat": "28.7501",
                "lon": "77.1177",
                "display_name": "Delhi Technological University",
            }
        ]
    )
    monkeypatch.setattr(geocode_routes, "get_http_client", lambda timeout=10.0: fake_client)

    client = TestClient(app)
    resp1 = client.post("/geocode", json={"address": "DTU, Delhi"})
    assert resp1.status_code == 200
    assert fake_client.call_count == 1

    # Second request with different casing/trailing spaces should hit cache
    resp2 = client.post("/geocode", json={"address": "  dtu, delhi  "})
    assert resp2.status_code == 200
    assert fake_client.call_count == 1  # No additional network call made
    assert resp2.json() == resp1.json()
