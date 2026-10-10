from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AQICategory(str, Enum):
    GOOD = "Good"
    MODERATE = "Moderate"
    UNHEALTHY_SENSITIVE = "Unhealthy for Sensitive Groups"
    UNHEALTHY = "Unhealthy"
    VERY_UNHEALTHY = "Very Unhealthy"
    HAZARDOUS = "Hazardous"


class AnalyzeRequest(BaseModel):
    """
    Input schema for air quality analysis and prediction.
    Accepts core pollutant measurements and environmental parameters.
    """
    pm25: float = Field(
        ...,
        ge=0.0,
        le=1000.0,
        description="Fine particulate matter (PM2.5) concentration in µg/m³",
        examples=[45.5],
    )
    pm10: float = Field(
        ...,
        ge=0.0,
        le=1500.0,
        description="Coarse particulate matter (PM10) concentration in µg/m³",
        examples=[85.0],
    )
    no2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1000.0,
        description="Nitrogen dioxide (NO2) concentration in µg/m³",
        examples=[24.0],
    )
    so2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1000.0,
        description="Sulfur dioxide (SO2) concentration in µg/m³",
        examples=[12.5],
    )
    co: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Carbon monoxide (CO) concentration in mg/m³",
        examples=[1.2],
    )
    o3: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1000.0,
        description="Ozone (O3) concentration in µg/m³",
        examples=[35.0],
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=-50.0,
        le=60.0,
        description="Ambient temperature in °C",
        examples=[28.5],
    )
    humidity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Relative humidity in percentage (0-100)",
        examples=[55.0],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "pm25": 58.4,
                "pm10": 110.2,
                "no2": 32.0,
                "so2": 14.5,
                "co": 1.1,
                "o3": 40.0,
                "temperature": 29.0,
                "humidity": 62.0,
            }
        }
    }


class AnalyzeResponse(BaseModel):
    """
    Response schema returning computed AQI, classification, and actionable insights.
    """
    aqi: int = Field(
        ...,
        ge=0,
        description="Calculated or predicted Air Quality Index (0-500+)",
        examples=[153],
    )
    category: AQICategory = Field(
        ...,
        description="Qualitative EPA/CPCB air quality category",
        examples=[AQICategory.UNHEALTHY],
    )
    dominant_pollutant: str = Field(
        ...,
        description="Primary pollutant driving the AQI score",
        examples=["PM2.5"],
    )
    health_advisory: str = Field(
        ...,
        description="Summary health impact statement",
        examples=["Some members of the general public may experience health effects."],
    )
    recommendations: List[str] = Field(
        ...,
        description="Actionable mitigation steps for individuals",
        examples=[
            "Wear an N95 mask outdoors.",
            "Avoid prolonged outdoor exertion.",
            "Run an indoor air purifier if available.",
        ],
    )
    is_mock: bool = Field(
        default=False,
        description="Indicates whether this prediction was produced by the mock model",
    )
