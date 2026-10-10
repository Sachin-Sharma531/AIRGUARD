# AIRGUARD Backend Audit Report

**Date**: October 2026  
**Auditor**: Senior Backend Engineer & Software Architect  
**Project**: AIRGUARD (Air Pollution Monitoring & Prediction System)  
**Status**: Complete Backend Audit & Architecture Verification (Phase 1)

---

## 1. Executive Summary

This audit report evaluates the existing backend architecture, data flow, external integrations, security posture, test coverage, and code hygiene for the **AIRGUARD** backend.

The backend is built with **FastAPI**, **Pydantic v2**, and **Uvicorn**, providing two primary API capabilities:
1. Air pollutant analysis and EPA-standard AQI prediction (`POST /analyze`).
2. Pollution-aware multi-objective route planning and ranking (`POST /routes/pollution-aware`).

The existing codebase demonstrates strong architectural separation:
- Router endpoints handle HTTP validation and status codes.
- Pydantic models enforce strict coordinate bounds and input constraints.
- Services encapsulate external integrations behind abstract interfaces (`BaseRoutesProvider`, `BaseAirQualityProvider`, `BasePredictor`).
- In-memory caching with time-to-live (`DEFAULT_CACHE_TTL_SECONDS = 1800.0`) and coordinate rounding (~110m resolution) optimizes upstream API consumption.
- Multi-objective ranking balances travel duration against cumulative air pollution exposure with tie-break handling.

At handoff, **65 automated tests** pass cleanly with 0 failures, including geocoding contract tests and Google Routes request-shape tests added for this integration.

---

## 2. Codebase Architecture & Execution Flow

### 2.1 File Structure & Module Responsibilities

```text
backend/
├── app/
│   ├── config.py              # Pydantic Settings, environment variables, API key resolution
│   ├── main.py                # FastAPI app initialization, CORS middleware, lifespan events
│   ├── routes/
│   │   ├── analyze.py         # POST /analyze endpoint definition
│   │   └── routing.py         # POST /routes/pollution-aware endpoint and aliases
│   ├── schemas/
│   │   ├── analyze.py         # Pydantic schemas: AnalyzeRequest, AnalyzeResponse, AQICategory
│   │   └── routing.py         # Pydantic schemas: RoutePlanRequest, RoutePlanResponse, RouteDetails
│   ├── services/
│   │   ├── http_client.py     # Shared async httpx.AsyncClient lifecycle manager
│   │   ├── polyline.py        # Haversine distance, Google encoded polyline decoder, coordinate sampling
│   │   ├── google_routes.py   # Google Routes API (v2) client implementing BaseRoutesProvider
│   │   ├── google_air_quality.py # Google Air Quality API client implementing BaseAirQualityProvider
│   │   └── route_optimizer.py # Multi-criteria route exposure scoring and ranking service
│   └── ml/
│       └── inference.py       # BasePredictor interface & EPA breakpoint MockAirQualityPredictor
├── tests/
│   ├── conftest.py            # Pytest fixtures and mock scenario providers
│   ├── fixtures/              # Deterministic synthetic route and pollution fixtures
│   ├── test_analyze.py        # Analysis endpoint tests & dependency injection
│   ├── test_e2e_scenarios.py  # End-to-end multi-route and preference scenarios
│   ├── test_health.py         # Root and health check tests
│   ├── test_ml.py             # Validation bounds and predictor unit tests
│   ├── test_mock_datasets.py  # Fixture structure integrity tests
│   ├── test_route_optimizer_audit.py # Multi-objective ranking edge case tests
│   ├── test_routing.py        # Routing validation, mock providers, and error handling
│   └── test_services_unit.py  # Polyline, formatting, cache, and category mapper unit tests
└── local_testing/
    ├── manual_smoke_test.py   # Standalone smoke test runner
    └── mock_test_harness.html # Browser test harness
```

### 2.2 Execution Tracing of Primary Endpoints

#### Execution Flow: `POST /routes/pollution-aware`
1. **HTTP Ingestion**: Request received by `app.routes.routing:plan_pollution_aware_route`.
2. **Input Validation**: `RoutePlanRequest` validates:
   - Latitude `[-90, 90]`, Longitude `[-180, 180]`.
   - Distinct endpoints (`validate_endpoints_differ` raises 422 if distance < 1e-6 degrees).
   - Preference (`faster`, `balanced`, `cleaner`) and travel mode (`DRIVE`, `WALK`, etc.).
