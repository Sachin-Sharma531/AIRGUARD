import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.routing import RoutePlanRequest, RoutePlanResponse
from app.services.route_optimizer import RouteOptimizerService, get_route_optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Routing"])


@router.post(
    "/routes/pollution-aware",
    response_model=RoutePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute pollution-aware navigation routes",
    description=(
        "Calculates candidate driving/walking routes between origin and destination coordinates, "
        "samples air quality indices along each path, estimates cumulative exposure, and recommends "
        "the optimal route based on the selected trade-off preference ('faster', 'balanced', or 'cleaner')."
    ),
    responses={
        200: {
            "description": "Successfully generated recommended route with alternatives and trade-off metrics."
        },
        400: {
            "description": "Invalid input parameters (e.g. origin and destination are identical)."
        },
        404: {
            "description": "No routing paths found between the specified origin and destination."
        },
        422: {
            "description": "Validation error caused by out-of-range coordinates or malformed request payload."
        },
        502: {
            "description": "Upstream error communicating with external routing or air quality providers."
        },
        503: {
            "description": "External routing service credentials not configured."
        },
        504: {
            "description": "Timeout communicating with upstream routing or environmental APIs."
        },
    },
)
@router.post(
    "/routes",
    response_model=RoutePlanResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.post(
    "/routes/plan",
    response_model=RoutePlanResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def plan_pollution_aware_route(
    payload: RoutePlanRequest,
    optimizer: RouteOptimizerService = Depends(get_route_optimizer),
) -> RoutePlanResponse:
    """
    Computes pollution-aware routes balancing travel duration and air pollution exposure.
    """
    try:
        response = await optimizer.plan_route(payload)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during route planning: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while calculating the pollution-aware route.",
        ) from exc
