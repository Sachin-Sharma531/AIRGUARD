from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes.analyze import router as analyze_router
from app.routes.geocode import router as geocode_router
from app.routes.routing import router as routing_router
from app.services.http_client import close_http_client
from app.routes.forecast import router as forecast_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_http_client()


app = FastAPI(
    title=settings.APP_NAME,
    description="AIRGUARD Backend API - Air Pollution Monitoring & Prediction System",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing (CORS) for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    """
    Root endpoint providing a friendly status greeting.
    """
    return {
        "message": f"Welcome to the {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "routes": "/routes/pollution-aware",
        "geocode": "/geocode",
        "analyze": "/analyze",
        "forecast": "/forecast/pm25",
        "stations": "/forecast/stations",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Standard health check endpoint.
    Used by AWS App Runner / ALB / container orchestrators to monitor instance health.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


# Register domain routers
app.include_router(analyze_router)
app.include_router(geocode_router)
app.include_router(routing_router)
app.include_router(forecast_router)


