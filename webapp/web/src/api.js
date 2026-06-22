// Thin client for the FastAPI backend. Same-origin in production (Vercel),
// proxied to :8000 in dev (see vite.config.js).

export async function getMeta() {
  const r = await fetch("/api/meta");
  if (!r.ok) throw new Error("Failed to load metadata");
  return r.json();
}

export async function runQuery(filters) {
  const r = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filters }),
  });
  if (!r.ok) throw new Error("Query failed");
  return r.json();
}
