import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function apiFetch(endpoint, options = {}) {
  const primaryUrl = API_BASE ? `${API_BASE}${endpoint}` : endpoint
  try {
    const res = await fetch(primaryUrl, options)
    return res
  } catch (err) {
    // If relative proxy request fails (e.g. running on separate port), fallback to direct port 8000
    if (!API_BASE || !primaryUrl.startsWith('http://localhost:8000')) {
      try {
        return await fetch(`http://localhost:8000${endpoint}`, options)
      } catch {
        return await fetch(`http://127.0.0.1:8000${endpoint}`, options)
      }
    }
    throw err
  }
}

// Popular Delhi/NCR demo locations. These let the team test the UI without a
// geocoding key. Other text addresses are resolved through the backend /geocode endpoint.
const LOCATION_PRESETS = [
  { names: ['dtu', 'delhi technological university'], label: 'Delhi Technological University (DTU)', latitude: 28.7501, longitude: 77.1177, station: 'Delhi - DTU' },
  { names: ['rohini', 'rohini delhi', 'rohini sector 7'], label: 'Rohini, Delhi', latitude: 28.7380, longitude: 77.0820, station: 'Delhi - Rohini' },
  { names: ['connaught place', 'cp', 'rajiv chowk'], label: 'Connaught Place, New Delhi', latitude: 28.6315, longitude: 77.2167, station: 'Delhi - Mandir Marg' },
  { names: ['noida sector 62', 'sector 62 noida'], label: 'Sector 62, Noida', latitude: 28.6270, longitude: 77.3720, station: 'Noida - Sector 62' },
  { names: ['india gate'], label: 'India Gate, New Delhi', latitude: 28.6129, longitude: 77.2295, station: 'Delhi - Major Dhyan Chand National Stadium' },
  { names: ['saket', 'saket delhi'], label: 'Saket, New Delhi', latitude: 28.5245, longitude: 77.2066, station: 'Delhi - Sri Aurobindo Marg' },
  { names: ['cyber city', 'gurugram cyber city', 'cyber hub'], label: 'Cyber City, Gurugram', latitude: 28.4949, longitude: 77.0895, station: 'Gurugram - Vikas Sadan' },
]

const DEFAULT_STATIONS = [
  'Delhi - DTU',
  'Delhi - Anand Vihar',
  'Delhi - Punjabi Bagh',
  'Delhi - R K Puram',
  'Delhi - Shadipur',
  'Delhi - Mandir Marg',
  'Delhi - IGI Airport(T3)',
  'Delhi - Jahangirpuri',
  'Delhi - Rohini',
]

const MODE_MAP = {
  Walking: 'WALK',
  Driving: 'DRIVE',
  Cycling: 'BICYCLE',
  'Two-wheeler': 'TWO_WHEELER',
}

const MOCK_ROUTE_POINTS = [
  [
    [28.7501, 77.1177], [28.7460, 77.1090], [28.7435, 77.0980], [28.7395, 77.0890], [28.7380, 77.0820],
  ],
  [
    [28.7501, 77.1177], [28.7480, 77.1095], [28.7440, 77.1030], [28.7400, 77.0940], [28.7380, 77.0820],
  ],
  [
    [28.7501, 77.1177], [28.7520, 77.1080], [28.7465, 77.0985], [28.7420, 77.0895], [28.7380, 77.0820],
  ],
]

function encodePolyline(points) {
  let lastLat = 0
  let lastLng = 0
  let result = ''
  const encodeValue = (value) => {
    let v = value < 0 ? ~(value << 1) : value << 1
    let output = ''
    while (v >= 0x20) {
      output += String.fromCharCode((0x20 | (v & 0x1f)) + 63)
      v >>= 5
    }
    output += String.fromCharCode(v + 63)
    return output
  }
  points.forEach(([lat, lng]) => {
    const nextLat = Math.round(lat * 1e5)
    const nextLng = Math.round(lng * 1e5)
    result += encodeValue(nextLat - lastLat)
    result += encodeValue(nextLng - lastLng)
    lastLat = nextLat
    lastLng = nextLng
  })
  return result
}

