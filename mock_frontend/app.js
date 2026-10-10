/**
 * AIRGUARD — Frontend Application Logic
 *
 * Implements Mode A (Mock Data Mode) and Mode B (Live FastAPI Integration Mode)
 * with robust schema validation, error handling, and inspection tools.
 */

import { MOCK_SCENARIOS } from "./mock_data.js";

// State
let currentMode = "mock"; // 'mock' | 'live'
let selectedScenarioKey = "delhi_noida_3way";
let lastRequestPayload = null;
let lastResponseData = null;

// DOM Elements
const btnModeMock = document.getElementById("btnModeMock");
const btnModeLive = document.getElementById("btnModeLive");
const modeBanner = document.getElementById("modeBanner");
const modePill = document.getElementById("modePill");

const scenarioChips = document.querySelectorAll(".chip-btn");
const routePlanForm = document.getElementById("routePlanForm");
const endpointUrlInput = document.getElementById("endpointUrl");
const originLatInput = document.getElementById("originLat");
const originLngInput = document.getElementById("originLng");
const destLatInput = document.getElementById("destLat");
const destLngInput = document.getElementById("destLng");
const preferenceSelect = document.getElementById("preferenceSelect");
const travelModeSelect = document.getElementById("travelModeSelect");
const computeAlternativesCheckbox = document.getElementById("computeAlternativesCheckbox");

const btnSubmitPlan = document.getElementById("btnSubmitPlan");
const btnResetForm = document.getElementById("btnResetForm");
const btnCheckHealth = document.getElementById("btnCheckHealth");
const healthDot = document.getElementById("healthDot");
const healthStatusText = document.getElementById("healthStatusText");

const resultsContainer = document.getElementById("resultsContainer");
const emptyState = document.getElementById("emptyState");
const loadingState = document.getElementById("loadingState");
const loadingText = document.getElementById("loadingText");
const errorBanner = document.getElementById("errorBanner");
const activeResults = document.getElementById("activeResults");
const summaryBanner = document.getElementById("summaryBanner");
const summaryText = document.getElementById("summaryText");
const limitationsBox = document.getElementById("limitationsBox");
const routesList = document.getElementById("routesList");
const resultsDataSourceBadge = document.getElementById("resultsDataSourceBadge");

const debugToggleBtn = document.getElementById("debugToggleBtn");
const debugContent = document.getElementById("debugContent");
const debugChevron = document.getElementById("debugChevron");
const debugRequestPayload = document.getElementById("debugRequestPayload");
const debugResponseJson = document.getElementById("debugResponseJson");
const copyJsonBtn = document.getElementById("copyJsonBtn");

// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------
function init() {
  bindEvents();
  loadScenario(selectedScenarioKey);
  checkBackendHealth();
}

// -----------------------------------------------------------------------------
// Event Bindings
// -----------------------------------------------------------------------------
function bindEvents() {
  btnModeMock.addEventListener("click", () => setMode("mock"));
  btnModeLive.addEventListener("click", () => setMode("live"));

  scenarioChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      scenarioChips.forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      const scenarioKey = chip.getAttribute("data-scenario");
      selectedScenarioKey = scenarioKey;
      loadScenario(scenarioKey);
    });
  });

  routePlanForm.addEventListener("submit", handleFormSubmit);
  btnResetForm.addEventListener("click", handleReset);
  btnCheckHealth.addEventListener("click", checkBackendHealth);

  debugToggleBtn.addEventListener("click", () => {
    const isHidden = debugContent.style.display === "none";
    debugContent.style.display = isHidden ? "block" : "none";
    debugChevron.textContent = isHidden ? "▲" : "▼";
  });

  copyJsonBtn.addEventListener("click", handleCopyJson);
}

