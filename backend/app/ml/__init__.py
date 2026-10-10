"""ML model integration and inference package."""

from app.ml.forecast_service import (
    get_available_locations,
    predict_pollution,
)
from app.ml.inference import (
    BasePredictor,
    MockAirQualityPredictor,
    get_predictor,
)

__all__ = [
    "BasePredictor",
    "MockAirQualityPredictor",
    "get_available_locations",
    "get_predictor",
    "predict_pollution",
]

