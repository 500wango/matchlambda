/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";

// Resolve the configured API origin so connect-src can name it exactly instead
// of allowing an arbitrary "https:" source. NEXT_PUBLIC_API_URL is inlined at
// build time for both `next build` and `next start`.
function resolveApiOrigin() {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (!configured) return null;
  try {
    return new URL(configured).origin;
  } catch {
    return null;
  }
}

const apiOrigin = resolveApiOrigin();

// Local development hosts. Relative same-origin requests are already covered
// by "'self'" (the app derives `${window.location.origin}/v1` on HTTPS).
const connectSrc = Array.from(
  new Set([
    "'self'",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    apiOrigin,
  ].filter(Boolean))
).join(" ");

// Next needs inline scripts (hydration/RSC payloads) and inline styles, so
// 'unsafe-inline' stays. 'unsafe-eval' is only needed by the dev Fast Refresh
// runtime; production no longer requires it.
const scriptSrc = ["'self'", "'unsafe-inline'", isProd ? null : "'unsafe-eval'"]
  .filter(Boolean)
  .join(" ");

const csp = [
  "default-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  `script-src ${scriptSrc}`,
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
