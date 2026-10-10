# AIRGUARD Developer Guide & Operation Manual

**System**: AIRGUARD — Air Pollution Monitoring & Multi-Objective Route Optimization  
**Version**: 0.1.0 (Development Edition)

---

## 1. Prerequisites & Installation

### 1.1 Backend Dependencies
AIRGUARD requires **Python 3.11+** (Python 3.13 tested).

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment (if not already existing)
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 1.2 Frontend Dependencies
The mock frontend has **zero npm/build dependencies**. It is implemented using pure HTML5, CSS3, and ES Modules.

---

## 2. Configuration & Environment Variables

Create or update `backend/.env` based on `backend/.env.example`:

```env
# Core Application Settings
APP_NAME=AIRGUARD
ENVIRONMENT=development
DEBUG=True
PORT=8000
HOST=0.0.0.0

# CORS Whitelist (allows local frontend servers)
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8080","http://127.0.0.1:8080","http://localhost:8000","http://127.0.0.1:8000","http://127.0.0.1:3000","http://127.0.0.1:5500"]

# Google Cloud APIs Configuration
# If unconfigured, backend operates in fallback/mock testing mode.
GOOGLE_MAPS_API_KEY=your_google_cloud_api_key_here
# Optional distinct API keys:
# GOOGLE_ROUTES_API_KEY=your_routes_api_key_here
# GOOGLE_AIR_QUALITY_API_KEY=your_air_quality_api_key_here

# Routing Settings
ROUTING_TIMEOUT_SECONDS=10.0
ROUTING_MAX_SAMPLE_POINTS=8
```

### Required Google Cloud Credentials (For Live Mode)
To use live routing with Google Maps, enable the following in the [Google Cloud Console](https://console.cloud.google.com/):
1. **Routes API** (Google Routes API v2 `computeRoutes`)
2. **Air Quality API** (Google Air Quality API `currentConditions:lookup`)

---

## 3. Starting the Services

### 3.1 Start the FastAPI Backend
From `backend/`:
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify backend health:
- Root greeting: [http://localhost:8000/](http://localhost:8000/)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Swagger OpenAPI documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3.2 Start the Mock Frontend
From `mock_frontend/`:
```powershell
python -m http.server 8080
```

Open your browser to:
**[http://localhost:8080](http://localhost:8080)** (or `http://127.0.0.1:8080`)

---

## 4. Using the Mock Frontend

### 4.1 Switching Modes
The top navigation bar contains two toggle buttons:
* **Mode A: Mock Mode (Synthetic)**: Loads pre-configured, deterministic test datasets from `mock_data.js`. No Google API calls or costs are incurred. Ideal for testing UI components, trade-off explanations, and loading states.
* **Mode B: Live Backend API**: Dispatches actual HTTP POST calls to `http://localhost:8000/routes/pollution-aware`. The backend will query Google Routes v2 and Google Air Quality APIs if credentials are configured.

### 4.2 Available Test Scenarios (Mode A)
1. **Delhi CP → Noida Sec 62**: 3 routes (Fastest/Smog Expressway vs Ring Road Bypass vs Clean Belt Parkway).
2. **Saket → Cyber City**: High smog tie-break scenario (60-second delay yields an 82% reduction in exposure).
3. **Arterial Corridor**: Single route candidate without alternatives.
4. **Remote Corridor**: Missing environmental sensor data (tests duration-only fallback without false clean claims).

### 4.3 Raw API Inspection
Click **View Raw API Request & Response JSON** at the bottom of the results card to inspect the exact JSON sent and returned, or use the **Copy JSON** button.

---

## 5. Running Automated Tests

Run the complete test suite with `pytest`:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

Run the standalone CLI smoke test:
```powershell
cd backend
python local_testing/manual_smoke_test.py
```

---

## 6. Implementation Status Matrix

| Component / Feature | Status | Notes |
| :--- | :--- | :--- |
| **FastAPI Core & Routers** | `IMPLEMENTED & TESTED` | Lifespan client management, CORS, root, and health checks |
| **POST /analyze** | `IMPLEMENTED & TESTED` | EPA breakpoint calculation with mock predictor |
| **POST /routes/pollution-aware** | `IMPLEMENTED & TESTED` | Schema validation, multi-criteria scoring, tie-breaking |
| **Polyline Geometry & Sampling** | `IMPLEMENTED & TESTED` | Pure Python Haversine + polyline decoder + waypoint sampler |
| **Google Routes Integration** | `IMPLEMENTED & TESTED` | Field masks, HTTP error handling, timeout (504), missing key (503) |
| **Google Air Quality Integration**| `IMPLEMENTED & TESTED` | 30-min in-memory cache, ~110m deduplication, concurrent batch |
| **Multi-Objective Optimizer** | `IMPLEMENTED & TESTED` | Normalized time vs exposure scoring, tie-break relative benefits |
| **Mock Frontend (Mode A & B)** | `IMPLEMENTED & TESTED` | Vanilla HTML/CSS/JS, scenario presets, live backend connector |
| **Live Google API Integration** | `IMPLEMENTED (UNTESTED CREDENTIALS)` | Integration code is complete; awaiting user's live Google API key |
| **Trained ML Model Weights** | `NOT IMPLEMENTED / MOCKED` | EPA mock predictor in place awaiting ML team model artifact |
| **AWS App Runner / Cloud Infra** | `NOT IMPLEMENTED (OUT OF SCOPE)` | Reserved for future cloud infrastructure phase |
