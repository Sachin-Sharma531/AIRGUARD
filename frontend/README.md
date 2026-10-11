# AIRGUARD Frontend

React + Vite frontend for the AIRGUARD pollution-aware route planner.

## Run locally

Requirements: Node.js 18+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`).

## Environment Configuration

Configure the backend API URL using the `VITE_API_BASE_URL` environment variable:

- **Local development**: Default is `http://localhost:8000` (or via Vite proxy). You can override it in a `.env.local` file:
  ```env
  VITE_API_BASE_URL=http://localhost:8000
  ```
- **Production (AWS Amplify)**: Set `VITE_API_BASE_URL` in the AWS Amplify Console under **App settings > Environment variables**:
  ```env
  VITE_API_BASE_URL=https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws
  ```

## Modes

- **Demo** uses clearly labelled synthetic sample data and does not require a running backend.
- **Live API** calls the FastAPI backend configured by `VITE_API_BASE_URL`.

Live routing uses `POST /routes/pollution-aware`, whose request requires coordinate objects, route preference (`faster`, `balanced`, or `cleaner`), travel mode (`DRIVE`, `WALK`, `BICYCLE`, or `TWO_WHEELER`), and `compute_alternatives`. The frontend resolves well-known demo places (DTU, Rohini, Connaught Place, Noida Sector 62, India Gate, Saket, Cyber City) locally; other addresses use `POST /geocode` (powered by OpenStreetMap Nominatim).

## AWS Amplify Hosting Deployment

For AWS Amplify Hosting (static site):
- **Monorepo root / App root**: `frontend`
- **Build command**: `npm run build`
- **Build output directory**: `dist`
- **Environment variables**: `VITE_API_BASE_URL=https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws`
