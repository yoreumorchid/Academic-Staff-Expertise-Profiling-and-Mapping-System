import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { useAuthStore } from "../store/auth";
import { Banner } from "./Profile";

export function AccountSettingsPage() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setInfo(null);

    if (newPassword !== confirmPassword) {
      setError("New password confirmation does not match.");
      return;
    }

    setBusy(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setInfo("Password updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(extractApiError(err, "Could not change password."));
    } finally {
      setBusy(false);
    }
  }

  function endSession() {
    logout();
    navigate("/login", { replace: true });
  }

  if (!user) return null;

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Account Settings
        </h1>
        <p className="mt-2 text-body text-text-tertiary">
          Manage the sign-in security and active session for {user.email}.
        </p>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {info && <Banner kind="success">{info}</Banner>}

      <section className="card space-y-4">
        <div>
          <h2 className="text-heading-3 font-announce text-text-primary">
            Change password
          </h2>
          <p className="mt-1 text-small text-text-tertiary">
            Enter your current password before choosing a new one.
          </p>
        </div>
        <form onSubmit={changePassword} className="space-y-4">
          <div>
            <label
              className="mb-2 block text-small font-signature text-text-secondary"
              htmlFor="current-password"
            >
              Current password
            </label>
            <input
              id="current-password"
              className="input"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </div>
          <div>
            <label
              className="mb-2 block text-small font-signature text-text-secondary"
              htmlFor="new-password"
            >
              New password
            </label>
            <input
              id="new-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </div>
          <div>
            <label
              className="mb-2 block text-small font-signature text-text-secondary"
              htmlFor="confirm-password"
            >
              Confirm new password
            </label>
            <input
              id="confirm-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </div>
          <div className="flex justify-end">
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Updating…" : "Update password"}
            </button>
          </div>
        </form>
      </section>

      <section className="card flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-heading-3 font-announce text-text-primary">
            Current session
          </h2>
          <p className="mt-1 text-small text-text-tertiary">
            Sign out of Expertise Insight on this device.
          </p>
        </div>
        <button
          type="button"
          className="btn-ghost shrink-0 self-start sm:self-center"
          onClick={endSession}
        >
          Log out
        </button>
      </section>
    </div>
  );
}
