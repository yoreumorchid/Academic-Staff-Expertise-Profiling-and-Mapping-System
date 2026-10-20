/**
 * Administrator landing page — surfaces the strategic-dashboard summary
 * (UC-6) as a concise faculty expertise overview.
 */
import { InternalExpertisePanel } from "./InternalExpertise";

export function AdminHomePage() {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-heading-1 font-announce text-text-primary">
          Strategic Dashboard
        </h1>
      </header>

      <InternalExpertisePanel embedded />
    </div>
  );
}
