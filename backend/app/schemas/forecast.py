from typing import List
from pydantic import BaseModel, Field


class ForecastResponse(BaseModel):
    """Schema for PM2.5 forecast endpoint response."""

    location: str = Field(..., description="Monitoring station name")
    current_pm25: float = Field(..., description="Baseline PM2.5 observation in µg/m³")
    predicted_pm25: float = Field(..., description="Predicted PM2.5 3 hours ahead in µg/m³")
    observation_time: str = Field(..., description="ISO 8601 timestamp of latest baseline observation")
    prediction_time: str = Field(..., description="ISO 8601 timestamp for the forecast target")
    horizon_minutes: int = Field(default=180, description="Forecast horizon in minutes")
    model: str = Field(default="random_forest", description="Predictive model architecture")
    data_source: str = Field(default="historical_dataset", description="Source of underlying observations")
    dataset_latest_observation: str = Field(..., description="Latest available observation date in dataset")
    is_live_forecast: bool = Field(default=False, description="Flag indicating if forecast uses live telemetry")


class StationsResponse(BaseModel):
    """Schema for available monitoring stations response."""

    stations: List[str] = Field(..., description="List of available monitoring station names")
    count: int = Field(..., description="Total number of available stations")