function makeDemoResponse(preference) {
  const routes = [
    {
      route_id: 'demo-route-fast', description: 'Fastest arterial route', distance_meters: 12400,
      duration_seconds: 1860, distance_formatted: '12.4 km', duration_formatted: '31 min',
      estimated_exposure_score: 95.6, average_aqi: 185.0, air_quality_category: 'Unhealthy',
      exposure_status: 'ESTIMATED', polyline: encodePolyline(MOCK_ROUTE_POINTS[0]), waypoints_sampled: 5,
      score: 0.75, is_recommended: false,
    },
    {
      route_id: 'demo-route-balanced', description: 'Balanced bypass route', distance_meters: 13100,
      duration_seconds: 2220, distance_formatted: '13.1 km', duration_formatted: '37 min',
      estimated_exposure_score: 56.7, average_aqi: 92.0, air_quality_category: 'Moderate',
      exposure_status: 'ESTIMATED', polyline: encodePolyline(MOCK_ROUTE_POINTS[1]), waypoints_sampled: 5,
      score: 0.48, is_recommended: true,
    },
    {
      route_id: 'demo-route-parkway', description: 'Lower-exposure green corridor', distance_meters: 14800,
      duration_seconds: 2520, distance_formatted: '14.8 km', duration_formatted: '42 min',
      estimated_exposure_score: 38.5, average_aqi: 55.0, air_quality_category: 'Moderate',
      exposure_status: 'ESTIMATED', polyline: encodePolyline(MOCK_ROUTE_POINTS[2]), waypoints_sampled: 5,
      score: 0.62, is_recommended: false,
    },
  ]
  const index = preference === 'faster' ? 0 : preference === 'cleaner' ? 2 : 1
  routes.forEach((route, i) => { route.is_recommended = i === index })
  const recommended = routes[index]
  const alternatives = routes.filter((_, i) => i !== index)
  return {
    recommended_route: recommended,
    alternative_routes: alternatives,
    preference,
    summary: `DEMO ONLY: ${recommended.description} was selected for the '${preference}' preference using synthetic sample values. This is not live pollution data.`,
    data_limitations: ['Synthetic demo values only. Switch to Live API mode to query the backend and Google services.', 'Exposure index is an estimate calculated from average AQI and travel duration; it is not a medical dose.'],
  }
}

const DEMO_STATION_DATA = {
  'Delhi - DTU': { current: 428.0, predicted: 388.4 },
  'Delhi - Anand Vihar': { current: 452.0, predicted: 418.2 },
  'Delhi - Punjabi Bagh': { current: 395.0, predicted: 355.8 },
  'Delhi - RK Puram': { current: 362.5, predicted: 340.1 },
  'Delhi - R K Puram': { current: 362.5, predicted: 340.1 },
  'Delhi - Shadipur': { current: 410.0, predicted: 378.6 },
  'Delhi - Mandir Marg': { current: 310.0, predicted: 288.0 },
  'Delhi - IGI Airport (T3)': { current: 285.0, predicted: 260.4 },
  'Delhi - IGI Airport(T3)': { current: 285.0, predicted: 260.4 },
  'Delhi - Jahangirpuri': { current: 440.0, predicted: 398.5 },
  'Delhi - Rohini': { current: 415.0, predicted: 382.0 },
  'Delhi - Alipur': { current: 370.0, predicted: 345.0 },
}

function makeDemoForecastResponse(location = 'Delhi - DTU') {
  const data = DEMO_STATION_DATA[location] || { current: 385.0, predicted: 350.0 }
  return {
    location,
    current_pm25: data.current,
    predicted_pm25: data.predicted,
    observation_time: '2022-12-31T21:00:00',
    prediction_time: '2023-01-01T00:00:00',
    horizon_minutes: 180,
    model: 'random_forest',
    data_source: 'historical_dataset',
    dataset_latest_observation: '2022-12-31T21:00:00',
    is_live_forecast: false,
  }
}

function normalizeAddress(text) {
  return text.trim().toLowerCase().replace(/[^a-z0-9, .-]/g, '').replace(/\s+/g, ' ')
}

function parseCoordinates(text) {
  const match = text.trim().match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (!match) return null
  const latitude = Number(match[1])
  const longitude = Number(match[2])
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return { latitude, longitude, formatted_address: `${latitude.toFixed(5)}, ${longitude.toFixed(5)}` }
}

