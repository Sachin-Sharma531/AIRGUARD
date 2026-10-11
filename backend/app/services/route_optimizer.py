import logging
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from app.config import Settings, get_settings
from app.schemas.analyze import AQICategory
from app.schemas.routing import (
    ExposureStatus,
    RouteDetails,
    RoutePlanRequest,
    RoutePlanResponse,
    RoutePreference,
)
from app.services.google_air_quality import BaseAirQualityProvider, GoogleAirQualityClient
from app.services.google_routes import BaseRoutesProvider, GoogleRoutesClient, RawRouteCandidate
from app.services.osrm_routes import OSRMRoutesClient
from app.services.polyline import decode_polyline, sample_polyline_coordinates
from app.services.open_meteo_air_quality import OpenMeteoAirQualityClient
from app.services.valhalla_routes import ValhallaRoutesClient

logger = logging.getLogger(__name__)


def format_duration(seconds: int) -> str:
    """Format duration in seconds into human-readable text."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min" if minutes == 1 else f"{minutes} mins"
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    return f"{hours}h {rem_min}m"


def format_distance(meters: int) -> str:
    """Format distance in meters into human-readable text."""
    if meters < 1000:
        return f"{meters} m"
    km = meters / 1000.0
    return f"{km:.1f} km"


def map_aqi_to_category(aqi: Optional[float]) -> Optional[AQICategory]:
    """Map numeric AQI to qualitative category."""
    if aqi is None:
        return None
    val = round(aqi)
    if val <= 50:
        return AQICategory.GOOD
    if val <= 100:
        return AQICategory.MODERATE
    if val <= 150:
        return AQICategory.UNHEALTHY_SENSITIVE
    if val <= 200:
        return AQICategory.UNHEALTHY
    if val <= 300:
        return AQICategory.VERY_UNHEALTHY
    return AQICategory.HAZARDOUS


class RouteOptimizerService:
    """
    Orchestrates route generation, environmental air quality sampling along paths,
    exposure estimation, and multi-objective ranking.
    """

    def __init__(
        self,
        routes_provider: Optional[BaseRoutesProvider] = None,
        air_quality_provider: Optional[BaseAirQualityProvider] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.routes_provider = routes_provider or GoogleRoutesClient(settings=self.settings)
        self.air_quality_provider = (
            air_quality_provider
            if air_quality_provider is not None
            else OpenMeteoAirQualityClient(settings=self.settings)
        )
    def _get_preference_weights(self, preference: RoutePreference) -> Tuple[float, float]:
        """Returns (time_weight, pollution_weight) based on user preference."""
        if preference == RoutePreference.FASTER:
            return (
                self.settings.ROUTING_WEIGHT_FASTER_TIME,
                self.settings.ROUTING_WEIGHT_FASTER_POLLUTION,
            )
        elif preference == RoutePreference.CLEANER:
            return (
                self.settings.ROUTING_WEIGHT_CLEANER_TIME,
                self.settings.ROUTING_WEIGHT_CLEANER_POLLUTION,
            )
        else:
            return (
                self.settings.ROUTING_WEIGHT_BALANCED_TIME,
                self.settings.ROUTING_WEIGHT_BALANCED_POLLUTION,
            )

    async def _evaluate_route_exposure(
        self,
        candidate: RawRouteCandidate,
        origin_coords: Tuple[float, float],
        dest_coords: Tuple[float, float],
    ) -> Tuple[Optional[float], Optional[float], Optional[AQICategory], ExposureStatus, int]:
        """
        Samples coordinates along route geometry, measures air quality, and computes
        time-weighted exposure index.
        """
        # 1. Decode polyline geometry
        if candidate.polyline_encoded:
            precision = 6 if candidate.route_id.startswith("valhalla-") else 5
            coords = decode_polyline(candidate.polyline_encoded, precision=precision)
        else:
            coords = [origin_coords, dest_coords]

        if not coords:
            coords = [origin_coords, dest_coords]

        # 2. Sample waypoints along the route
        sampled_points = sample_polyline_coordinates(
            coords,
            max_samples=self.settings.ROUTING_MAX_SAMPLE_POINTS,
        )

        if not sampled_points:
            return (None, None, None, ExposureStatus.UNAVAILABLE, 0)

        # 3. Retrieve air quality observations along sampled points
        readings = await self.air_quality_provider.get_air_quality_batch(sampled_points)
        valid_readings = [r for r in readings if r.is_valid and r.aqi is not None]

        if not valid_readings:
            return (None, None, None, ExposureStatus.UNAVAILABLE, len(sampled_points))

        # Check coverage completeness
        valid_ratio = len(valid_readings) / len(sampled_points)
        status = ExposureStatus.ESTIMATED if valid_ratio >= 0.5 else ExposureStatus.INSUFFICIENT_DATA

        # Compute average AQI along sampled points
        avg_aqi = sum(r.aqi for r in valid_readings if r.aqi is not None) / len(valid_readings)
        avg_aqi = round(avg_aqi, 1)

        # Estimate cumulative exposure index:
        # Exposure Index = average AQI * travel duration in hours
        # Distinct from concentration or direct lung dose.
        duration_hours = candidate.duration_seconds / 3600.0
        exposure_score = round(avg_aqi * duration_hours, 2)
        category = map_aqi_to_category(avg_aqi)

        return (exposure_score, avg_aqi, category, status, len(sampled_points))

    async def plan_route(self, request: RoutePlanRequest) -> RoutePlanResponse:
        """
        Plans candidate routes and selects the optimal route based on air pollution and travel duration.
        """
        # Fetch candidate routes from routing provider
        
              
        # Fetch candidate routes from routing provider


        if request.travel_mode.value == "DRIVE":
            routes_provider = (
                OSRMRoutesClient(settings=self.settings)
                if isinstance(self.routes_provider, GoogleRoutesClient)
                else self.routes_provider
            )
        elif request.travel_mode.value in ("WALK", "BICYCLE", "TWO_WHEELER"):
            routes_provider = ValhallaRoutesClient(settings=self.settings)
        else:
            routes_provider = self.routes_provider



        raw_candidates = await routes_provider.get_routes(
            origin_lat=request.origin.latitude,
            origin_lng=request.origin.longitude,
            dest_lat=request.destination.latitude,
            dest_lng=request.destination.longitude,
            travel_mode=request.travel_mode.value,
            compute_alternatives=request.compute_alternatives,
        )


        if not raw_candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No routing path could be found between the specified origin and destination.",
            )

        origin_tuple = (request.origin.latitude, request.origin.longitude)
        dest_tuple = (request.destination.latitude, request.destination.longitude)

        # Evaluate exposure for all candidate routes
        evaluated_routes: List[RouteDetails] = []
        limitations: List[str] = []

        for candidate in raw_candidates:
            (
                exp_score,
                avg_aqi,
                cat,
                exp_status,
                sampled_count,
            ) = await self._evaluate_route_exposure(candidate, origin_tuple, dest_tuple)

            if exp_status == ExposureStatus.UNAVAILABLE:
                msg = f"Air quality data unavailable for {candidate.route_id}; candidate evaluated without pollution metrics."
                if msg not in limitations:
                    limitations.append(msg)
            elif exp_status == ExposureStatus.INSUFFICIENT_DATA:
                msg = f"Partial air quality coverage for {candidate.route_id}; exposure calculated with limited sample points."
                if msg not in limitations:
                    limitations.append(msg)

            evaluated_routes.append(
                RouteDetails(
                    route_id=candidate.route_id,
                    description=candidate.description,
                    distance_meters=candidate.distance_meters,
                    duration_seconds=candidate.duration_seconds,
                    distance_formatted=format_distance(candidate.distance_meters),
                    duration_formatted=format_duration(candidate.duration_seconds),
                    estimated_exposure_score=exp_score,
                    average_aqi=avg_aqi,
                    air_quality_category=cat,
                    exposure_status=exp_status,
                    polyline=candidate.polyline_encoded,
                    waypoints_sampled=sampled_count,
                )
            )

        # Route Normalization and Ranking
        all_have_exposure = all(
            r.estimated_exposure_score is not None and r.exposure_status != ExposureStatus.UNAVAILABLE
            for r in evaluated_routes
        )

        # 1. Normalize travel times across candidates
        min_time = min(r.duration_seconds for r in evaluated_routes)
        max_time = max(r.duration_seconds for r in evaluated_routes)
        time_range = max_time - min_time

        # 2. Normalize exposure scores across candidates
        if all_have_exposure and len(evaluated_routes) > 1:
            exps = [r.estimated_exposure_score for r in evaluated_routes if r.estimated_exposure_score is not None]
            min_exp = min(exps)
            max_exp = max(exps)
            exp_range = max_exp - min_exp
        else:
            min_exp = 0.0
            max_exp = 0.0
            exp_range = 0.0

        w_time, w_pollution = self._get_preference_weights(request.preference)

        for route in evaluated_routes:
            norm_time = (route.duration_seconds - min_time) / time_range if time_range > 0 else 0.0
            route.normalized_time = round(norm_time, 4)

            if all_have_exposure and route.estimated_exposure_score is not None:
                norm_exp = (
                    (route.estimated_exposure_score - min_exp) / exp_range
                    if exp_range > 0
                    else 0.0
                )
                route.normalized_exposure = round(norm_exp, 4)
                route.score = round(w_time * norm_time + w_pollution * norm_exp, 4)
            else:
                # If exposure data is unavailable or insufficient across candidates,
                # fall back to normalized travel time alone to avoid fabricating pollution preference.
                route.normalized_exposure = None
                route.score = round(norm_time, 4)

        # Handle balanced preference tie-breaking when candidate routes have symmetric min-max scores
        if (
            request.preference == RoutePreference.BALANCED
            and len(evaluated_routes) == 2
            and all_have_exposure
            and time_range > 0
            and exp_range > 0
            and evaluated_routes[0].score is not None
            and evaluated_routes[1].score is not None
            and abs(evaluated_routes[0].score - evaluated_routes[1].score) < 1e-3
        ):
            r1, r2 = evaluated_routes[0], evaluated_routes[1]
            faster = r1 if r1.duration_seconds < r2.duration_seconds else r2
            slower = r2 if faster is r1 else r1

            if (
                faster.duration_seconds > 0
                and faster.estimated_exposure_score is not None
                and slower.estimated_exposure_score is not None
                and faster.estimated_exposure_score > 0
            ):
                time_increase_pct = (slower.duration_seconds - faster.duration_seconds) / faster.duration_seconds
                exp_reduction_pct = (faster.estimated_exposure_score - slower.estimated_exposure_score) / faster.estimated_exposure_score

                # If the percentage reduction in pollution significantly outweighs the percentage increase in duration,
                # favor the cleaner route; otherwise favor the faster route.
                if exp_reduction_pct > time_increase_pct:
                    slower.score = round(slower.score - 0.02, 4)
                else:
                    faster.score = round(faster.score - 0.02, 4)

        # Sort candidate routes by score ascending, breaking ties by duration then distance
        evaluated_routes.sort(
            key=lambda r: (
                r.score if r.score is not None else float("inf"),
                r.duration_seconds,
                r.distance_meters,
            )
        )

        # Mark top route as recommended
        recommended = evaluated_routes[0]
        recommended.is_recommended = True
        alternatives = evaluated_routes[1:]

        # Compose user-friendly summary of the decision trade-off
        if len(evaluated_routes) == 1:
            summary = (
                f"Selected {recommended.route_id} ({recommended.duration_formatted}, "
                f"{recommended.distance_formatted}). Only one candidate route was available from the provider."
            )
        elif not all_have_exposure:
            summary = (
                f"Recommended {recommended.route_id} as the fastest candidate ({recommended.duration_formatted}). "
                "Reliable air quality data was unavailable for all routes, so exposure-based ranking was omitted."
            )
        else:
            fastest_route = min(evaluated_routes, key=lambda r: r.duration_seconds)
            cleanest_route = min(
                evaluated_routes,
                key=lambda r: r.estimated_exposure_score if r.estimated_exposure_score is not None else float("inf"),
            )

            if recommended.route_id == cleanest_route.route_id and recommended.route_id != fastest_route.route_id:
                time_diff_sec = recommended.duration_seconds - fastest_route.duration_seconds
                exp_diff_pct = (
                    ((fastest_route.estimated_exposure_score - recommended.estimated_exposure_score) / fastest_route.estimated_exposure_score) * 100
                    if fastest_route.estimated_exposure_score and fastest_route.estimated_exposure_score > 0
                    else 0.0
                )
                summary = (
                    f"Recommended {recommended.route_id} reduces estimated pollution exposure by "
                    f"{exp_diff_pct:.1f}% compared to the fastest route ({fastest_route.route_id}) "
                    f"for an extra {format_duration(time_diff_sec)} under the '{request.preference.value}' preference."
                )
            elif recommended.route_id == fastest_route.route_id and recommended.route_id != cleanest_route.route_id:
                time_diff_sec = cleanest_route.duration_seconds - recommended.duration_seconds
                summary = (
                    f"Recommended {recommended.route_id} is the fastest candidate ({recommended.duration_formatted}), "
                    f"saving {format_duration(time_diff_sec)} under the '{request.preference.value}' preference."
                )
            else:
                summary = (
                    f"Recommended {recommended.route_id} effectively balances travel time "
                    f"({recommended.duration_formatted}) and estimated air quality "
                    f"(AQI ~{recommended.average_aqi}) under the '{request.preference.value}' preference."
                )

        return RoutePlanResponse(
            recommended_route=recommended,
            alternative_routes=alternatives,
            preference=request.preference,
            summary=summary,
            data_limitations=limitations,
        )


# Singleton factory for dependency injection
_optimizer_instance: Optional[RouteOptimizerService] = None


def get_route_optimizer() -> RouteOptimizerService:
    """Returns a singleton instance of RouteOptimizerService for FastAPI dependency injection."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = RouteOptimizerService()
    return _optimizer_instance