3. **Route Candidate Generation**: `RouteOptimizerService` invokes `routes_provider.get_routes()`:
   - Constructs Google Routes API v2 payload with field masks (`routes.duration`, `routes.distanceMeters`, `routes.polyline.encodedPolyline`, `routes.description`).
   - If missing API key, raises HTTP 503; if timeout, raises HTTP 504; if upstream failure, raises HTTP 502.
4. **Route Geometry & Coordinate Sampling**:
   - For each candidate route, decodes the polyline string into `(lat, lng)` coordinates.
   - Samples up to `ROUTING_MAX_SAMPLE_POINTS` (default: 8) evenly along cumulative distance, ensuring start and destination points are included.
5. **Environmental Exposure Sampling**:
   - Queries `air_quality_provider.get_air_quality_batch(sampled_points)`.
   - Google Air Quality client checks in-memory cache at `(round(lat, 3), round(lng, 3))` resolution within TTL (30 min).
   - Computes average AQI and estimated cumulative exposure index:  
     $$\text{Exposure Score} = \text{Average AQI} \times \frac{\text{duration\_seconds}}{3600}$$
   - Identifies coverage status: `ESTIMATED` ($\ge 50\%$ valid samples), `INSUFFICIENT_DATA`, or `UNAVAILABLE`.
6. **Multi-Objective Scoring & Tie Breaking**:
   - Normalizes travel time: $\text{norm\_time} = \frac{T - T_{\min}}{T_{\max} - T_{\min}}$
   - Normalizes exposure: $\text{norm\_exp} = \frac{E - E_{\min}}{E_{\max} - E_{\min}}$
   - Calculates weighted score: $\text{Score} = w_{\text{time}} \cdot \text{norm\_time} + w_{\text{poll}} \cdot \text{norm\_exp}$
   - In `balanced` mode with symmetric min-max trade-offs, evaluates relative benefit ($> \Delta\text{time}$) before tie-breaking.
   - If pollution data is unavailable, falls back to normalized duration without fabricating clean route claims.
7. **Response Serialization**:
   - Marks lowest-score candidate as `recommended_route`.
   - Generates human-readable trade-off summary explaining time vs pollution savings.
   - Returns serialized `RoutePlanResponse`.

#### Execution Flow: `POST /analyze`
1. Request received by `app.routes.analyze:analyze_air_quality`.
2. `AnalyzeRequest` validates non-negative concentrations and physical bounds.
3. `predictor.predict(payload)` executes `MockAirQualityPredictor`:
   - Calculates EPA sub-indices for PM2.5 and PM10 using standard linear interpolation breakpoints.
   - Identifies dominant pollutant and assigns qualitative category (`Good` to `Hazardous`).
   - Generates health advisories and actionable mitigation recommendations.
4. Returns `AnalyzeResponse` with `is_mock: True`.

---

## 3. Detailed Audit Findings & Recommendations

### Finding 1: Concurrent Gathering for Air Quality Batch Sampling
* **File & Function**: `app/services/google_air_quality.py` -> `GoogleAirQualityClient.get_air_quality_batch`
* **Problem**: Queries sampled waypoints sequentially in a `for` loop with `await self.get_air_quality(lat, lng)`.
* **Why It Matters**: With 8 waypoints across candidate routes, sequential requests can accumulate 2.4s to 5s of latency on live network calls.
* **Classification**: Maintainability & Performance Improvement.
* **Recommended Fix**: Use `asyncio.gather(*[self.get_air_quality(lat, lng) for lat, lng in locations])` to fetch readings concurrently.
* **Blast Radius**: Zero. Return type and contract remain identical.

