/**
 * Global session-expired dialog. Triggered by the axios 401 interceptor
 * in api/client.ts. Offers the user a choice between returning to the
 * login page or dismissing the dialog (in case they are mid-form).
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SESSION_EXPIRED_EVENT } from "../api/client";
import { useAuthStore } from "../store/auth";

export function SessionExpiredModal() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    const onExpired = () => setOpen(true);
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  if (!open) return null;

  function relogin() {
    setOpen(false);
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
    >
      <div className="w-full max-w-sm rounded-card border border-border-secondary bg-white p-6 shadow-floating">
        <h2 className="text-heading-3 font-announce text-text-primary">
          Session expired
        </h2>
        <p className="mt-2 text-small text-text-secondary">
          Your access token has expired. Would you like to log in again?
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setOpen(false)}
          >
            Dismiss
          </button>
          <button type="button" className="btn-primary" onClick={relogin}>
            Log in again
          </button>
        </div>
      </div>
    </div>
  );
}
