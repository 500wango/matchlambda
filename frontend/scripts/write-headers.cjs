#!/usr/bin/env node
/**
 * Emits `out/_headers` for Cloudflare Pages.
 *
 * A static export has no Node server, so `headers()` in next.config.js cannot
 * run. Cloudflare Pages reads a plain `_headers` file from the deployed bundle
 * instead, so this script renders the same policy into that file after
 * `next build`. Run via `npm run build:static`.
 */
const fs = require("node:fs");
const path = require("node:path");
const { buildCsp, resolveApiOrigin, SECURITY_HEADERS } = require("../lib/csp.cjs");

const outDir = path.join(__dirname, "..", "out");

if (!fs.existsSync(outDir)) {
  console.error(
    `[write-headers] ${outDir} does not exist.\n` +
      "  Run the export first: NEXT_STATIC_EXPORT=1 next build"
  );
  process.exit(1);
}

// lib/api.ts falls back to `${window.location.origin}/v1` on HTTPS when
// NEXT_PUBLIC_API_URL is unset. On Cloudflare Pages that origin serves the
// static bundle and has no /v1, so an unset value must fail the build rather
// than ship a frontend that silently calls a 404.
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
if (!apiUrl) {
  console.error(
    "[write-headers] NEXT_PUBLIC_API_URL is not set.\n" +
      "  Set it to the public API base, e.g. https://api.example.com/v1"
  );
  process.exit(1);
}

const apiOrigin = resolveApiOrigin(apiUrl);
if (!apiOrigin) {
  console.error(`[write-headers] NEXT_PUBLIC_API_URL is not a valid URL: ${apiUrl}`);
  process.exit(1);
}

const csp = buildCsp({ apiUrl, isProd: true });
const body = [
  "/*",
  ...SECURITY_HEADERS.map(([key, value]) => `  ${key}: ${value}`),
  `  Content-Security-Policy: ${csp}`,
  "",
].join("\n");

fs.writeFileSync(path.join(outDir, "_headers"), body, "utf8");
console.log(`[write-headers] wrote out/_headers with connect-src origin ${apiOrigin}`);
