// Thin fetch wrapper. Its one real job is flattening FastAPI's two different
// error shapes into a single ApiError, so no caller has to remember that
// 422 from /ingest carries an object detail while every other 4xx carries a string.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  /** Populated on 422 from the ingest routes. Per-source rejection reasons. */
  skipped: string[];

  constructor(message: string, status: number, skipped: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.skipped = skipped;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = ((await res.json()) as { detail?: unknown })?.detail;
  } catch {
    // Body was empty or not JSON — fall through to the generic message.
  }

  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; skipped?: string[] };
    return new ApiError(
      d.message ?? `Request failed (${res.status})`,
      res.status,
      d.skipped ?? [],
    );
  }

  return new ApiError(
    typeof detail === "string" ? detail : `Request failed (${res.status})`,
    res.status,
  );
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the API. Check that it's running.", 0);
  }

  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export { BASE_URL };
