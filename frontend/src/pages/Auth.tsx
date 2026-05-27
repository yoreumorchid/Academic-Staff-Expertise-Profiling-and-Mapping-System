/**
 * Auth pages: login (UC-3), register (UC-1), forgot password (UC-4),
 * reset password (UC-4). The visual treatment follows DESIGN.md §1-4.
 */
import { FormEvent, useState } from "react";
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
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-marketing px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-display font-signature text-text-primary">
            ExpertiseInsight
          </h1>
          <p className="mt-2 text-small text-text-tertiary">{subtitle}</p>
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
// UC-3 — Login
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
        (data.user.role === "faculty_administrator" ? "/admin" : "/staff/profile");
      navigate(next, { replace: true });
    } catch (err) {
      setError(extractApiError(err, "Invalid email or password."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Access your institutional dashboard.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">
            Institutional email
          </label>
          <input
            id="email"
            type="email"
            className="input"
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
          <div className="rounded-comfy border border-white/[0.08] bg-white/[0.02] p-3 text-caption text-text-secondary">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <div className="flex justify-between text-caption">
          <Link to="/register" className="text-brand-violet hover:text-brand-hover">
            Create account
          </Link>
          <Link
            to="/forgot-password"
            className="text-brand-violet hover:text-brand-hover"
          >
            Forgot password?
          </Link>
        </div>
      </form>
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// UC-1 — Register
// ---------------------------------------------------------------------------

const PORTFOLIO_OPTIONS: { label: string; value: PortfolioType }[] = [
  { label: "Faculty Manager (HR)", value: "faculty_manager" },
  { label: "Head of Department (HoD)", value: "head_of_department" },
  { label: "Deputy Dean (Research)", value: "deputy_dean_research" },
  { label: "Deputy Dean (UG/PG)", value: "deputy_dean_ugpg" },
];

export function RegisterPage() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("academic_staff");
  const [department, setDepartment] = useState("");
  const [orcidId, setOrcidId] = useState("");
  const [portfolio, setPortfolio] = useState<PortfolioType>("faculty_manager");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: fullName,
        email,
        password,
        role,
      };
      if (role === "academic_staff") {
        payload.department = department;
        payload.orcid_id = orcidId;
      } else {
        payload.portfolio = portfolio;
        if (orcidId) {
          payload.orcid_id = orcidId; // UC-1 dual-role flag
          if (department) payload.department = department;
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
      <AuthShell
        title="Registration submitted"
        subtitle="Your request is awaiting Faculty Manager approval (UC-1 post-condition)."
      >
        <p className="text-small text-text-secondary">
          You will receive an email at <strong>{email}</strong> once a Faculty
          Manager reviews your request. Redirecting to the login page…
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create an account"
      subtitle="UC-1 — Pending status until administrative approval."
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="full_name">
            Full name
          </label>
          <input
            id="full_name"
            type="text"
            className="input"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="email">
            Institutional email
          </label>
          <input
            id="email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="password">
            Password (min. 8 characters)
          </label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
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
                    ? "border-brand-violet bg-white/[0.05] text-text-primary"
                    : "border-white/[0.08] bg-white/[0.02] text-text-secondary hover:bg-white/[0.05]",
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
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="orcid">
                ORCID ID (0000-0000-0000-0000)
              </label>
              <input
                id="orcid"
                type="text"
                className="input"
                value={orcidId}
                onChange={(e) => setOrcidId(e.target.value)}
                pattern="^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                placeholder="0000-0000-0000-0000"
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
                ORCID ID (optional — enables dual-role profile)
              </label>
              <input
                id="orcid_optional"
                type="text"
                className="input"
                value={orcidId}
                onChange={(e) => setOrcidId(e.target.value)}
                pattern="^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                placeholder="0000-0000-0000-0000"
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
                />
              </div>
            )}
          </>
        )}

        {error && (
          <div className="rounded-comfy border border-white/[0.08] bg-white/[0.02] p-3 text-caption text-text-secondary">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Submitting…" : "Submit registration"}
        </button>
        <p className="text-center text-caption text-text-tertiary">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-violet hover:text-brand-hover">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// UC-4 — Forgot password (request reset link)
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
    <AuthShell title="Reset password" subtitle="UC-4 — request a secure reset link.">
      {success ? (
        <p className="text-small text-text-secondary">
          If <strong>{email}</strong> is registered, a reset link has been
          dispatched to your institutional inbox.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">
              Institutional email
            </label>
            <input
              id="email"
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="rounded-comfy border border-white/[0.08] bg-white/[0.02] p-3 text-caption text-text-secondary">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Sending…" : "Send reset link"}
          </button>
          <p className="text-center text-caption text-text-tertiary">
            <Link to="/login" className="text-brand-violet hover:text-brand-hover">
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------
// UC-4 — Reset password (consume token)
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
      <AuthShell title="Invalid link" subtitle="UC-4 exception flow.">
        <p className="text-small text-text-secondary">
          The reset link is missing required parameters. Please request a new
          one from the forgot-password page.
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Set a new password" subtitle="UC-4 — finish reset.">
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
            required
          />
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
            required
          />
        </div>
        {error && (
          <div className="rounded-comfy border border-white/[0.08] bg-white/[0.02] p-3 text-caption text-text-secondary">
            {error}
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Updating…" : "Update password"}
        </button>
      </form>
    </AuthShell>
  );
}

// Re-export the user type for convenience.
export type { CurrentUser };
