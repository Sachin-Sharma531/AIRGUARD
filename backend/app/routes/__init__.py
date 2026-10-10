"""API route definitions and endpoints."""

from app.routes.analyze import router as analyze_router
from app.routes.forecast import router as forecast_router
from app.routes.geocode import router as geocode_router
from app.routes.routing import router as routing_router

__all__ = [
    "analyze_router",
    "forecast_router",
    "geocode_router",
    "routing_router",
]

