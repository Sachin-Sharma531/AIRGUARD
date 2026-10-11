# AIRGUARD — Backend Service

The backend API service for **AIRGUARD** (Air Pollution Monitoring & Prediction System), built with FastAPI, Pydantic, and Uvicorn.

---

## 1. Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── config.py             # Type-safe settings loader & environment manager
│   ├── main.py               # FastAPI application entry point, CORS, and router registration
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── analyze.py        # POST /analyze HTTP endpoint
│   │   ├── geocode.py        # POST /geocode address-to-coordinates endpoint
│   │   └── routing.py        # POST /routes/pollution-aware HTTP endpoint
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── analyze.py        # Pydantic request & response models for AQI analysis
│   │   └── routing.py        # Pydantic request & response models for route planning
│   ├── services/
│   │   ├── __init__.py
│   │   ├── http_client.py    # Reusable async HTTP client lifecycle manager
│   │   ├── polyline.py       # Geometry decoding, Haversine distance & coordinate sampling
│   │   ├── google_routes.py  # Google Routes API v2 integration client
│   │   ├── google_air_quality.py # Google Air Quality API integration client
│   │   └── route_optimizer.py # Multi-criteria exposure scoring & route selection
│   └── ml/
│       ├── __init__.py
│       └── inference.py      # Predictor interface & EPA-standard mock predictor
├── tests/
│   ├── __init__.py
│   ├── test_health.py        # Health probe and root endpoint tests
│   ├── test_ml.py            # Validation bounds and mock predictor tests
│   ├── test_analyze.py       # End-to-end API HTTP tests & dependency injection tests
│   └── test_routing.py       # Routing validation, mock provider, scoring & error handling tests
├── .env.example              # Environment variable template
├── .gitignore                # Git exclusion rules
├── requirements.txt          # Pinned Python dependencies
└── README.md
```

---

## 2. Setup & Installation

### A. Activate Virtual Environment

From the `backend/` directory:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### B. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## 3. Running the Server

Start the local development server with auto-reload:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Interactive API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API Documentation (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 4. API Endpoints

### `GET /health`

- **Purpose**: System liveness check for AWS App Runner / ALB probes.
- **Response**:
  ```json
  {
    "status": "healthy",
    "app": "AIRGUARD",
    "environment": "development"
  }
  ```

### `POST /geocode`

- **Purpose**: Resolves a human-readable place name/address into latitude/longitude before route planning.
- **Provider**: OpenStreetMap Nominatim Search API (`https://nominatim.openstreetmap.org/search`). No Google API key is required.
- **Attribution**: Address data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
- **Policy Compliance**: Identifies via custom `User-Agent`, caches queries in memory, and serializes requests to respect Nominatim usage guidelines.
- **Request**:
  ```json
  { "address": "Connaught Place, New Delhi" }
  ```
- **Response**:
  ```json
  {
    "formatted_address": "Connaught Place, New Delhi, Delhi, India",
    "latitude": 28.6315,
    "longitude": 77.2167
  }
  ```

### `POST /analyze`

- **Purpose**: Analyzes pollutant concentrations and returns computed/predicted AQI, category, and health advisories.
- **Request Body Example**:
  ```json
  {
    "pm25": 58.4,
    "pm10": 110.2,
    "no2": 32.0,
    "so2": 14.5,
    "co": 1.1,
    "o3": 40.0,
    "temperature": 29.0,
    "humidity": 62.0
  }
  ```
- **Response Body Example (200 OK)**:
  ```json
  {
    "aqi": 153,
    "category": "Unhealthy",
    "dominant_pollutant": "PM2.5",
    "health_advisory": "Everyone may begin to experience health effects; members of sensitive groups may experience more serious effects.",
    "recommendations": [
      "Avoid prolonged outdoor exertion.",
      "Wear an N95 mask outdoors.",
      "Close windows to avoid dirty outdoor air."
    ],
    "is_mock": true
  }
  ```

### `POST /routes/pollution-aware`

