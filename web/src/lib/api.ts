// Thin client for the FastAPI backend (app/api/routes.py). Same origin:
// Vite proxies /api in development and FastAPI serves this app in
// production, so the session cookie just works.

export interface AppConfig {
  provider: string;
  provider_label: string;
  models: string[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** The server's message: FastAPI sends `detail` as a string for our own
 *  errors and as a list for request validation errors. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return `Please check your input: ${detail[0].msg}.`;
  if (status === 429) return "Too many requests. Please try again later.";
  return status >= 500 ? "Something went wrong on our side. Please try again." : `Request failed (${status}).`;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...init });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* not JSON */
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body));
  return body as T;
}

export const getConfig = () => request<AppConfig>("/api/config");
