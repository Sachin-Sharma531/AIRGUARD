from fastapi import APIRouter, HTTPException, Query
from app.ml.forecast_service import get_available_locations, predict_pollution
from app.schemas.forecast import ForecastResponse, StationsResponse

router = APIRouter(prefix="/forecast", tags=["Forecast"])


@router.get("/stations", response_model=StationsResponse)
def list_stations():
    """
    Returns the list of available air quality monitoring stations
    present in the historical dataset.
    """
    try:
        stations = get_available_locations()
        return StationsResponse(stations=stations, count=len(stations))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load stations: {exc}") from exc


@router.get("/pm25", response_model=ForecastResponse)
def forecast_pm25(
    location: str = Query(
        ...,
        min_length=1,
        description="Exact monitoring station name from the historical dataset",
        examples=["Delhi - DTU"],
    )
):
    """
    Predicts PM2.5 concentration three hours ahead for a historical monitoring station.
    Note: Predictions are based on the historical dataset and do not represent live telemetry.
    """
    try:
        result = predict_pollution(location.strip())
        return ForecastResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