- **Purpose**: Plans navigation routes between origin and destination coordinates, samples air quality along each candidate path, computes time-weighted exposure, and selects the optimal route based on travel time and air quality trade-offs.
- **Aliases**: `POST /routes`, `POST /routes/plan`
- **Preferences**:
  - `faster`: Heavily weights travel time (85% time / 15% pollution).
  - `balanced`: Trades off travel time and exposure (50% time / 50% pollution with relative benefit tie-breaking).
  - `cleaner`: Prioritizes lower pollution exposure (15% time / 85% pollution).
- **Request Body Example**:
  ```json
  {
    "origin": {
      "latitude": 28.6139,
      "longitude": 77.209
    },
    "destination": {
      "latitude": 28.5355,
      "longitude": 77.391
    },
    "preference": "balanced",
    "travel_mode": "DRIVE",
    "compute_alternatives": true
  }
  ```
- **Response Body Example (200 OK)**:
  ```json
  {
    "recommended_route": {
      "route_id": "route-2",
      "description": "via Yamuna Expressway Link",
      "distance_meters": 18500,
      "duration_seconds": 1500,
      "distance_formatted": "18.5 km",
      "duration_formatted": "25 mins",
      "estimated_exposure_score": 28.33,
      "average_aqi": 68.0,
      "air_quality_category": "Moderate",
      "exposure_status": "ESTIMATED",
      "polyline": "encoded_polyline_string_here",
      "waypoints_sampled": 8,
      "score": 0.48,
      "normalized_time": 1.0,
      "normalized_exposure": 0.0,
      "is_recommended": true
    },
    "alternative_routes": [
      {
        "route_id": "route-1",
        "description": "via Inner Ring Rd",
        "distance_meters": 16200,
        "duration_seconds": 1320,
        "distance_formatted": "16.2 km",
        "duration_formatted": "22 mins",
        "estimated_exposure_score": 67.83,
        "average_aqi": 185.0,
        "air_quality_category": "Unhealthy",
        "exposure_status": "ESTIMATED",
        "polyline": "encoded_polyline_string_here",
        "waypoints_sampled": 8,
        "score": 0.5,
        "normalized_time": 0.0,
        "normalized_exposure": 1.0,
        "is_recommended": false
      }
    ],
    "preference": "balanced",
    "summary": "Recommended route-2 reduces estimated pollution exposure by 58.2% compared to the fastest route (route-1) for an extra 3 mins under the 'balanced' preference.",
    "data_limitations": []
  }
  ```

---

### `GET /forecast/stations`

- **Purpose**: Returns the list of all available air quality monitoring stations in the historical dataset.
- **Response Body Example (200 OK)**:
  ```json
  {
    "stations": [
      "Delhi - Alipur",
      "Delhi - Anand Vihar",
      "Delhi - DTU",
      "Delhi - IGI Airport (T3)",
      "Delhi - Mandir Marg",
      "Delhi - Punjabi Bagh",
      "Delhi - R K Puram",
      "Delhi - Rohini",
      "Delhi - Shadipur"
    ],
    "count": 9
  }
  ```

### `GET /forecast/pm25`

- **Purpose**: Predicts PM2.5 concentration three hours ahead for a historical monitoring station using the trained Random Forest model.
- **Query Parameters**:
  - `location` (string, required): Exact station name (e.g. `Delhi - DTU`).
- **Response Body Example (200 OK)**:
  ```json
  {
    "location": "Delhi - DTU",
    "current_pm25": 428.0,
    "predicted_pm25": 388.4,
    "observation_time": "2022-12-31T21:00:00",
    "prediction_time": "2023-01-01T00:00:00",
    "horizon_minutes": 180,
    "model": "random_forest",
    "data_source": "historical_dataset",
    "dataset_latest_observation": "2022-12-31T21:00:00",
    "is_live_forecast": false
  }
  ```
- **Important Note**: Predictions are derived from historical observations (ending Dec 31, 2022) to demonstrate the ML pipeline; they do not represent real-time sensor measurements.

---

## 5. Frontend Integration

The primary React + Vite application is located in `../frontend/`. It provides both the **Route Optimizer** and the **3h PM2.5 Forecast** views, supporting both offline Demo mode and live backend communication.

## 6. Running Tests

Run the complete test suite (70 tests):

```powershell
python -m pytest tests -v
```

Run the standalone CLI smoke test:

```powershell
python local_testing/manual_smoke_test.py
```
