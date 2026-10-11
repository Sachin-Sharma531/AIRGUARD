/**
 * AIRGUARD Frontend API Client
 *
 * Centralized API client for communicating with the AIRGUARD FastAPI backend.
 * Handles environment-based URL configuration (VITE_API_BASE_URL),
 * URL path normalization (preventing duplicate or missing slashes),
 * and actionable error reporting distinguishing network/connection issues from HTTP errors.
 */

/**
 * Returns the configured backend API base URL from the environment.
 * Strips any trailing slashes to guarantee clean endpoint concatenation.
 */
export function getApiBaseUrl() {
  const envUrl = (import.meta.env.VITE_API_BASE_URL || '').trim()
  return envUrl.replace(/\/+$/, '')
}

export const API_BASE = getApiBaseUrl()

/**
 * Constructs a normalized target URL for a given backend endpoint.
 *
 * @param {string} endpoint - API path, e.g. '/health' or '/routes/pollution-aware'
 * @returns {string} Fully qualified URL or clean relative path
 */
export function buildApiUrl(endpoint) {
  if (!endpoint || typeof endpoint !== 'string') {
    throw new Error('A valid endpoint path string is required.')
  }

  // Ensure endpoint always starts with exactly one leading slash
  const cleanEndpoint = '/' + endpoint.replace(/^\/+/, '')
  const base = getApiBaseUrl()

  if (base) {
    return `${base}${cleanEndpoint}`
  }

  // If in production and no VITE_API_BASE_URL was provided at build time,
  // fail with a clear, actionable error rather than silently making requests to localhost.
  if (import.meta.env.PROD) {
    throw new Error(
      'VITE_API_BASE_URL is not configured. In AWS Amplify Hosting, configure VITE_API_BASE_URL in App Settings > Environment Variables (e.g. https://ai-2b2d0254201647a5aa94f05d776c8c29.ecs.ap-southeast-2.on.aws) and redeploy.'
    )
  }

  // In local development without an explicit VITE_API_BASE_URL,
  // return the relative endpoint so it routes through the Vite dev proxy.
  return cleanEndpoint
}

/**
 * Centralized fetch helper for all backend requests.
 *
 * Note on error handling:
 * - Network failures (connection refused, DNS failure, CORS block, timeout) cause fetch() to throw.
 *   These are caught, tagged with `isNetworkError = true`, and re-thrown with actionable diagnostics.
 * - HTTP responses (e.g. 200, 404, 500, 502) resolve successfully and return the Response object,
 *   allowing callers to inspect `response.status`, `response.ok`, and parse JSON error bodies.
 * - No automatic retry to localhost is performed, preventing duplicate requests and confusing console CORS errors.
 *
 * @param {string} endpoint - Relative API endpoint path
 * @param {RequestInit} [options={}] - Fetch configuration options
 * @returns {Promise<Response>} Fetch Response object
 */
export async function apiFetch(endpoint, options = {}) {
  const targetUrl = buildApiUrl(endpoint)

  try {
    const response = await fetch(targetUrl, options)
    return response
  } catch (err) {
    const base = getApiBaseUrl()
    const errorMsg = base
      ? `Network error: Unable to connect to backend at ${targetUrl} (${err.message}). Verify backend service health, network reachability, and CORS configuration.`
      : `Network error: Failed to reach ${targetUrl} via local Vite proxy (${err.message}). Ensure the backend is running on port 8000 or set VITE_API_BASE_URL.`

    const enhancedError = new Error(errorMsg)
    enhancedError.cause = err
    enhancedError.isNetworkError = true
    enhancedError.targetUrl = targetUrl
    throw enhancedError
  }
}
