import pytest
from pydantic import ValidationError
from app.schemas.analyze import AnalyzeRequest, AQICategory
from app.ml.inference import get_predictor


def test_schema_valid_input():
    payload = {
        "pm25": 35.0,
        "pm10": 70.0,
        "no2": 20.0,
        "temperature": 25.0,
        "humidity": 50.0
    }
    req = AnalyzeRequest(**payload)
    assert req.pm25 == 35.0
    assert req.pm10 == 70.0
    assert req.temperature == 25.0


def test_schema_rejects_negative_pollutants():
    with pytest.raises(ValidationError):
        AnalyzeRequest(pm25=-5.0, pm10=50.0)


def test_mock_predictor_good_air():
    predictor = get_predictor()
    req = AnalyzeRequest(pm25=8.0, pm10=20.0)
    res = predictor.predict(req)

    assert res.is_mock is True
    assert res.aqi <= 50
    assert res.category == AQICategory.GOOD
    assert len(res.recommendations) > 0


def test_mock_predictor_unhealthy_air():
    predictor = get_predictor()
    req = AnalyzeRequest(pm25=120.0, pm10=180.0)
    res = predictor.predict(req)

    assert res.is_mock is True
    assert 150 <= res.aqi <= 200
    assert res.category == AQICategory.UNHEALTHY
    assert "mask" in " ".join(res.recommendations).lower()


def test_mock_predictor_decimal_boundary():
    """Verify that decimal inputs sitting near breakpoint borders (e.g. 12.05) do not fall through."""
    predictor = get_predictor()
    req = AnalyzeRequest(pm25=12.05, pm10=54.5)
    res = predictor.predict(req)

    assert res.aqi > 50  # Must correctly be in Moderate range, not drop to 0
    assert res.category == AQICategory.MODERATE

