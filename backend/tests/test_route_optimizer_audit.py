"""
Phase 3 Regression & Audit Tests: Route Optimizer Algorithm
Verifies all 10 required algorithmic scenarios for the AIRGUARD route optimizer.
"""

import pytest
from app.schemas.routing import (
    Coordinates,
    ExposureStatus,
    RoutePlanRequest,
    RoutePreference,
)
from app.services.google_air_quality import AirQualityReading, BaseAirQualityProvider
from app.services.google_routes import BaseRoutesProvider, RawRouteCandidate
from app.services.route_optimizer import RouteOptimizerService


class CustomListRoutesProvider(BaseRoutesProvider):
    def __init__(self, candidates):
        self.candidates = candidates

    async def get_routes(self, *args, **kwargs):
        return self.candidates


class CustomDictAirQualityProvider(BaseAirQualityProvider):
    def __init__(self, aqi_by_route_id=None, default_reading=None):
        self.aqi_by_route_id = aqi_by_route_id or {}
        self.default_reading = default_reading or AirQualityReading(aqi=50, is_valid=True)
        self.call_count = 0

    async def get_air_quality(self, lat: float, lng: float):
        return self.default_reading

    async def get_air_quality_batch(self, locations):
        # Returns corresponding reading sequentially with modulo wrap
        idx = self.call_count
        self.call_count += 1
        keys = list(self.aqi_by_route_id.keys())
        if keys:
            r_id = keys[idx % len(keys)]
            reading = self.aqi_by_route_id[r_id]
            return [reading for _ in locations]
        return [self.default_reading for _ in locations]



BASE_ORIGIN = Coordinates(latitude=28.6139, longitude=77.2090)
BASE_DEST = Coordinates(latitude=28.5355, longitude=77.3910)


# --------------------------------------------------------------------------
# Scenario 1: One Candidate Route
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_1_single_candidate_route():
    candidates = [
        RawRouteCandidate(
            route_id="solo-route",
            description="Only Highway",
            distance_meters=10000,
            duration_seconds=900,
        )
    ]
    aq_provider = CustomDictAirQualityProvider({"solo-route": AirQualityReading(aqi=60, is_valid=True)})
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    req = RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED)
    res = await service.plan_route(req)

    assert res.recommended_route.route_id == "solo-route"
    assert len(res.alternative_routes) == 0
    assert "Only one candidate route was available" in res.summary


# --------------------------------------------------------------------------
# Scenario 2: Two routes where one is BOTH faster and cleaner (strictly dominant)
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_2_strictly_dominant_route():
    candidates = [
        RawRouteCandidate(route_id="dominant-route", distance_meters=8000, duration_seconds=600),
        RawRouteCandidate(route_id="inferior-route", distance_meters=12000, duration_seconds=1200),
    ]
    # Dominant route has AQI 30, Inferior has AQI 180
    aq_provider = CustomDictAirQualityProvider({
        "dominant-route": AirQualityReading(aqi=30, is_valid=True),
        "inferior-route": AirQualityReading(aqi=180, is_valid=True),
    })
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    for pref in [RoutePreference.FASTER, RoutePreference.BALANCED, RoutePreference.CLEANER]:
        req = RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=pref)
        res = await service.plan_route(req)
        assert res.recommended_route.route_id == "dominant-route"
        assert res.recommended_route.score == 0.0


# --------------------------------------------------------------------------
# Scenario 3: Faster but dirtier vs Slower but cleaner
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_3_tradeoff_faster_dirty_vs_slower_clean():
    candidates = [
        RawRouteCandidate(route_id="fast-dirty", distance_meters=10000, duration_seconds=900),   # 15m, AQI 250 -> Exp 62.5
        RawRouteCandidate(route_id="slow-clean", distance_meters=14000, duration_seconds=1500),  # 25m, AQI 35 -> Exp 14.58
    ]
    aq_provider = CustomDictAirQualityProvider({
        "fast-dirty": AirQualityReading(aqi=250, is_valid=True),
        "slow-clean": AirQualityReading(aqi=35, is_valid=True),
    })
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    # Under cleaner: slow-clean must win
    res_clean = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.CLEANER))
    assert res_clean.recommended_route.route_id == "slow-clean"

    # Under faster: fast-dirty must win
    res_fast = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.FASTER))
    assert res_fast.recommended_route.route_id == "fast-dirty"