### Finding 2: CORS Configuration for Additional Local Development Ports
* **File & Function**: `app/config.py` -> `Settings.CORS_ORIGINS`
* **Problem**: Default CORS origins list was limited to `["http://localhost:3000", "http://localhost:5173"]`. Common testing servers run on ports `8080`, `8000`, and `5500`.
* **Why It Matters**: Browser preflight blocks mock frontend requests running on port 8080 or Live Server.
* **Classification**: Configuration & Usability Improvement.
* **Recommended Fix**: Expand default allowed origins in `config.py` to include `http://localhost:8080`, `http://127.0.0.1:8080`, `http://localhost:8000`, `http://127.0.0.1:8000`, `http://127.0.0.1:3000`, `http://127.0.0.1:5173`, `http://127.0.0.1:5500`.
* **Blast Radius**: Safe; purely additive for development convenience.

### Finding 3: Air Quality Missing Key Log Deduplication
* **File & Function**: `app/services/google_air_quality.py` -> `GoogleAirQualityClient.get_air_quality`
* **Problem**: Emits a `logger.warning` for every single waypoint when `GOOGLE_AIR_QUALITY_API_KEY` is not set, generating up to 24 identical warnings per request.
* **Why It Matters**: Clutters application logs during local testing or when the user intentionally runs routing-only tests.
* **Classification**: Observability & Hygiene Improvement.
* **Recommended Fix**: Log the warning once per instance or at debug level during waypoint evaluation when unconfigured.
* **Blast Radius**: None.

### Finding 4: Defensive Guard in Polyline Coordinate Sampling
* **File & Function**: `app/services/polyline.py` -> `sample_polyline_coordinates`
* **Problem**: If `max_samples <= 0`, logic branch evaluates `max_samples <= 2` as true and returns all coordinates.
* **Why It Matters**: Passing zero or negative samples should safely return an empty list.
* **Classification**: Defensive Bug Fix.
* **Recommended Fix**: Add explicit `if max_samples < 1: return []`.
* **Blast Radius**: None.

### Finding 5: Module Exports in `__init__.py`
* **File & Function**: `app/services/__init__.py` and `app/ml/__init__.py`
* **Problem**: Missing `__all__` exports for key service and ML classes.
* **Why It Matters**: Improves developer ergonomics when importing core domain services.
* **Classification**: Maintainability Improvement.
* **Recommended Fix**: Add explicit exports for `RouteOptimizerService`, `GoogleRoutesClient`, `GoogleAirQualityClient`, `BasePredictor`, etc.
* **Blast Radius**: None; existing deep imports remain intact.

### Finding 6: Google Routes Routing Preference for Non-Driving Modes
* **File & Function**: `backend/app/services/google_routes.py` -> `GoogleRoutesClient.get_routes`
* **Problem**: The original payload sent `routingPreference: ROUTING_PREFERENCE_UNSPECIFIED` for WALK and BICYCLE requests. The official Routes API reference says `routingPreference` can only be specified for DRIVE and TWO_WHEELER; setting it for other modes fails the request.
* **Fix Applied**: The backend now sends `routingPreference: TRAFFIC_AWARE` only for DRIVE and TWO_WHEELER, and omits the field for WALK/BICYCLE. Mocked request-shape tests cover both branches.
* **Reference**: Google Routes API Compute Routes documentation.

### Finding 7: Mock Frontend Separation
* **File & Function**: Root workspace / mock frontend
* **Problem**: Only an embedded testing HTML exists in `backend/local_testing/`. The project lacks a standalone, full-featured mock frontend with both Mock Mode (Mode A) and Live API Mode (Mode B), coordinate presets, interactive route comparison, and debug inspection.
* **Why It Matters**: Core Phase 3 requirement.
* **Classification**: Feature Requirement.
* **Recommended Fix**: Build `mock_frontend/` in the project root with pure Vanilla HTML/CSS/JS, dark mode aesthetic, full input validation, scenario switcher, live mode toggle, and API inspection.

---

## 4. Verification & Audit Conclusion

- **Syntactic Correctness**: 100% verified.
- **Import Hygiene**: All imports are active and resolvable.
- **Test Suite Status**: 65 of 65 tests passing (`python -m pytest tests -q`).
- **Smoke Runner**: Standalone runner `local_testing/manual_smoke_test.py` passed all checks.
- **Architecture Integrity**: Clean separation between routing, environmental sampling, scoring, schemas, and API routers.

Phase 1 is complete. We proceed directly to Phase 2 (clean and implement confirmed improvements).
