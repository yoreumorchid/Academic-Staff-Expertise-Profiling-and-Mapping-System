import axios from "axios";

/**
 * Singleton Axios instance. The bearer token is injected at runtime by
 * the auth store so we never persist secrets in module scope.
 */
export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

export const SESSION_EXPIRED_EVENT = "expertise-insight:session-expired";

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

// ---------------------------------------------------------------------------
// 401 interceptor — surface a modal asking the user to re-authenticate
// instead of leaking a raw "Access token has expired" string into pages.
// ---------------------------------------------------------------------------
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? "";
      // Skip the login call itself — invalid credentials must stay an
      // in-form error rather than a global modal.
      if (!url.includes("/auth/login")) {
        window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
      }
    }
    return Promise.reject(error);
  },
);