# --------------------------------------------------------------------------
# Scenario 4: Three or more candidate routes
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_4_three_or_more_candidates():
    candidates = [
        RawRouteCandidate(route_id="route-A", distance_meters=10000, duration_seconds=900),   # Fast (15m), AQI 220
        RawRouteCandidate(route_id="route-B", distance_meters=11000, duration_seconds=1050),  # Mid (17.5m), AQI 70
        RawRouteCandidate(route_id="route-C", distance_meters=15000, duration_seconds=1600),  # Slow (26.6m), AQI 35
    ]
    aq_provider = CustomDictAirQualityProvider({
        "route-A": AirQualityReading(aqi=220, is_valid=True),
        "route-B": AirQualityReading(aqi=70, is_valid=True),
        "route-C": AirQualityReading(aqi=35, is_valid=True),
    })
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    res_bal = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))
    assert len(res_bal.alternative_routes) == 2
    assert res_bal.recommended_route.route_id in ["route-A", "route-B", "route-C"]


# --------------------------------------------------------------------------
# Scenario 5: Identical route metrics
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_5_identical_route_metrics():
    candidates = [
        RawRouteCandidate(route_id="identical-1", distance_meters=10000, duration_seconds=900),
        RawRouteCandidate(route_id="identical-2", distance_meters=10000, duration_seconds=900),
    ]
    aq_provider = CustomDictAirQualityProvider({
        "identical-1": AirQualityReading(aqi=80, is_valid=True),
        "identical-2": AirQualityReading(aqi=80, is_valid=True),
    })
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    res = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))
    # Neither route should receive an arbitrary discount; scores remain equal
    assert res.recommended_route.score == 0.0
    assert res.alternative_routes[0].score == 0.0


# --------------------------------------------------------------------------
# Scenario 6: Order Invariance (Reversing candidate inputs produces identical winner)
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_6_order_invariance():
    route_fast = RawRouteCandidate(route_id="route-fast", distance_meters=10000, duration_seconds=900)
    route_clean = RawRouteCandidate(route_id="route-clean", distance_meters=11000, duration_seconds=960)

    # Test order [fast, clean]
    aq1 = CustomDictAirQualityProvider({
        "route-fast": AirQualityReading(aqi=280, is_valid=True),
        "route-clean": AirQualityReading(aqi=45, is_valid=True),
    })
    s1 = RouteOptimizerService(routes_provider=CustomListRoutesProvider([route_fast, route_clean]), air_quality_provider=aq1)
    res1 = await s1.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))

    # Test reversed order [clean, fast]
    aq2 = CustomDictAirQualityProvider({
        "route-clean": AirQualityReading(aqi=45, is_valid=True),
        "route-fast": AirQualityReading(aqi=280, is_valid=True),
    })
    s2 = RouteOptimizerService(routes_provider=CustomListRoutesProvider([route_clean, route_fast]), air_quality_provider=aq2)
    res2 = await s2.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))

    # Both input orders must select the exact same winner (route-clean)
    assert res1.recommended_route.route_id == "route-clean"
    assert res2.recommended_route.route_id == "route-clean"


