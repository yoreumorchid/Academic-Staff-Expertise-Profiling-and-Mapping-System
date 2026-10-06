import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import type { SyncJob, SyncProgressStage, SyncStatus } from "../types";

const TERMINAL_STATUSES = new Set(["succeeded", "no_new_data", "failed"]);
const STAGE_MESSAGES: Record<SyncProgressStage, string> = {
  queued: "Waiting for an available synchronization worker…",
  resolving_profile: "Resolving your ORCID and OpenAlex profile…",
  fetching_publications: "Retrieving your latest publications…",
  processing_abstracts: "Preparing publication abstracts for analysis…",
  extracting_keywords: "Extracting research concepts from abstracts…",
  normalizing_tags: "Normalizing expertise terms with the language model…",
  saving_results: "Saving publications and expertise tags…",
  finalizing: "Finalizing your updated expertise profile…",
  completed: "Synchronization completed.",
  failed: "Synchronization failed.",
};

export function SyncStatusGuard() {
  const user = useAuthStore((state) => state.user);
  const activeJobId = useAuthStore((state) => state.activeSyncJobId);
  const setActiveJobId = useAuthStore((state) => state.setActiveSyncJobId);
  const [status, setStatus] = useState<SyncJob["status"] | null>(null);
  const [progressStage, setProgressStage] = useState<SyncProgressStage>("queued");
  const [completedJob, setCompletedJob] = useState<SyncJob | null>(null);
  const latestSeenJobId = useRef<string | null | undefined>(undefined);
  const isAcademic =
    user?.role === "academic_staff" || user?.is_dual_role === true;

  useEffect(() => {
    latestSeenJobId.current = undefined;
  }, [user?.id]);

  useEffect(() => {
    if (!isAcademic || activeJobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const discover = async () => {
      try {
        const { data } = await api.get<SyncStatus>("/sync/status");
        if (cancelled) return;
        const previousJobId = latestSeenJobId.current;
        latestSeenJobId.current = data.job_id;
        if (data.active && data.job_id) {
          setActiveJobId(data.job_id);
          setStatus(data.status);
          setProgressStage(data.progress_stage ?? "queued");
          return;
        }
        if (
          previousJobId !== undefined &&
          data.job_id &&
          data.job_id !== previousJobId &&
          data.status &&
          TERMINAL_STATUSES.has(data.status)
        ) {
          const result = await api.get<SyncJob>(`/sync/jobs/${data.job_id}`);
          if (cancelled) return;
          setCompletedJob(result.data);
          window.dispatchEvent(
            new CustomEvent("expertise-sync-completed", { detail: result.data }),
          );
        }
      } catch {
        // Discovery is best-effort; retry without interrupting the user.
      }
      if (!cancelled) timer = setTimeout(discover, 3000);
    };
    void discover();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeJobId, isAcademic, setActiveJobId]);

  useEffect(() => {
    if (!activeJobId) {
      setStatus(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const { data } = await api.get<SyncJob>(`/sync/jobs/${activeJobId}`);
        if (cancelled) return;
        setStatus(data.status);
        setProgressStage(data.progress_stage);
        if (TERMINAL_STATUSES.has(data.status)) {
          latestSeenJobId.current = data.id;
          setActiveJobId(null);
          setCompletedJob(data);
          window.dispatchEvent(
            new CustomEvent("expertise-sync-completed", { detail: data }),
          );
          return;
        }
      } catch {
        // Keep the job id and retry after a temporary network failure.
      }
      if (!cancelled) timer = setTimeout(poll, 3000);
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeJobId, setActiveJobId]);

  useEffect(() => {
    if (!activeJobId) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [activeJobId]);

  if (!activeJobId && !completedJob) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      role="status"
      aria-live="polite"
    >
      <div className="card max-w-md text-center">
        {completedJob ? (
          <>
            <h2 className="text-heading-3 font-announce">
              {completedJob.status === "failed"
                ? "Synchronization failed"
                : completedJob.status === "no_new_data"
                  ? "Your expertise profile is up to date"
                  : "Synchronization completed"}
            </h2>
            <p className="mt-3 text-body text-text-secondary">
              {completedJob.status === "failed"
                ? completedJob.error_message ?? "The synchronization could not be completed."
                : completedJob.status === "no_new_data"
                  ? "No new publications or expertise tags were found."
                  : `${completedJob.publications_added} publication(s) and ${completedJob.tags_added} expertise tag(s) were added.`}
            </p>
            <button
              className="btn-primary mt-5"
              onClick={() => setCompletedJob(null)}
            >
              OK
            </button>
          </>
        ) : (
          <>
            <h2 className="text-heading-3 font-announce">Updating expertise profile</h2>
            <div className="mx-auto mt-5 h-2 w-2/3 overflow-hidden rounded-full bg-bg-surface">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-brand-green" />
            </div>
            <p className="mt-4 text-body text-text-secondary">
              {status === "queued"
                ? STAGE_MESSAGES.queued
                : STAGE_MESSAGES[progressStage]}
            </p>
            <p className="mt-2 text-small text-text-tertiary">
              Please keep this page open and wait until synchronization finishes.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
