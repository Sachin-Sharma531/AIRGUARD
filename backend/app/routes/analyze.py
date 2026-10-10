import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.ml.inference import BasePredictor, get_predictor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze air pollutant metrics and predict AQI",
    description="Accepts pollutant concentrations and meteorological readings, computes AQI sub-indices, and returns health impact advisories.",
    responses={
        200: {
            "description": "Successful analysis with AQI calculation and recommendations."
        },
        422: {
            "description": "Validation error caused by negative or out-of-range sensor readings."
        },
        500: {
            "description": "Internal server error during analysis processing."
        },
    },
)
async def analyze_air_quality(
    payload: AnalyzeRequest,
    predictor: BasePredictor = Depends(get_predictor),
) -> AnalyzeResponse:
    """
    Analyzes submitted air pollutant metrics.

    - **pm25**: PM2.5 concentration in µg/m³ (required)
    - **pm10**: PM10 concentration in µg/m³ (required)
    - **no2**, **so2**, **co**, **o3**: Optional gaseous pollutant measurements
    - **temperature**, **humidity**: Optional meteorological observations
    """
    try:
        result = predictor.predict(payload)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error occurred while analyzing air quality metrics: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the air quality metrics.",
        ) from exc

