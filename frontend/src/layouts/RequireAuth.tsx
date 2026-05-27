import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/auth";

/**
 * Wraps protected routes. Unauthenticated visitors are bounced to the
 * login page (UC-3) with a ``next`` parameter so they return to the
 * intended destination after authenticating.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  const location = useLocation();
  if (!token) {
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname)}`}
        replace
      />
    );
  }
  return <>{children}</>;
}