// -----------------------------------------------------------------------------
// Mode Switcher (Mode A vs Mode B)
// -----------------------------------------------------------------------------
function setMode(mode) {
  currentMode = mode;

  if (mode === "mock") {
    btnModeMock.classList.add("active");
    btnModeLive.classList.remove("active", "live");
    btnModeMock.setAttribute("aria-pressed", "true");
    btnModeLive.setAttribute("aria-pressed", "false");

    modeBanner.className = "mode-indicator-bar mode-mock";
    modeBanner.innerHTML = `
      <div>
        <strong>Mode A Active (Deterministic Mock Data):</strong> Testing with offline synthetic datasets matching backend Pydantic schemas without invoking paid APIs.
      </div>
      <span class="status-pill" id="modePill">MOCK DATA</span>
    `;
    btnSubmitPlan.textContent = "Run Route Analysis (Mock)";
  } else {
    btnModeLive.classList.add("active", "live");
    btnModeMock.classList.remove("active");
    btnModeMock.setAttribute("aria-pressed", "false");
    btnModeLive.setAttribute("aria-pressed", "true");

    modeBanner.className = "mode-indicator-bar mode-live";
    modeBanner.innerHTML = `
      <div>
        <strong>Mode B Active (Live Integration Mode):</strong> Submits requests to the local FastAPI backend, which invokes the live Google Routes & Air Quality APIs.
      </div>
      <span class="status-pill" id="modePill">LIVE BACKEND</span>
    `;
    btnSubmitPlan.textContent = "Query Live Backend API";
  }
}

// -----------------------------------------------------------------------------
// Scenario Loading
// -----------------------------------------------------------------------------
function loadScenario(scenarioKey) {
  const scenario = MOCK_SCENARIOS[scenarioKey];
  if (!scenario) return;

  const req = scenario.request;
  originLatInput.value = req.origin.latitude;
  originLngInput.value = req.origin.longitude;
  destLatInput.value = req.destination.latitude;
  destLngInput.value = req.destination.longitude;
  preferenceSelect.value = req.preference;
  travelModeSelect.value = req.travel_mode;
  computeAlternativesCheckbox.checked = req.compute_alternatives;
}

// -----------------------------------------------------------------------------
// Form Submission & Request Execution
// -----------------------------------------------------------------------------
async function handleFormSubmit(e) {
  e.preventDefault();

  // 1. Gather & Validate inputs
  const originLat = parseFloat(originLatInput.value);
  const originLng = parseFloat(originLngInput.value);
  const destLat = parseFloat(destLatInput.value);
  const destLng = parseFloat(destLngInput.value);

  if (isNaN(originLat) || isNaN(originLng) || isNaN(destLat) || isNaN(destLng)) {
    showError("Please enter valid decimal coordinates for origin and destination.");
    return;
  }

  if (originLat < -90 || originLat > 90 || destLat < -90 || destLat > 90) {
    showError("Latitude must be between -90.0 and 90.0 degrees.");
    return;
  }

  if (originLng < -180 || originLng > 180 || destLng < -180 || destLng > 180) {
    showError("Longitude must be between -180.0 and 180.0 degrees.");
    return;
  }

  if (Math.abs(originLat - destLat) < 1e-6 && Math.abs(originLng - destLng) < 1e-6) {
    showError("Validation Error: Origin and destination coordinates must be distinct locations.");
    return;
  }

  const payload = {
    origin: { latitude: originLat, longitude: originLng },
    destination: { latitude: destLat, longitude: destLng },
    preference: preferenceSelect.value,
    travel_mode: travelModeSelect.value,
    compute_alternatives: computeAlternativesCheckbox.checked,
  };

  lastRequestPayload = payload;
  hideError();
  showLoading();

  if (currentMode === "mock") {
    await executeMockMode(payload);
  } else {
    await executeLiveMode(payload);
  }
}

// -----------------------------------------------------------------------------
// Mode A: Mock Mode Execution
// -----------------------------------------------------------------------------
async function executeMockMode(payload) {
  loadingText.textContent = "Loading synthetic test scenario...";

  // Brief synthetic delay to verify loading state UX
  await new Promise((r) => setTimeout(r, 350));

  let scenario = MOCK_SCENARIOS[selectedScenarioKey];
  if (!scenario) {
    scenario = MOCK_SCENARIOS.delhi_noida_3way;
  }

  const responseData = JSON.parse(JSON.stringify(scenario.response));
  // Adjust response preference to match user's chosen form preference
  responseData.preference = payload.preference;

  lastResponseData = responseData;
  hideLoading();
  renderResults(responseData, "MODE A — SYNTHETIC MOCK DATA");
}