async function resolveLocation(text) {
  const coordinates = parseCoordinates(text)
  if (coordinates) return coordinates
  const normalized = normalizeAddress(text)
  const preset = LOCATION_PRESETS.find((item) => item.names.some((name) => normalizeAddress(name) === normalized))
  if (preset) return { latitude: preset.latitude, longitude: preset.longitude, formatted_address: preset.label }

  const response = await apiFetch('/geocode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address: text.trim() }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `Could not locate "${text}" (HTTP ${response.status}).`)
  return data
}

function decodePolyline(encoded) {
  if (!encoded || typeof encoded !== 'string') return []
  const points = []
  let index = 0
  let lat = 0
  let lng = 0
  while (index < encoded.length) {
    let result = 0
    let shift = 0
    let byte
    do {
      if (index >= encoded.length) return points
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    lat += (result & 1) ? ~(result >> 1) : (result >> 1)
    result = 0
    shift = 0
    do {
      if (index >= encoded.length) return points
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    lng += (result & 1) ? ~(result >> 1) : (result >> 1)
    points.push([lat / 1e5, lng / 1e5])
  }
  return points
}

function formatIsoTime(isoString) {
  if (!isoString) return '—'
  try {
    const d = new Date(isoString)
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}

function displayRouteName(route, index) {
  return route.description || route.route_id || `Route ${index + 1}`
}

function categoryTone(category) {
  const value = (category || '').toLowerCase()
  if (value.includes('good')) return 'tone-good'
  if (value.includes('moderate')) return 'tone-moderate'
  if (value.includes('unhealthy') || value.includes('hazardous')) return 'tone-high'
  return 'tone-unknown'
}

function buildRouteMap(routes) {
  const decoded = routes.map((route) => ({ route, points: decodePolyline(route.polyline) })).filter((item) => item.points.length > 1)
  if (!decoded.length) return null
  const allPoints = decoded.flatMap((item) => item.points)
  const lats = allPoints.map((p) => p[0])
  const lngs = allPoints.map((p) => p[1])
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLng = Math.min(...lngs)
  const maxLng = Math.max(...lngs)
  const latSpan = maxLat - minLat || 0.001
  const lngSpan = maxLng - minLng || 0.001
  const width = 500
  const height = 280
  const pad = 28
  const project = ([lat, lng]) => {
    const x = pad + ((lng - minLng) / lngSpan) * (width - pad * 2)
    const y = height - pad - ((lat - minLat) / latSpan) * (height - pad * 2)
    return [x, y]
  }
  return { decoded, project, width, height }
}

function App() {
  const [activeTab, setActiveTab] = useState('routes') // 'routes' | 'forecast'
  const [mode, setMode] = useState('demo')
  const [backendStatus, setBackendStatus] = useState('checking')

  // Routing State
  const [form, setForm] = useState({
    start: 'DTU',
    destination: 'Rohini',
    travelMode: 'Walking',
    preference: 'balanced',
  })
  const [tripResult, setTripResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Forecast State
  const [stations, setStations] = useState(DEFAULT_STATIONS)
  const [selectedStation, setSelectedStation] = useState('Delhi - DTU')
  const [forecastResult, setForecastResult] = useState(null)
  const [forecastLoading, setForecastLoading] = useState(false)
  const [forecastError, setForecastError] = useState('')

  const verifyBackend = useCallback(async () => {
    try {
      const response = await apiFetch('/health')
      if (response.ok) {
        setBackendStatus('online')
        return true
      }
      setBackendStatus('offline')
      return false
    } catch {
      setBackendStatus('offline')
      return false
    }
  }, [])

  useEffect(() => {
    let active = true

    const checkAndLoad = async () => {
      try {
        const response = await apiFetch('/health')
        if (response.ok) {
          if (active) setBackendStatus('online')
          // Load stations when backend is online
          try {
            const stRes = await apiFetch('/forecast/stations')
            if (stRes.ok) {
              const data = await stRes.json()
              if (active && data?.stations?.length) {
                setStations(data.stations)
              }
            }
          } catch {
            // fallback stations remain
          }
        } else {
          if (active) setBackendStatus('offline')
        }
      } catch {
        if (active) setBackendStatus('offline')
      }
    }

    checkAndLoad()
    // Poll every 3 seconds so status automatically updates as soon as the backend process starts
    const interval = setInterval(checkAndLoad, 3000)

    // Initialize default station forecast so it's ready immediately
    setForecastResult(makeDemoForecastResponse('Delhi - DTU'))

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))

  async function handleGetForecast(targetStation = selectedStation, overrideMode = null) {
    const station = targetStation || selectedStation
    const effectiveMode = overrideMode || mode
    setForecastError('')
    setForecastLoading(true)
    try {
      if (effectiveMode === 'demo') {
        await new Promise((resolve) => setTimeout(resolve, 200))
        setForecastResult(makeDemoForecastResponse(station))
      } else {
        try {
          const response = await apiFetch(`/forecast/pm25?location=${encodeURIComponent(station)}`)
          const data = await response.json().catch(() => ({}))
          if (!response.ok) {
            const err = new Error(data.detail || `Forecast request failed with HTTP ${response.status}`)
            err.isHttpError = true
            throw err
          }
          setForecastResult(data)
          setBackendStatus('online')
        } catch (fetchErr) {
          // If backend is offline or network fails, gracefully display demo data with a clear notification
          setForecastResult(makeDemoForecastResponse(station))
          if (fetchErr.isHttpError) {
            setForecastError(fetchErr.message)
            // Backend is still online since it returned an HTTP response
            setBackendStatus('online')
          } else {
            setForecastError('Backend service is offline or unreachable on port 8000. Start it with `python -m uvicorn app.main:app --port 8000` or switch to Demo mode. Showing local prototype data.')
            setBackendStatus('offline')
          }
        }
      }
    } catch (err) {
      setForecastResult(makeDemoForecastResponse(station))
      setForecastError(err.message || 'Backend service is offline. Showing local prototype data.')
    } finally {
      setForecastLoading(false)
    }
  }

  async function analyzeTrip(event) {
    event.preventDefault()
    setError('')
    setTripResult(null)
    if (!form.start.trim() || !form.destination.trim()) {
      setError('Enter both a starting point and a destination.')
      return
    }

    setLoading(true)
    try {
      if (mode === 'demo') {
        await new Promise((resolve) => setTimeout(resolve, 450))
        setTripResult({
          data: makeDemoResponse(form.preference),
          start: form.start.trim(),
          destination: form.destination.trim(),
          travelMode: form.travelMode,
          preference: form.preference,
          origin: { latitude: 28.7501, longitude: 77.1177 },
          destinationCoords: { latitude: 28.7380, longitude: 77.0820 },
          source: 'synthetic',
        })
      } else {
        const [origin, destination] = await Promise.all([
          resolveLocation(form.start),
          resolveLocation(form.destination),
        ])
        if (Math.abs(origin.latitude - destination.latitude) < 1e-6 && Math.abs(origin.longitude - destination.longitude) < 1e-6) {
          throw new Error('Starting point and destination resolve to the same coordinates. Please choose two different places.')
        }
        const payload = {
          origin: { latitude: origin.latitude, longitude: origin.longitude },
          destination: { latitude: destination.latitude, longitude: destination.longitude },
          preference: form.preference,
          travel_mode: MODE_MAP[form.travelMode] || 'WALK',
          compute_alternatives: true,
        }
        const response = await apiFetch('/routes/pollution-aware', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          if (response.status === 503) {
            throw new Error(
              'Backend is connected! Upstream Google Routes API key is not configured in backend/.env. Switch to "Demo" mode (top-right) to view sample route optimization, or configure GOOGLE_MAPS_API_KEY in backend/.env.'
            )
          }
          if (response.status === 404) throw new Error(data.detail || 'No route was found between those locations.')
          if (response.status === 422) throw new Error(`The backend rejected the request: ${JSON.stringify(data.detail || data)}`)
          throw new Error(data.detail || `Backend request failed (HTTP ${response.status}).`)
        }
        setTripResult({
          data,
          start: origin.formatted_address || form.start.trim(),
          destination: destination.formatted_address || form.destination.trim(),
          travelMode: form.travelMode,
          preference: form.preference,
          origin: { latitude: origin.latitude, longitude: origin.longitude },
          destinationCoords: { latitude: destination.latitude, longitude: destination.longitude },
          source: 'live',
        })
      }
    } catch (caught) {
      setError(caught?.message || 'Something went wrong while analyzing this trip.')
    } finally {
      setLoading(false)
    }
  }

  function resetTrip() {
    setTripResult(null)
    setError('')
  }

  const liveData = tripResult?.data
  const allRoutes = useMemo(() => {
    if (!liveData?.recommended_route) return []
    return [liveData.recommended_route, ...(liveData.alternative_routes || [])]
  }, [liveData])
  const recommendedRoute = liveData?.recommended_route
  const mapShape = useMemo(() => buildRouteMap(allRoutes), [allRoutes])

  const exposureComparison = useMemo(() => {
    if (!recommendedRoute || allRoutes.length < 2) {
      return {
        headline: '—',
        label: allRoutes.length === 1 ? 'Only one route candidate available from provider' : 'No routes available',
      }
    }

    const chosenExposure = recommendedRoute.estimated_exposure_score
    const hasValidExposure = Number.isFinite(chosenExposure) && chosenExposure > 0

    if (!hasValidExposure || recommendedRoute.exposure_status === 'UNAVAILABLE') {
      return {
        headline: '—',
        label: 'Air quality measurements unavailable for exposure comparison',
      }
    }

    const fastest = [...allRoutes].sort((a, b) => a.duration_seconds - b.duration_seconds)[0]
    const fastestExposure = fastest.estimated_exposure_score
    const alternatives = allRoutes.filter((r) => r.route_id !== recommendedRoute.route_id)
    const validAlts = alternatives.filter((r) => Number.isFinite(r.estimated_exposure_score))

    // Case 1: Recommended route is slower than the fastest route, but has lower exposure
    if (
      fastest.route_id !== recommendedRoute.route_id &&
      Number.isFinite(fastestExposure) &&
      fastestExposure > 0 &&
      chosenExposure < fastestExposure
    ) {
      const pct = Math.round(((fastestExposure - chosenExposure) / fastestExposure) * 100)
      return {
        headline: `${pct}%`,
        label: 'lower estimated exposure index than the fastest route',
      }
    }

    // Case 2: Recommended route IS the fastest route
    if (fastest.route_id === recommendedRoute.route_id && validAlts.length > 0) {
      const altExposures = validAlts.map((r) => r.estimated_exposure_score)
      const maxAltExposure = Math.max(...altExposures)

      if (maxAltExposure > chosenExposure) {
        const pct = Math.round(((maxAltExposure - chosenExposure) / maxAltExposure) * 100)
        return {
          headline: `${pct}%`,
          label: 'lower estimated exposure than the alternative path (also the fastest route)',
        }
      }

      return {
        headline: '✓ Optimal',
        label: 'Fastest route with minimal exposure across candidates',
      }
    }

    // Case 3: Recommended route prioritized speed over a cleaner alternative
    if (validAlts.length > 0) {
      const minAltExposure = Math.min(...validAlts.map((r) => r.estimated_exposure_score))
      if (minAltExposure < chosenExposure) {
        return {
          headline: '⚡ Fastest',
          label: 'Fastest route chosen by priority (alternative had lower pollution index)',
        }
      }
    }

    return {
      headline: '—',
      label: 'Exposure levels are closely matched across candidate routes',
    }
  }, [recommendedRoute, allRoutes])

  const mapsUrl = tripResult
    ? `https://www.google.com/maps/dir/?api=1&origin=${tripResult.origin.latitude},${tripResult.origin.longitude}&destination=${tripResult.destinationCoords.latitude},${tripResult.destinationCoords.longitude}&travelmode=${({ Walking: 'walking', Driving: 'driving', Cycling: 'bicycling', 'Two-wheeler': 'driving' })[tripResult.travelMode] || 'walking'}`
    : '#'

  // Forecast calculations
  const pmDelta = forecastResult ? forecastResult.predicted_pm25 - forecastResult.current_pm25 : 0
  const pmPercent = forecastResult && forecastResult.current_pm25 > 0 ? ((pmDelta / forecastResult.current_pm25) * 100).toFixed(1) : '0'

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand brand-button" onClick={() => { setActiveTab('routes'); resetTrip() }} aria-label="AIRGUARD home">
          <div className="brand-mark">A</div>
          <div>
            <div className="brand-name">AIRGUARD</div>
            <div className="brand-sub">Personal pollution intelligence</div>
          </div>
        </button>

        <div className="nav-tabs" role="tablist" aria-label="Main Navigation">
          <button
            role="tab"
            aria-selected={activeTab === 'routes'}
            className={`tab-btn ${activeTab === 'routes' ? 'active' : ''}`}
            onClick={() => setActiveTab('routes')}
          >
            Route Optimizer
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'forecast'}
            className={`tab-btn ${activeTab === 'forecast' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('forecast')
              if (!forecastResult) handleGetForecast(selectedStation)
            }}
          >
            3h PM2.5 Forecast
          </button>
        </div>

        <div className="topbar-actions">
          <div className="mode-switch" role="group" aria-label="Data mode">
            <button
              className={mode === 'demo' ? 'selected' : ''}
              onClick={() => {
                setMode('demo')
                setForecastError('')
                setForecastResult(makeDemoForecastResponse(selectedStation))
                resetTrip()
              }}
            >
              Demo
            </button>
            <button
              className={mode === 'live' ? 'selected live-selected' : ''}
              onClick={async () => {
                setMode('live')
                resetTrip()
                setForecastError('')
                const isOnline = await verifyBackend()
                if (isOnline && activeTab === 'forecast') {
                  handleGetForecast(selectedStation, 'live')
                }
              }}
            >
              Live API
            </button>
          </div>
          <div
            className="status-pill"
            onClick={() => verifyBackend()}
            style={{ cursor: 'pointer' }}
            title="Click to refresh backend connectivity status"
          >
            <span className={`status-dot ${mode === 'demo' ? 'online' : backendStatus}`} />
            {mode === 'demo' ? 'Demo Mode (Offline Ready)' : `Backend ${backendStatus}`}
          </div>
        </div>
      </header>

      <main>
        {activeTab === 'forecast' ? (
          <section className="forecast-layout">
            <div className="forecast-header">
              <div className="eyebrow">AIR QUALITY PREDICTIVE INTELLIGENCE</div>
              <h1>3-Hour Ahead <span>PM2.5 Forecast</span></h1>
              <p>
                Machine-learning prediction powered by a Random Forest model trained on historical Delhi monitoring observations. Forecasts PM2.5 concentrations 3 hours forward based on recent temporal lags and weather features.
              </p>
            </div>

            <div className="forecast-grid">
              <div className="forecast-card-main">
                <div className="card-heading">
                  <div>
                    <div className="card-kicker">MONITORING STATION</div>
                    <h2>Select Delhi Station</h2>
                  </div>
                  <div className="spark">⚡</div>
                </div>

                <label>
                  Station Name
                  <select
                    className="station-select"
                    value={selectedStation}
                    onChange={(e) => {
                      setSelectedStation(e.target.value)
                      handleGetForecast(e.target.value)
                    }}
                  >
                    {stations.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </label>

                <div style={{ marginTop: '14px' }}>
                  <span className="map-label">POPULAR DELHI STATIONS:</span>
                  <div className="quick-station-chips">
                    {DEFAULT_STATIONS.slice(0, 5).map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`station-chip ${selectedStation === s ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedStation(s)
                          handleGetForecast(s)
                        }}
                      >
                        {s.replace('Delhi - ', '')}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  style={{ marginTop: '24px' }}
                  className="primary-btn"
                  onClick={() => handleGetForecast(selectedStation)}
                  disabled={forecastLoading}
                >
                  {forecastLoading ? 'Calculating Forecast…' : 'Update 3h Forecast →'}
                </button>

                {forecastError && (
                  <div className="error-card" role="alert" style={{ marginTop: '18px' }}>
                    <strong>Forecast Error</strong>
                    <span>{forecastError}</span>
                  </div>
                )}

                <div className="prototype-warning-badge">
                  <strong>CRITICAL LIMITATION & PROTOTYPE NOTICE</strong>
                  This forecasting prototype evaluates historical observations (baseline: December 31, 2022). It serves as a proof-of-concept ML pipeline and does not depict current live atmospheric telemetry.
                </div>
              </div>

              <div className="forecast-card-results">
                <div className="card-heading">
                  <div>
                    <div className="card-kicker">PREDICTION RESULTS</div>
                    <h2>{forecastResult?.location || selectedStation}</h2>
                  </div>
                  <span className="status-pill">
                    {mode === 'demo' ? 'DEMO SIMULATION' : 'ML PIPELINE'}
                  </span>
                </div>

                {forecastResult ? (
                  <>
                    <div className="forecast-metrics">
                      <div className="forecast-metric-box">
                        <span className="metric-label">BASELINE PM2.5</span>
                        <div className="metric-val">
                          {forecastResult.current_pm25}
                          <span className="metric-unit">µg/m³</span>
                        </div>
                        <small style={{ color: '#7a8c84', fontSize: '10px' }}>Historical observation</small>
                      </div>

                      <div className="forecast-metric-box" style={{ borderColor: 'rgba(131,228,173,.3)' }}>
                        <span className="metric-label">3H FORECAST PM2.5</span>
                        <div className="metric-val" style={{ color: '#86e5af' }}>
                          {forecastResult.predicted_pm25}
                          <span className="metric-unit">µg/m³</span>
                        </div>
                        <small style={{ color: '#7a8c84', fontSize: '10px' }}>Random Forest model</small>
                      </div>

                      <div className="forecast-metric-box">
                        <span className="metric-label">3H DELTA</span>
                        <div className={`metric-val ${pmDelta > 0 ? 'trend-worse' : pmDelta < 0 ? 'trend-better' : 'trend-steady'}`}>
                          {pmDelta > 0 ? `+${pmDelta.toFixed(1)}` : pmDelta.toFixed(1)}
                          <span className="metric-unit">µg/m³</span>
                        </div>
                        <small style={{ color: '#7a8c84', fontSize: '10px' }}>{pmPercent}% shift</small>
                      </div>
                    </div>

                    <div className="forecast-meta-row">
                      <span>Baseline Observation Timestamp:</span>
                      <strong>{formatIsoTime(forecastResult.observation_time)}</strong>
                    </div>
                    <div className="forecast-meta-row">
                      <span>Forecast Target Timestamp (+3h):</span>
                      <strong>{formatIsoTime(forecastResult.prediction_time)}</strong>
                    </div>
                    <div className="forecast-meta-row">
                      <span>Prediction Horizon:</span>
                      <strong>180 minutes (3 hours)</strong>
                    </div>
                    <div className="forecast-meta-row">
                      <span>Predictor Architecture:</span>
                      <strong>RandomForestRegressor (13 input features)</strong>
                    </div>
                    <div className="forecast-meta-row">
                      <span>Telemetry Status:</span>
                      <strong style={{ color: '#ffd27a' }}>Historical Dataset Prototype (Non-Live)</strong>
                    </div>

                    <div className="advisory-box">
                      <h4>DEPARTURE & TRAVEL EXPOSURE ADVISORY</h4>
                      {pmDelta < -5 ? (
                        <p>
                          📉 <strong>Improving Air Quality Anticipated:</strong> Predicted PM2.5 decreases by {Math.abs(pmDelta).toFixed(1)} µg/m³ over the next 3 hours. If your trip is flexible, postponing outdoor commuting could substantially decrease cumulative lung exposure.
                        </p>
                      ) : pmDelta > 5 ? (
                        <p>
                          📈 <strong>Deteriorating Conditions Projected:</strong> PM2.5 is forecast to rise by {pmDelta.toFixed(1)} µg/m³ over the 3-hour window. Departing immediately or choosing enclosed transportation with filtration is recommended.
                        </p>
                      ) : (
                        <p>
                          ➡️ <strong>Stable Ambient Conditions:</strong> Particulate levels are projected to remain steady over the 3-hour forecast horizon. Route selection remains the primary factor for minimizing exposure.
                        </p>
                      )}
                    </div>
                  </>
                ) : (
                  <div style={{ padding: '40px 0', textAlign: 'center', color: '#7a8c84' }}>
                    Select a station to calculate the 3-hour PM2.5 forecast.
                  </div>
                )}
              </div>
            </div>
          </section>
        ) : !tripResult ? (
          <section className="hero-layout">
            <div className="hero-copy">
              <div className="eyebrow">SMARTER TRAVEL. CLEANER AIR.</div>
              <h1>Know the air<br /><span>before you travel.</span></h1>
              <p className="hero-text">
                AIRGUARD compares route options using air-quality observations and travel time, then explains the trade-off so you can make a more informed journey decision.
              </p>
              <div className="mini-stats">
                <div><strong>Route AQI</strong><span>Along candidate paths</span></div>
                <div><strong>3 preferences</strong><span>Faster · Balanced · Cleaner</span></div>
                <div><strong>Explainable</strong><span>See why a route was chosen</span></div>
              </div>
              {mode === 'live' && (
                <div className="mode-info">
                  <strong>Live API mode</strong>
                  <span>Uses the FastAPI backend. Known demo locations (DTU, Rohini, Connaught Place, Noida Sector 62, India Gate, Saket and Cyber City) work without geocoding; other addresses use the Google Geocoding API.</span>
                  <code>{API_BASE}</code>
                </div>
              )}
            </div>

            <div className="trip-card">
              <div className="card-heading">
                <div><div className="card-kicker">PLAN YOUR JOURNEY</div><h2>Analyze your exposure</h2></div>
                <div className="spark">✦</div>
              </div>
              <form onSubmit={analyzeTrip}>
                <label>Starting point
                  <div className="input-wrap"><span className="origin-dot">●</span><input value={form.start} onChange={(event) => update('start', event.target.value)} placeholder="e.g. DTU or 28.7501, 77.1177" autoComplete="street-address" /></div>
                </label>
                <label>Destination
                  <div className="input-wrap"><span className="destination-dot">●</span><input value={form.destination} onChange={(event) => update('destination', event.target.value)} placeholder="e.g. Rohini or latitude, longitude" autoComplete="off" /></div>
                </label>
                <div className="two-col">
                  <label>Travel mode
                    <select value={form.travelMode} onChange={(event) => update('travelMode', event.target.value)}>
                      <option>Walking</option><option>Driving</option><option>Cycling</option><option>Two-wheeler</option>
                    </select>
                  </label>
                  <label>Route priority
                    <select value={form.preference} onChange={(event) => update('preference', event.target.value)}>
                      <option value="faster">Faster</option><option value="balanced">Balanced</option><option value="cleaner">Cleaner air</option>
                    </select>
                  </label>
                </div>
                <button className="primary-btn" disabled={loading}>{loading ? 'Analyzing routes…' : mode === 'demo' ? 'Try demo analysis →' : 'Analyze live routes →'}</button>
              </form>
              {error && <div className="error-card" role="alert"><strong>Could not analyze this trip</strong><span>{error}</span>{mode === 'live' && backendStatus === 'offline' && <small>Make sure the backend is running on port 8000. Instructions are in the project README.</small>}</div>}
              <div className="privacy-note">
  {mode === 'demo'
    ? 'DEMO MODE: Illustrative sample routes, travel times, and pollution values. They are not calculated for your selected journey and are not live measurements.'
    : 'Coordinates are sent to your backend to calculate routes'}
</div>
              {mode === 'live' && <div className="location-hint">Tip: try DTU → Rohini first. For a custom address, enable Google Geocoding API on the same Google Cloud project.</div>}
            </div>
          </section>
        ) : (
          <section className="results-page">
            <button className="back-btn" onClick={resetTrip}>← Plan another trip</button>
            <div className="results-head">
              <div>
                <div className="eyebrow">{tripResult.source === 'live' ? 'LIVE TRIP ANALYSIS' : 'DEMO TRIP ANALYSIS'}</div>
                <h1>{tripResult.start} <span>→</span> {tripResult.destination}</h1>
                <p>{tripResult.travelMode} · {tripResult.preference.charAt(0).toUpperCase() + tripResult.preference.slice(1)} priority · {tripResult.source === 'live' ? 'Backend response' : 'Synthetic sample response'}</p>
              </div>
              <div className={`risk-card ${categoryTone(recommendedRoute?.air_quality_category)}`}>
                <span>AVERAGE AIR QUALITY</span>
                <strong>{recommendedRoute?.air_quality_category || 'Unavailable'}</strong>
                <small>{recommendedRoute?.average_aqi != null ? `Average AQI ${Number(recommendedRoute.average_aqi).toFixed(1)}` : 'AQI data unavailable'}</small>
              </div>
            </div>

            {tripResult.source === 'synthetic' && <div className="demo-notice"><strong>DEMO DATA</strong><span>These values are synthetic examples, not live measurements. Switch to Live API mode to use the backend.</span></div>}

{allRoutes.length === 1 && (
  <div className="limitations-box">
    <strong>Only one route available</strong>
    <p>
      The routing provider returned only one candidate route.
      AIRGUARD cannot compare alternatives or confirm that this
      route has lower pollution exposure than other routes.
    </p>
  </div>
)}

            <div className="metrics-row">
              <div className="metric"><span>AVERAGE AQI</span><strong>{recommendedRoute?.average_aqi != null ? Number(recommendedRoute.average_aqi).toFixed(1) : '—'}</strong><small>{recommendedRoute?.air_quality_category || 'No reading'}</small></div>
              <div className="metric"><span>EXPOSURE INDEX</span><strong>{recommendedRoute?.estimated_exposure_score != null ? Number(recommendedRoute.estimated_exposure_score).toFixed(1) : '—'}</strong><small>AQI × travel hours</small></div>
              <div className="metric"><span>ROUTES COMPARED</span><strong>{allRoutes.length}</strong><small>{allRoutes.length === 1 ? 'candidate route' : 'candidate routes'}</small></div>
              <div className="metric good"><span>RECOMMENDED TIME</span><strong>{recommendedRoute?.duration_formatted || '—'}</strong><small>{recommendedRoute?.distance_formatted || 'Distance unavailable'}</small></div>
            </div>

            <div className="content-grid">
              <div className="map-card">
                <div className="map-top"><div><span className="map-label">ROUTE GEOMETRY</span><h3>Compare candidate paths</h3></div><span className="map-chip">Provider route lines</span></div>
                <div className="fake-map">
                  <div className="map-grid" />
                  {mapShape ? (
                    <svg className="route-svg" viewBox={`0 0 ${mapShape.width} ${mapShape.height}`} role="img" aria-label="Route geometry preview">
                      {mapShape.decoded.map(({ route, points }, index) => {
                        const plotted = points.map(mapShape.project).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
                        const isRecommended = route.route_id === recommendedRoute?.route_id
                        return <polyline key={route.route_id || index} points={plotted} fill="none" stroke={isRecommended ? '#83e4ad' : ['#ef8b74', '#8eaaa0', '#74b8ed'][index % 3]} strokeWidth={isRecommended ? 7 : 4} strokeLinecap="round" strokeLinejoin="round" opacity={isRecommended ? 1 : 0.78} />
                      })}
                      <circle cx={mapShape.project(mapShape.decoded[0].points[0])[0]} cy={mapShape.project(mapShape.decoded[0].points[0])[1]} r="9" fill="#eaf7ef" stroke="#07110e" strokeWidth="3" />
                      <circle cx={mapShape.project(mapShape.decoded[0].points.at(-1))[0]} cy={mapShape.project(mapShape.decoded[0].points.at(-1))[1]} r="9" fill="#eaf7ef" stroke="#07110e" strokeWidth="3" />
                    </svg>
                  ) : <div className="map-empty">The backend did not return encoded route geometry for this result.</div>}
                  <div className="map-legend"><span><i className="legend-green" /> Recommended</span><span><i className="legend-red" /> Alternative</span></div>
                </div>
                <div className="map-caption">Schematic route-shape preview from provider polylines; not a street basemap.</div>
                <a className="maps-link" href={mapsUrl} target="_blank" rel="noreferrer">Open trip in Google Maps ↗</a>
              </div>

              <div className="recommend-card">
                <div className="recommend-icon">✓</div>
                <div className="map-label">BACKEND RECOMMENDATION</div>
                <h3>{displayRouteName(recommendedRoute || {}, 0)}</h3>
                <p>{liveData.summary || 'The backend selected this route according to your chosen preference.'}</p>
                
<div className="reduction">
  <strong>{exposureComparison.headline}</strong>
  <span>{exposureComparison.label}</span>
</div>

                <div className="reason-line"><span>Travel time</span><strong>{recommendedRoute?.duration_formatted || 'Unavailable'}</strong></div>
                <div className="reason-line"><span>Distance</span><strong>{recommendedRoute?.distance_formatted || 'Unavailable'}</strong></div>
               
<div className="reason-line">
  <span>Air quality data</span>
  <strong>{recommendedRoute?.exposure_status || 'Unavailable'}</strong>
</div>
<div className="reason-line">
  <span>Data source</span>
  <strong>
    {tripResult.source === 'synthetic'
      ? 'Demo sample'
      : recommendedRoute?.average_aqi != null
        ? 'Open-Meteo model estimate'
        : 'Unavailable'}
  </strong>
</div>


                <div className="route-forecast-callout">
                  <div className="route-forecast-callout-header">
                    <span className="map-label">DEPARTURE TIMING & FORECAST</span>
                    <button
                      type="button"
                      className="station-chip selected"
                      style={{ fontSize: '10px', padding: '3px 8px' }}
                      onClick={() => {
                        setActiveTab('forecast')
                        handleGetForecast('Delhi - DTU')
                      }}
                    >
                      View 3h PM2.5 Forecast ↗
                    </button>
                  </div>
                  <small style={{ color: '#9db2a8', display: 'block', lineHeight: 1.5 }}>
                    Station-level 3-hour forecasts can help optimize your departure time. Check the ML forecast tab to see if ambient PM2.5 is projected to decrease.
                  </small>
                </div>
              </div>
            </div>

            <div className="section-title"><div><div className="map-label">ROUTE COMPARISON</div><h2>Compare your options</h2></div><span>Lower exposure index is better when data is available.</span></div>
            <div className="routes-grid route-grid-dynamic">
              {allRoutes.map((route, index) => {
                const routeName = displayRouteName(route, index)
                const score = route.estimated_exposure_score
                const exposureValues = allRoutes.map((candidate) => candidate.estimated_exposure_score).filter((value) => Number.isFinite(value))
                const maxScore = exposureValues.length ? Math.max(...exposureValues) : 0
                const relativeBar = Number.isFinite(score) && maxScore > 0 ? Math.max(4, (score / maxScore) * 100) : 0
                return (
                  <article className={`route-card ${route.is_recommended || route.route_id === recommendedRoute?.route_id ? 'recommended' : ''}`} key={route.route_id || index}>
                    <div className="route-card-top"><div><span className="route-name">{routeName}</span><span className="route-label">{route.is_recommended || route.route_id === recommendedRoute?.route_id ? 'Backend recommended' : (route.air_quality_category || 'Alternative option')}</span></div><div className="route-score"><strong>{score != null ? Number(score).toFixed(1) : '—'}</strong><span>{score != null ? 'AQI·h' : 'No exposure data'}</span></div></div>
                    <div className="route-bar"><span style={{ width: `${relativeBar}%` }} /></div>
                    <div className="route-meta"><span>◷ {route.duration_formatted || 'Time n/a'}</span><span>{route.distance_formatted || 'Distance n/a'}</span></div>
                    <div className="route-detail-row"><span>Average AQI</span><strong>{route.average_aqi != null ? Number(route.average_aqi).toFixed(1) : 'Unavailable'}</strong></div>
                    <div className="route-detail-row"><span>Coverage</span><strong className={route.exposure_status === 'ESTIMATED' ? 'coverage-good' : 'coverage-limited'}>{route.exposure_status || 'Unavailable'}</strong></div>
                  </article>
                )
              })}
            </div>

            {(liveData.data_limitations || []).length > 0 && <div className="limitations-box"><strong>Data coverage notes</strong><ul>{liveData.data_limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          </section>
        )}
      </main>

      <footer><span>AIRGUARD</span><span>Environmental Hacks · Bharat Builds Tour 2026</span><span>Air-quality estimates are informational, not medical advice.</span></footer>
    </div>
  )
}

export default App
