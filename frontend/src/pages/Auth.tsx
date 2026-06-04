/**
 * Auth pages: login, register, forgot password, reset password.
 * Light-mode design tokens (DESIGN.md Light Mode Neutrals).
 */
import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, extractApiError } from "../api/client";
import { useAuthStore } from "../store/auth";
import type {
  CurrentUser,
  PortfolioType,
  TokenResponse,
  UserRole,
} from "../types";

function AuthShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-marketing px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-display font-signature text-text-primary">
            Expertise Insight
          </h1>
        </div>
        <div className="card">
          <h2 className="mb-6 text-heading-3 font-announce text-text-primary">
            {title}
          </h2>
          {children}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

const UM_EMAIL_PATTERN = /^[A-Za-z0-9._%+-]+@um\.edu\.my$/;
const PASSWORD_PATTERN =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?`~]).{8,16}$/;

function validateUmEmail(value: string): string | null {
  return UM_EMAIL_PATTERN.test(value.trim())
    ? null
    : "UM Email must end with @um.edu.my";
}

function validatePassword(value: string): string | null {
  return PASSWORD_PATTERN.test(value)
    ? null
    : "Password must be 8-16 characters and include upper case, lower case, a digit, and a special character.";
}

function validateDepartment(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length < 2 || trimmed.length > 100) {
    return "Department must be 2-100 characters.";
  }
  if (!/[A-Za-z]/.test(trimmed)) {
    return "Department must contain alphabetic characters.";
  }
  return null;
}

function validateName(value: string, field: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length < 1 || trimmed.length > 80) {
    return field + " must be 1-80 characters.";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post<TokenResponse>("/auth/login", {
        email,
        password,
      });
      login(data.access_token, data.user);
      const next =
        params.get("next") ??
        (data.user.role === "faculty_administrator"
          ? "/admin"
          : "/staff/profile");
      navigate(next, { replace: true });
    } catch (err) {
      setError(extractApiError(err, "Invalid email or password."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Log in">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">
            UM Email
          </label>
          <input
            id="email"
            type="email"
            className="input"
            placeholder="staffname@um.edu.my"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        {error && (
          <div className="rounded-comfy border border-border-primary bg-bg-surface p-3 text-caption text-text-secondary">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Logging in..." : "Log in"}
        </button>
        <div className="flex justify-between text-caption">
          <Link to="/register" className="text-brand-indigo hover:text-brand-hover">
            Create account
          </Link>
          <Link
            to="/forgot-password"
            className="text-brand-indigo hover:text-brand-hover"
          >
            Forgot password?
          </Link>
        </div>
      </form>
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// Register
// ---------------------------------------------------------------------------

const PORTFOLIO_OPTIONS: { label: string; value: PortfolioType }[] = [
  { label: "Faculty Manager (HR)", value: "faculty_manager" },
  { label: "Head of Department (HoD)", value: "head_of_department" },
  { label: "Deputy Dean (Research)", value: "deputy_dean_research" },
  { label: "Deputy Dean (UG/PG)", value: "deputy_dean_ugpg" },
];

export function RegisterPage() {
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("academic_staff");
  const [department, setDepartment] = useState("");
  const [orcidId, setOrcidId] = useState("");
  const [portfolio, setPortfolio] = useState<PortfolioType>("faculty_manager");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const fullName = useMemo(
    () => (firstName.trim() + " " + lastName.trim()).trim().toUpperCase(),
    [firstName, lastName],
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const fnErr = validateName(firstName, "First name");
    if (fnErr) return setError(fnErr);
    const lnErr = validateName(lastName, "Last name");
    if (lnErr) return setError(lnErr);
    const emErr = validateUmEmail(email);
    if (emErr) return setError(emErr);
    const pwErr = validatePassword(password);
    if (pwErr) return setError(pwErr);
    if (role === "academic_staff") {
      const dErr = validateDepartment(department);
      if (dErr) return setError(dErr);
      if (!/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(orcidId)) {
        return setError("ORCID ID must match the format 0000-0000-0000-0000.");
      }
    } else if (orcidId) {
      // Optional dual-role flag; if provided, format and department must hold.
      if (!/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(orcidId)) {
        return setError("ORCID ID must match the format 0000-0000-0000-0000.");
      }
      const dErr = validateDepartment(department);
      if (dErr) return setError(dErr);
    }

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: fullName,
        email: email.trim().toLowerCase(),
        password,
        role,
      };
      if (role === "academic_staff") {
        payload.department = department.trim();
        payload.orcid_id = orcidId;
      } else {
        payload.portfolio = portfolio;
        if (orcidId) {
          payload.orcid_id = orcidId;
          if (department) payload.department = department.trim();
        }
      }
      await api.post("/auth/register", payload);
      setSuccess(true);
      setTimeout(() => navigate("/login", { replace: true }), 2500);
    } catch (err) {
      setError(extractApiError(err, "Registration failed."));
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <AuthShell title="Registration submitted">
        <p className="text-small text-text-secondary">
          You will receive an email at <strong>{email}</strong> once a Faculty
          Manager reviews your request. Redirecting to the login page...
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create an account">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="first_name">
              First name
            </label>
            <input
              id="first_name"
              type="text"
              className="input"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="last_name">
              Last name
            </label>
            <input
              id="last_name"
              type="text"
              className="input"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
            />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="email">
            UM Email
          </label>
          <input
            id="email"
            type="email"
            className="input"
            placeholder="staffname@um.edu.my"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            maxLength={16}
            required
          />
          <p className="mt-1 text-label text-text-quaternary">
            8-16 chars, must include upper case, lower case, a digit and a
            special character.
          </p>
        </div>
        <div>
          <label className="label">Role</label>
          <div className="flex gap-2">
            {(["academic_staff", "faculty_administrator"] as UserRole[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={[
                  "flex-1 rounded-comfy border px-3 py-2 text-small font-signature transition-colors",
                  role === r
                    ? "border-brand-indigo bg-bg-secondary text-text-primary"
                    : "border-border-primary bg-white text-text-secondary hover:bg-bg-surface",
                ].join(" ")}
              >
                {r === "academic_staff" ? "Academic Staff" : "Faculty Administrator"}
              </button>
            ))}
          </div>
        </div>

        {role === "academic_staff" && (
          <>
            <div>
              <label className="label" htmlFor="department">
                Department
              </label>
              <input
                id="department"
                type="text"
                className="input"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                minLength={2}
                maxLength={100}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="orcid">
                ORCID ID (Fill in if you also have academic publications)
              </label>
              <input
                id="orcid"
                type="text"
                className="input"
                value={orcidId}
                onChange={(e) => setOrcidId(e.target.value)}
                pattern="^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                required
              />
            </div>
          </>
        )}

        {role === "faculty_administrator" && (
          <>
            <div>
              <label className="label" htmlFor="portfolio">
                Portfolio
              </label>
              <select
                id="portfolio"
                className="input"
                value={portfolio}
                onChange={(e) => setPortfolio(e.target.value as PortfolioType)}
              >
                {PORTFOLIO_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="orcid_optional">
                ORCID ID (Fill in if you also have academic publications)
              </label>
              <input
                id="orcid_optional"
                type="text"
                className="input"
                value={orcidId}
                onChange={(e) => setOrcidId(e.target.value)}
                pattern="^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
              />
            </div>
            {orcidId && (
              <div>
                <label className="label" htmlFor="department_optional">
                  Department (required when ORCID provided)
                </label>
                <input
                  id="department_optional"
                  type="text"
                  className="input"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  minLength={2}
                  maxLength={100}
                />
              </div>
            )}
          </>
        )}

        {error && (
          <div className="rounded-comfy border border-status-red bg-white p-3 text-caption text-status-red">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Submitting..." : "Submit registration"}
        </button>
        <p className="text-center text-caption text-text-tertiary">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-indigo hover:text-brand-hover">
            Log in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// Forgot password
// ---------------------------------------------------------------------------

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSuccess(true);
    } catch (err) {
      setError(extractApiError(err, "Could not initiate reset."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Reset password">
      {success ? (
        <p className="text-small text-text-secondary">
          If <strong>{email}</strong> is registered, a reset link has been
          dispatched to your UM inbox.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">
              UM Email
            </label>
            <input
              id="email"
              type="email"
              className="input"
              placeholder="staffname@um.edu.my"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="rounded-comfy border border-status-red bg-white p-3 text-caption text-status-red">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Sending..." : "Send reset link"}
          </button>
          <p className="text-center text-caption text-text-tertiary">
            <Link to="/login" className="text-brand-indigo hover:text-brand-hover">
              Back to log in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// Reset password
// ---------------------------------------------------------------------------

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Password confirmation does not match.");
      return;
    }
    const pwErr = validatePassword(newPassword);
    if (pwErr) return setError(pwErr);
    setLoading(true);
    try {
      await api.post("/auth/reset-password", {
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      navigate("/login", { replace: true });
    } catch (err) {
      setError(extractApiError(err, "Reset failed."));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <AuthShell title="Invalid link">
        <p className="text-small text-text-secondary">
          The reset link is missing required parameters. Please request a new
          one from the forgot-password page.
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Set a new password">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="new_password">
            New password
          </label>
          <input
            id="new_password"
            type="password"
            className="input"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
            maxLength={16}
            required
          />
          <p className="mt-1 text-label text-text-quaternary">
            8-16 chars, must include upper case, lower case, a digit and a
            special character.
          </p>
        </div>
        <div>
          <label className="label" htmlFor="confirm_password">
            Confirm new password
          </label>
          <input
            id="confirm_password"
            type="password"
            className="input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={8}
            maxLength={16}
            required
          />
        </div>
        {error && (
          <div className="rounded-comfy border border-status-red bg-white p-3 text-caption text-status-red">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Updating..." : "Update password"}
        </button>
      </form>
    </AuthShell>
  );
}

export type { CurrentUser };