// -----------------------------------------------------------------------------
// Mode B: Live Backend API Execution
// -----------------------------------------------------------------------------
async function executeLiveMode(payload) {
  const url = endpointUrlInput.value.trim() || "http://localhost:8000/routes/pollution-aware";
  loadingText.textContent = `Connecting to FastAPI backend (${url})...`;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const detail = data?.detail || `HTTP ${res.status}: ${res.statusText}`;
      let guidance = "";
      if (res.status === 503) {
        guidance = " (Upstream credentials missing: Configure GOOGLE_MAPS_API_KEY or GOOGLE_ROUTES_API_KEY in backend/.env).";
      } else if (res.status === 504) {
        guidance = " (Upstream Google Routes service timed out. Try again shortly).";
      } else if (res.status === 502) {
        guidance = " (Bad Gateway: External Google service returned an error).";
      } else if (res.status === 404) {
        guidance = " (No routes found between origin and destination coordinates).";
      }
      throw new Error(`${detail}${guidance}`);
    }

    lastResponseData = data;
    hideLoading();
    renderResults(data, "MODE B — LIVE BACKEND API");
  } catch (err) {
    hideLoading();
    let msg = err.message;
    if (err.name === "TypeError" && msg.includes("Failed to fetch")) {
      msg = `Failed to connect to backend at ${url}. Ensure the FastAPI server is running with 'uvicorn app.main:app --reload' and CORS allows this origin.`;
    }
    showError(msg);
  }
}

// -----------------------------------------------------------------------------
// Render Results
// -----------------------------------------------------------------------------
function renderResults(data, sourceLabel) {
  emptyState.style.display = "none";
  activeResults.style.display = "block";
  resultsDataSourceBadge.textContent = sourceLabel;
  resultsDataSourceBadge.style.color = currentMode === "live" ? "var(--accent-emerald)" : "var(--accent-blue)";

  // Summary Banner
  summaryText.innerHTML = `<strong>Selection Rationale:</strong> ${data.summary}`;

  // Limitations Banner
  if (data.data_limitations && data.data_limitations.length > 0) {
    limitationsBox.style.display = "block";
    limitationsBox.innerHTML = `<strong>Coverage Notes / Disclaimers:</strong><ul style="margin: 4px 0 0 16px;">${data.data_limitations.map((l) => `<li>${l}</li>`).join("")}</ul>`;
  } else {
    limitationsBox.style.display = "none";
  }

  // Render Routes
  const allRoutes = [data.recommended_route, ...(data.alternative_routes || [])];

  routesList.innerHTML = allRoutes
    .map((route) => createRouteCardHtml(route, route.is_recommended))
    .join("");

  // Update Debug Payloads
  debugRequestPayload.textContent = JSON.stringify(lastRequestPayload, null, 2);
  debugResponseJson.textContent = JSON.stringify(data, null, 2);
}

