const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  /**
   * @param {number} status   HTTP status code
   * @param {string} message  Human-readable message
   * @param {object} data     Full parsed JSON body from the response
   */
  constructor(status, message, data = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

// Internal helper
async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  let data
  try {
    data = await response.json()
  } catch {
    data = {}
  }

  if (!response.ok) {
    throw new ApiError(response.status, data.error ?? 'An unexpected error occurred.', data)
  }

  return data
}

// Public API
/**
 * POST /api/shorten
 * @param {string} url  The long URL to shorten.
 * @returns {Promise<{ alias: string, short_url: string, original_url: string }>}
 * @throws {ApiError}
 */
export async function shortenUrl(url, customAlias) {
  const payload = { url }
  if (customAlias?.trim()) {
    payload.custom_alias = customAlias.trim()
  }

  return request('/api/shorten', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * GET /api/urls
 * @returns {Promise<{ urls: Array }>}
 * @throws {ApiError}
 */
export async function fetchAllUrls() {
  const res = await fetch('/api/urls');
  const data = await res.json();
  if (!res.ok) throw new ApiError(res.status, data.error ?? "Failed to load URLs.", data);
  return data.urls;
}

/**
 * GET /api/urls/:alias/analytics
 * @param {string} alias
 * @returns {Promise<{ alias: string, analytics: Array }>}
 * @throws {ApiError}
 */
export async function fetchAnalytics(alias) {
  const res = await fetch(`/api/analytics/${encodeURIComponent(alias)}`);
  const data = await res.json();
  if (!res.ok) throw new ApiError(res.status, data.error ?? "Failed to load analytics.", data);
  return data;
}