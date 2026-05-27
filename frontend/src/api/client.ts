import axios from "axios";

/**
 * Singleton Axios instance. The bearer token is injected at runtime by
 * the auth store so we never persist secrets in module scope.
 */
export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

export function setAuthToken(token: string | null): void {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

/** Normalize backend error envelopes into a single message string. */
export function extractApiError(error: unknown, fallback = "Unexpected error."): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { error?: { message?: string } }
      | undefined;
    return data?.error?.message ?? error.message ?? fallback;
  }
  return fallback;
}
