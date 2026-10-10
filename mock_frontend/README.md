# AIRGUARD — Mock Frontend Verification Console

An interactive, zero-dependency testing interface designed to verify AIRGUARD's pollution-aware routing engine, validate API contracts, and test both synthetic mock datasets and live Google Maps integrations.

---

## 1. Quick Start

### A. Start the Backend API
From the project root:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### B. Launch the Mock Frontend
The mock frontend uses modern Vanilla HTML/CSS/JavaScript with ES modules. Serve it with any local static HTTP server:

```powershell
# Option 1: Python built-in HTTP server (recommended)
cd mock_frontend
python -m http.server 8080

# Option 2: Node npx serve (if Node is available)
npx serve mock_frontend -p 8080
```

Open your browser to:
**[http://localhost:8080](http://localhost:8080)** (or `http://127.0.0.1:8080`)

---

## 2. Testing Modes

The frontend provides two explicit, clearly segregated testing modes toggled at the top of the interface:

### Mode A — Mock Mode (Deterministic Synthetic Data)
* **Goal**: Validate UI states, loading states, error handling, route card rendering, metric formulas, and trade-off summaries without incurring API costs.
* **Data Source**: Pre-configured deterministic test fixtures (`mock_data.js`) aligned with EPA air quality breakpoints and backend Pydantic models.
* **Available Scenarios**:
  1. **Delhi CP → Noida Sec 62 (3-Way Comparison)**: Evaluates fast & dirty expressway vs balanced bypass vs clean parkway.
  2. **Saket → Cyber City (Smog Tie-Break)**: Demonstrates how a 60-second delay yields an 82% reduction in toxic exposure.
  3. **Arterial Corridor (Single Route)**: Validates single-candidate route handling when no alternatives exist.
  4. **Remote Corridor (Missing AQI Data)**: Demonstrates safe fallback to travel time without fabricating clean claims.

### Mode B — Live Backend API Mode
* **Goal**: Test end-to-end HTTP communication against your local running FastAPI instance (`http://localhost:8000`).
* **Data Flow**:
  $$\text{User Input} \longrightarrow \text{Frontend} \xrightarrow{\text{POST}} \text{FastAPI } (\text{/routes/pollution-aware}) \xrightarrow{} \text{Google Routes v2 \& Air Quality} \longrightarrow \text{Route Optimizer} \longrightarrow \text{Frontend Rendering}$$
* **Live Error Diagnostics**:
  * **HTTP 503**: Clean diagnostic if Google API keys are missing in `.env`.
  * **HTTP 504**: Clean handling if Google API requests time out.
  * **HTTP 422**: Real validation errors (e.g. latitude > 90 or identical origin/destination).
  * **Connection Refused**: Guided prompt to launch `uvicorn`.

---

## 3. Features & Visual Breakdown

* **Recommended Route vs Alternatives**: Recommended route is badged in emerald with a glowing card border and highlighted selection rationale.
* **Metric Cards**:
  * **Travel Time**: Human-formatted travel duration (`24 mins`).
  * **Distance**: Human-formatted distance (`18.2 km`).
  * **Average AQI**: Time-weighted average AQI along route checkpoints.
  * **Exposure Score**: Cumulative exposure index ($\text{AQI} \times \text{hours}$).
  * **Rank Score**: Combined multi-objective score ($0.0$ to $1.0$).
* **Raw API Inspector**: Collapsible JSON accordion displaying the exact request payload sent and response JSON received, with a 1-click **Copy JSON** button.
* **Backend Health Probe**: Real-time ping button checking `http://localhost:8000/health`.

---

## 4. API Key Configuration (For Live Mode)

In `backend/.env`:
```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
# Or individual keys:
# GOOGLE_ROUTES_API_KEY=your_key
# GOOGLE_AIR_QUALITY_API_KEY=your_key
```

Required Google Cloud APIs enabled on your project:
1. **Routes API** (Directions v2)
2. **Air Quality API** (currentConditions:lookup)
