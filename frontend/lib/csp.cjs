/**
 * Content-Security-Policy builder.
 *
 * CommonJS because two very different consumers need the exact same policy and
 * neither can import the other's module system:
 *   - next.config.js        -> sends it as a response header (local + Docker)
 *   - scripts/write-headers -> writes it into out/_headers for Cloudflare Pages
 *
 * Keeping one builder means the static export and the Node-served build cannot
 * drift into two different policies.
 */

/** Origin (scheme://host[:port]) of the configured API, or null if unusable. */
function resolveApiOrigin(apiUrl) {
  if (!apiUrl) return null;
  try {
    return new URL(apiUrl).origin;
  } catch {
    return null;
  }
}

function buildConnectSrc(apiUrl, isProd) {
  const apiOrigin = resolveApiOrigin(apiUrl);
  const sources = [
    "'self'",
    // Loopback origins are only reachable from a developer's own browser, so
    // they are dropped from a production policy.
    isProd ? null : "http://localhost:8000",
    isProd ? null : "http://127.0.0.1:8000",
    apiOrigin,
  ];
  return Array.from(new Set(sources.filter(Boolean))).join(" ");
}

function buildScriptSrc(isProd) {
  // Next needs inline scripts (hydration/RSC payloads) and inline styles, so
  // 'unsafe-inline' stays. 'unsafe-eval' is only needed by the dev Fast Refresh
  // runtime; production no longer requires it.
  return ["'self'", "'unsafe-inline'", isProd ? null : "'unsafe-eval'"]
    .filter(Boolean)
    .join(" ");
}

/**
 * @param {{ apiUrl?: string, isProd: boolean }} options
 * @returns {string} a complete CSP header value
 */
function buildCsp({ apiUrl, isProd }) {
  return [
    "default-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    `script-src ${buildScriptSrc(isProd)}`,
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${buildConnectSrc(apiUrl, isProd)}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

/** Headers that are not the CSP but travel with it. */
const SECURITY_HEADERS = [
  ["X-Frame-Options", "DENY"],
  ["Referrer-Policy", "strict-origin-when-cross-origin"],
  ["X-Content-Type-Options", "nosniff"],
];

module.exports = { buildCsp, resolveApiOrigin, SECURITY_HEADERS };
