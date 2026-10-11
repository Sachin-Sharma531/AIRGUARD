# AIRGUARD Frontend

React + Vite frontend for the AIRGUARD pollution-aware route planner.

## 🌐 Live Deployments & Links

- **Live Web Application**: [https://main.d22vk6edkcne12.amplifyapp.com/](https://main.d22vk6edkcne12.amplifyapp.com/)
- **Live Backend API**: [https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws/](https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws/)
- **Backend API Documentation (Swagger UI)**: [https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws/docs](https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws/docs)

---

## Run locally

Requirements: Node.js 18+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`).

## Modes

- **Demo** uses clearly labelled synthetic sample data and does not require a running backend.
- **Live API** calls the FastAPI backend at `http://localhost:8000` by default. Set `VITE_API_BASE_URL` in a frontend `.env.local` file if the backend is running elsewhere.

Live routing uses `POST /routes/pollution-aware`, whose request requires coordinate objects, route preference (`faster`, `balanced`, or `cleaner`), travel mode (`DRIVE`, `WALK`, `BICYCLE`, or `TWO_WHEELER`), and `compute_alternatives`. The frontend resolves well-known demo places (DTU, Rohini, Connaught Place, Noida Sector 62, India Gate, Saket, Cyber City) locally; other addresses use `POST /geocode`.

The backend's route response currently provides average AQI, an estimated cumulative exposure index (`average AQI × duration in hours`), travel time, distance, route geometry, data coverage status, a recommendation summary, and data limitations. It does **not** provide trip-time forecasting or PM2.5 concentration in the route response, so the live UI does not invent those values.
