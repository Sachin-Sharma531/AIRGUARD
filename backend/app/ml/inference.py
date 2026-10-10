from abc import ABC, abstractmethod
from typing import Tuple, List
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, AQICategory


class BasePredictor(ABC):
    """
    Abstract interface for air quality predictors.
    Ensures that real ML models and mock predictors share identical method signatures.
    """

    @abstractmethod
    def predict(self, data: AnalyzeRequest) -> AnalyzeResponse:
        pass


class MockAirQualityPredictor(BasePredictor):
    """
    Deterministic mock predictor based on standard EPA AQI breakpoints.
    Provides realistic predictions while the ML team finalizes the trained model.
    """

    @staticmethod
    def _calculate_sub_index(conc: float, breakpoints: List[Tuple[float, float, int, int]]) -> int:
        for c_low, c_high, i_low, i_high in breakpoints:
            if c_low <= conc <= c_high:
                return round(((i_high - i_low) / (c_high - c_low)) * (conc - c_low) + i_low)
        # Cap at 500 if above maximum breakpoint
        if conc > breakpoints[-1][1]:
            return 500
        return 0

    def _calculate_pm25_aqi(self, pm25: float) -> int:
        pm25_breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.0, 35.4, 51, 100),
            (35.4, 55.4, 101, 150),
            (55.4, 150.4, 151, 200),
            (150.4, 250.4, 201, 300),
            (250.4, 500.4, 301, 500),
        ]
        return self._calculate_sub_index(pm25, pm25_breakpoints)

    def _calculate_pm10_aqi(self, pm10: float) -> int:
        pm10_breakpoints = [
            (0.0, 54.0, 0, 50),
            (54.0, 154.0, 51, 100),
            (154.0, 254.0, 101, 150),
            (254.0, 354.0, 151, 200),
            (354.0, 424.0, 201, 300),
            (424.0, 604.0, 301, 500),
        ]
        return self._calculate_sub_index(pm10, pm10_breakpoints)

    def _get_category_and_advisory(self, aqi: int) -> Tuple[AQICategory, str, List[str]]:
        if aqi <= 50:
            return (
                AQICategory.GOOD,
                "Air quality is considered satisfactory, and air pollution poses little or no risk.",
                ["Enjoy outdoor activities.", "No health precautions needed."]
            )
        elif aqi <= 100:
            return (
                AQICategory.MODERATE,
                "Air quality is acceptable; however, there may be a moderate health concern for sensitive individuals.",
                ["Unusually sensitive people should consider reducing prolonged outdoor exertion.", "Keep windows open for fresh air if comfortable."]
            )
        elif aqi <= 150:
            return (
                AQICategory.UNHEALTHY_SENSITIVE,
                "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
                ["Active children, elderly, and people with respiratory disease should limit outdoor exertion.", "Wear a mask if sensitive."]
            )
        elif aqi <= 200:
            return (
                AQICategory.UNHEALTHY,
                "Everyone may begin to experience health effects; members of sensitive groups may experience more serious effects.",
                ["Avoid prolonged outdoor exertion.", "Wear an N95 mask outdoors.", "Close windows to avoid dirty outdoor air."]
            )
        elif aqi <= 300:
            return (
                AQICategory.VERY_UNHEALTHY,
                "Health alert: The risk of health effects is increased for everyone.",
                ["Avoid all physical outdoor activities.", "Keep air purifiers running indoors.", "Wear sealed N95/FFP2 masks outdoors."]
            )
        else:
            return (
                AQICategory.HAZARDOUS,
                "Health warning of emergency conditions: Everyone is more likely to be affected.",
                ["Remain indoors with air filtration.", "Avoid opening windows and doors.", "Seek medical attention if experiencing breathing distress."]
            )

    def predict(self, data: AnalyzeRequest) -> AnalyzeResponse:
        pm25_aqi = self._calculate_pm25_aqi(data.pm25)
        pm10_aqi = self._calculate_pm10_aqi(data.pm10)

        # The overall AQI is driven by the highest pollutant sub-index
        if pm25_aqi >= pm10_aqi:
            overall_aqi = pm25_aqi
            dominant = "PM2.5"
        else:
            overall_aqi = pm10_aqi
            dominant = "PM10"

        category, advisory, recommendations = self._get_category_and_advisory(overall_aqi)

        return AnalyzeResponse(
            aqi=overall_aqi,
            category=category,
            dominant_pollutant=dominant,
            health_advisory=advisory,
            recommendations=recommendations,
            is_mock=True,
        )


# Singleton factory or getter for dependency injection
_predictor_instance: BasePredictor = MockAirQualityPredictor()


def get_predictor() -> BasePredictor:
    """
    Returns the active predictor instance.
    When the ML team provides a real trained model artifact, 
    we only need to swap the instance returned here.
    """
    return _predictor_instance
