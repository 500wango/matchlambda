"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="zh">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          background: "#080c14",
          color: "#e2e8f0",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <main
          id="main-content"
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
          }}
        >
          <div style={{ maxWidth: 420, textAlign: "center" }}>
            <a
              href="/"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 20,
                color: "#fff",
                textDecoration: "none",
                fontWeight: "bold",
                fontSize: 18,
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "#2563eb",
                  color: "#fff",
                  fontWeight: "bold",
                }}
              >
                λ
              </span>
              MatchLambda
            </a>
            <h1 style={{ fontSize: 20, marginBottom: 8 }}>Something went wrong</h1>
            <p style={{ fontSize: 14, color: "#94a3b8" }}>
              {error?.message || "An unexpected error occurred."}
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 16 }}>
              <button
                type="button"
                onClick={() => reset()}
                style={{
                  padding: "8px 16px",
                  background: "#2563eb",
                  color: "#fff",
                  border: 0,
                  borderRadius: 8,
                  cursor: "pointer",
                }}
              >
                Reload
              </button>
              <a
                href="/"
                style={{
                  padding: "8px 16px",
                  background: "#1e293b",
                  color: "#e2e8f0",
                  borderRadius: 8,
                  textDecoration: "none",
                  fontSize: 14,
                }}
              >
                Home
              </a>
            </div>
          </div>
        </main>
      </body>
    </html>
  );
}
