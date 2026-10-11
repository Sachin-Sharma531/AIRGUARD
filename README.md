# AIRGUARD — Air Pollution Monitoring & Route Recommendation System

AIRGUARD is an intelligent, pollution-aware mobility and air quality forecasting platform. It compares journey options using travel duration and real-time/historical air-quality indicators, generates multi-objective route recommendations based on user priorities (**faster**, **balanced**, or **cleaner**), and provides a 3-hour machine learning PM2.5 forecast for ambient monitoring stations.

---

## 1. Project Architecture & Structure

```text
AIRGUARD_Integrated/
├── frontend/             # React + Vite web application (Route planning & 3h Station Forecast)
├── backend/              # FastAPI application service
│   ├── app/
│   │   ├── main.py       # FastAPI application, CORS, and lifecycle management
│   │   ├── config.py     # Pydantic Settings and environment configuration
│   │   ├── routes/       # API routers: /routes/pollution-aware, /forecast, /geocode, /analyze
│   │   ├── schemas/      # Strict Pydantic models for request validation and response contracts
│   │   ├── services/     # Route optimization, Google Routes v2, Google Air Quality, polylines
│   │   └── ml/           # PM2.5 forecasting service, Random Forest model loader, and artifacts
│   │       ├── artifacts/ # Location for pm25_model.joblib (371MB) and delhi_clean.csv (40MB)
│   │       ├── forecast_service.py # Feature engineering (13 features) & model inference
│   │       └── inference.py        # EPA breakpoint AQI calculations & MockPredictor
│   └── tests/            # 70 automated tests covering routing, ML forecast, geometry, and API contracts
├── mock_frontend/        # Standalone verification & inspection console (zero dependencies)
└── docs/                 # Architecture audit and developer implementation guides
```

---

## 2. ML Forecasting Component Details

- **Model File**: `backend/app/ml/artifacts/pm25_model.joblib` (Random Forest Regressor, ~371 MB).
- **Dataset File**: `backend/app/ml/artifacts/delhi_clean.csv` (Historical continuous ambient observations from Jan 1, 2021 – Dec 31, 2022; 233,600 rows).
- **Model Inputs (13 features)**:
  1. `location`: Station identifier
  2. `PM2.5`: Latest continuous measurement ($\mu\text{g/m}^3$)
  3. `pm25_lag_1`: Measurement 3 hours prior ($t-3\text{h}$)
  4. `pm25_lag_2`: Measurement 6 hours prior ($t-6\text{h}$)
  5. `pm25_lag_3`: Measurement 9 hours prior ($t-9\text{h}$)
  6. `temperature`: Ambient temperature (°C)
  7. `humidity`: Relative humidity (%)
  8. `wind_speed`: Wind velocity (m/s)
  9. `wind_direction`: Wind vector (degrees)
  10. `hour_sin` & 11. `hour_cos`: Cyclical diurnal features
  11. `day_sin` & 13. `day_cos`: Cyclical weekly features
- **Prediction Horizon**: 180 minutes (3 hours ahead).

> [!IMPORTANT]
> **Prototype & Historical Limitation**: The ML forecasting engine operates on historical observations spanning 2021–2022 (latest baseline: December 31, 2022). It serves as an integrated demonstration of the machine-learning pipeline and feature engineering. It is **not** connected to live real-time sensors, and its outputs must be distinguished from current atmospheric conditions.

---

## 3. Quick Start & Setup Guide

### Step A: Place Required ML Artifacts

Ensure the large model and dataset artifacts are placed in the artifacts folder:

```powershell
# Expected locations:
backend/app/ml/artifacts/pm25_model.joblib
backend/app/ml/artifacts/delhi_clean.csv
```

_(These files are excluded from Git history via `.gitignore` to prevent repository bloat)._

### Step B: Backend Setup & Launch

Open a PowerShell terminal in `backend/`:

```powershell
cd backend
python -m venv .venv

# Note: If PowerShell blocks script execution, use 'python -m ...' directly or run:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt

# Create .env from template
Copy-Item .env.example .env

# Run development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify backend operation:

- Root greeting: [http://localhost:8000/](http://localhost:8000/)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Step C: Frontend Setup & Launch

Open a second terminal in `frontend/`:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

Features available in the UI:

1. **Route Optimizer Tab**: Compare routes by travel duration vs exposure index ($\text{AQI} \times \text{hours}$).
2. **3h PM2.5 Forecast Tab**: Select from historical Delhi stations (e.g. `Delhi - DTU`, `Delhi - Anand Vihar`), view baseline vs 3-hour ahead predicted PM2.5, see trend metrics, and receive departure time advisories.
3. **Demo / Live API Switcher**: Test offline without external API keys in Demo mode, or switch to Live API mode to query the local FastAPI backend.

---

## 4. Primary API Endpoints

### 1. `GET /forecast/pm25?location=Delhi%20-%20DTU`

Returns the latest historical PM2.5 observation, the 3-hour future prediction, feature timestamps, and prototype metadata:

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

### 2. `GET /forecast/stations`

Lists all available air quality monitoring stations in the historical dataset.

### 3. `POST /routes/pollution-aware`

Multi-objective route planner balancing travel duration and cumulative air quality exposure.
Payload:

```json
{
  "origin": { "latitude": 28.7501, "longitude": 77.1177 },
  "destination": { "latitude": 28.738, "longitude": 77.082 },
  "preference": "balanced",
  "travel_mode": "DRIVE",
  "compute_alternatives": true
}
```

### 4. `POST /geocode`

Resolves address strings into geographic coordinates via OpenStreetMap Nominatim (no Google API key required; address data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)). Common demo locations (DTU, Rohini, CP, Noida Sec 62) are pre-mapped for offline evaluation.

---

## 5. Automated Testing & Verification

Run the full automated test suite (70 tests):

```powershell
cd backend
python -m pytest tests -v
```

Run the standalone in-process smoke test runner:

```powershell
cd backend
python local_testing/manual_smoke_test.py
```

All 70 tests pass cleanly, covering:

- Route scoring, tie-breaking, and boundary limits.
- ML model artifact loading and forecast calculations.
- 422 error handling on invalid station inputs.
- Fallback behavior when air quality data is unavailable (avoids false clean route claims).
- Polyline decoding and waypoint sampling math.

---

## 6. Exposure Metric Clarification

- **Estimated Exposure Score**: Calculated as $\text{Average AQI} \times \frac{\text{duration\_seconds}}{3600}$ ($\text{AQI}\cdot\text{h}$).
- This represents an environmental exposure index for comparative route ranking, **not a clinically validated lung dose or medical diagnosis**.