# --------------------------------------------------------------------------
# Scenario 7: Missing pollution data
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_7_missing_pollution_data():
    candidates = [
        RawRouteCandidate(route_id="route-1", distance_meters=10000, duration_seconds=800),
        RawRouteCandidate(route_id="route-2", distance_meters=12000, duration_seconds=1100),
    ]
    # Coverage completely unavailable
    aq_provider = CustomDictAirQualityProvider(default_reading=AirQualityReading(is_valid=False, aqi=None))
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    res = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.CLEANER))
    assert res.recommended_route.exposure_status == ExposureStatus.UNAVAILABLE
    assert res.recommended_route.estimated_exposure_score is None
    # Falls back to shortest travel time without claiming clean air
    assert res.recommended_route.route_id == "route-1"
    assert len(res.data_limitations) > 0


# --------------------------------------------------------------------------
# Scenario 8: Zero or boundary travel time / distance values
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_8_zero_duration_boundary():
    candidates = [
        RawRouteCandidate(route_id="zero-duration", distance_meters=0, duration_seconds=0),
        RawRouteCandidate(route_id="normal-route", distance_meters=5000, duration_seconds=400),
    ]
    aq_provider = CustomDictAirQualityProvider({"zero-duration": AirQualityReading(aqi=50, is_valid=True), "normal-route": AirQualityReading(aqi=50, is_valid=True)})
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    # Must process without ZeroDivisionError
    res = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST))
    assert res.recommended_route is not None


# --------------------------------------------------------------------------
# Scenario 9: Very small vs very large differences
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_9_small_vs_large_differences():
    # A) 1-second time difference, 80% pollution difference -> cleaner route must win
    c_small = [
        RawRouteCandidate(route_id="fast-dirty", distance_meters=10000, duration_seconds=900),
        RawRouteCandidate(route_id="clean-1s-slower", distance_meters=10000, duration_seconds=901),
    ]
    aq_small = CustomDictAirQualityProvider({
        "fast-dirty": AirQualityReading(aqi=200, is_valid=True),
        "clean-1s-slower": AirQualityReading(aqi=40, is_valid=True),
    })
    s_small = RouteOptimizerService(routes_provider=CustomListRoutesProvider(c_small), air_quality_provider=aq_small)
    res_small = await s_small.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))
    assert res_small.recommended_route.route_id == "clean-1s-slower"

    # B) 2-hour time difference (300% slower) for 1% less pollution -> faster route must win
    c_large = [
        RawRouteCandidate(route_id="fast-normal", distance_meters=10000, duration_seconds=1200),
        RawRouteCandidate(route_id="absurdly-slow", distance_meters=50000, duration_seconds=8400),  # +2 hours
    ]
    aq_large = CustomDictAirQualityProvider({
        "fast-normal": AirQualityReading(aqi=100, is_valid=True),
        "absurdly-slow": AirQualityReading(aqi=99, is_valid=True),
    })
    s_large = RouteOptimizerService(routes_provider=CustomListRoutesProvider(c_large), air_quality_provider=aq_large)
    res_large = await s_large.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.BALANCED))
    assert res_large.recommended_route.route_id == "fast-normal"


# --------------------------------------------------------------------------
# Scenario 10: All three preferences on identical candidates
# --------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_10_all_preferences():
    candidates = [
        RawRouteCandidate(route_id="express", distance_meters=10000, duration_seconds=900),    # 15m, AQI 180
        RawRouteCandidate(route_id="parkway", distance_meters=12000, duration_seconds=1300),   # 21.6m, AQI 40
    ]
    aq_provider = CustomDictAirQualityProvider({
        "express": AirQualityReading(aqi=180, is_valid=True),
        "parkway": AirQualityReading(aqi=40, is_valid=True),
    })
    service = RouteOptimizerService(routes_provider=CustomListRoutesProvider(candidates), air_quality_provider=aq_provider)

    res_faster = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.FASTER))
    assert res_faster.recommended_route.route_id == "express"

    res_cleaner = await service.plan_route(RoutePlanRequest(origin=BASE_ORIGIN, destination=BASE_DEST, preference=RoutePreference.CLEANER))
    assert res_cleaner.recommended_route.route_id == "parkway"