function createRouteCardHtml(route, isRecommended) {
  const category = route.air_quality_category || "Unrated";
  const catClass = `aqi-${category.replace(/\s+/g, "-")}`;
  const avgAqiDisplay = route.average_aqi !== null && route.average_aqi !== undefined ? route.average_aqi : "Unavailable";
  const exposureScoreDisplay = route.estimated_exposure_score !== null && route.estimated_exposure_score !== undefined ? route.estimated_exposure_score : "Unavailable";
  const combinedScoreDisplay = route.score !== null && route.score !== undefined ? route.score.toFixed(3) : "N/A";

  return `
    <article class="route-card ${isRecommended ? "is-recommended" : ""}" aria-label="${route.route_id}">
      <div class="route-header">
        <div class="route-title-group">
          <div class="route-name">
            <span>${route.route_id}</span>
            ${isRecommended ? '<span class="badge-recommended">★ Recommended</span>' : '<span class="badge-alternative">Alternative</span>'}
          </div>
          ${route.description ? `<div class="route-description">${route.description}</div>` : ""}
        </div>
        ${route.air_quality_category ? `<span class="aqi-pill ${catClass}">${route.air_quality_category}</span>` : ""}
      </div>

      <div class="metrics-row">
        <div class="metric-cell">
          <div class="metric-value">${route.duration_formatted}</div>
          <div class="metric-label">Travel Time</div>
        </div>
        <div class="metric-cell">
          <div class="metric-value">${route.distance_formatted}</div>
          <div class="metric-label">Distance</div>
        </div>
        <div class="metric-cell">
          <div class="metric-value" style="color: ${getAqiColor(route.average_aqi)};">${avgAqiDisplay}</div>
          <div class="metric-label">Avg AQI</div>
        </div>
        <div class="metric-cell">
          <div class="metric-value">${exposureScoreDisplay}</div>
          <div class="metric-label">Exposure Score</div>
        </div>
        <div class="metric-cell">
          <div class="metric-value">${combinedScoreDisplay}</div>
          <div class="metric-label">Rank Score</div>
        </div>
      </div>

      <div class="route-footer-meta">
        <div>
          <span>Exposure Status: <strong>${route.exposure_status}</strong></span>
          <span style="margin: 0 6px;">•</span>
          <span>Sampled Waypoints: <strong>${route.waypoints_sampled}</strong></span>
        </div>
        <div>
          ${route.polyline ? `<span title="Encoded Google polyline length: ${route.polyline.length} chars">Geometry Encoded ✓</span>` : "<span>No Polyline</span>"}
        </div>
      </div>
    </article>
  `;
}

function getAqiColor(aqi) {
  if (aqi === null || aqi === undefined) return "var(--text-dim)";
  if (aqi <= 50) return "#34d399";
  if (aqi <= 100) return "#fbbf24";
  if (aqi <= 150) return "#fb923c";
  if (aqi <= 200) return "#f87171";
  if (aqi <= 300) return "#c084fc";
  return "#fca5a5";
}

// -----------------------------------------------------------------------------
// UI State Helpers
// -----------------------------------------------------------------------------
function showLoading() {
  emptyState.style.display = "none";
  activeResults.style.display = "none";
  loadingState.style.display = "block";
  btnSubmitPlan.disabled = true;
}

function hideLoading() {
  loadingState.style.display = "none";
  btnSubmitPlan.disabled = false;
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.style.display = "block";
  errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideError() {
  errorBanner.style.display = "none";
  errorBanner.textContent = "";
}

function handleReset() {
  hideError();
  activeResults.style.display = "none";
  emptyState.style.display = "block";
  resultsDataSourceBadge.textContent = "No data loaded";
  resultsDataSourceBadge.style.color = "var(--text-muted)";
  loadScenario("delhi_noida_3way");
  selectedScenarioKey = "delhi_noida_3way";
  scenarioChips.forEach((c) => c.classList.remove("selected"));
  document.getElementById("scenarioDelhiNoida").classList.add("selected");
}

function handleCopyJson() {
  const content = `REQUEST:\n${debugRequestPayload.textContent}\n\nRESPONSE:\n${debugResponseJson.textContent}`;
  navigator.clipboard.writeText(content).then(() => {
    copyJsonBtn.textContent = "Copied!";
    setTimeout(() => {
      copyJsonBtn.textContent = "Copy JSON";
    }, 1500);
  });
}

// -----------------------------------------------------------------------------
// Backend Health Probe
// -----------------------------------------------------------------------------
async function checkBackendHealth() {
  healthDot.className = "health-dot checking";
  healthStatusText.textContent = "Checking backend status...";

  try {
    const res = await fetch("http://localhost:8000/health", { method: "GET" });
    if (res.ok) {
      const data = await res.json();
      healthDot.className = "health-dot online";
      healthStatusText.textContent = `Backend online (${data.app || "AIRGUARD"}, ${data.environment || "dev"})`;
    } else {
      healthDot.className = "health-dot offline";
      healthStatusText.textContent = `Backend returned HTTP ${res.status}`;
    }
  } catch (err) {
    healthDot.className = "health-dot offline";
    healthStatusText.textContent = "Backend offline (Start uvicorn on port 8000)";
  }
}

// Kick off initialization
document.addEventListener("DOMContentLoaded", init);
