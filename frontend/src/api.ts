export const apiBase = import.meta.env.PROD
  ? "/api/v1"
  : (
      import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"
    ).replace(/\/+$/, "");

export async function readHealth(signal: AbortSignal, database = false) {
  const response = await fetch(
    apiBase + (database ? "/health/db" : "/health"),
    {
      signal,
      cache: "no-store",
      credentials: "omit",
    },
  );
  if (!response.ok) throw new Error("API unavailable");
  const body = await response.json();
  if (body?.status === "ok") return { status: "ok" } as const;
  if (
    !database &&
    body?.status === "validation_only" &&
    typeof body.parser_probe_passed === "boolean"
  ) {
    return {
      status: "validation_only",
      parserReady: body.parser_probe_passed as boolean,
    } as const;
  }
  throw new Error("Unexpected health response");
}
