const { buildCsp, SECURITY_HEADERS } = require("./lib/csp.cjs");

/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";

// Cloudflare Pages serves a static bundle built with `output: "export"`. That
// bundle has no Node server, so `headers()` cannot run; the identical policy is
// written into out/_headers by scripts/write-headers.cjs instead. Build it with
// `npm run build:static`.
const isStaticExport = process.env.NEXT_STATIC_EXPORT === "1";

// NEXT_PUBLIC_API_URL is inlined at build time and also names the single origin
// connect-src allows, so a wrong value narrows the policy rather than silently
// widening it to "any https:".
const csp = buildCsp({
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  isProd: isProd || isStaticExport,
});

const nextConfig = isStaticExport
  ? {
      output: "export",
      // next/image's optimizer requires a server, which an export does not
      // have. The app uses no next/image today; leaving this off would turn any
      // future <Image> into a runtime 404 rather than a build-time error.
      images: { unoptimized: true },
    }
  : {
      async headers() {
        return [
          {
            source: "/:path*",
            headers: [
              ...SECURITY_HEADERS.map(([key, value]) => ({ key, value })),
              { key: "Content-Security-Policy", value: csp },
            ],
          },
        ];
      },
    };

module.exports = nextConfig;
