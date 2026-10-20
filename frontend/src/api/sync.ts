import axios from "axios";
import { useAuthStore } from "../store/auth";
import type { SyncJob } from "../types";
import { api } from "./client";

export interface SyncSubmission {
  jobId: string;
  alreadyActive: boolean;
}

/**
 * Queue a synchronization and register it with the application-wide tracker.
 *
 * All manual sync buttons must use this function so queued work is never
 * detached from the progress/result modal. A duplicate request adopts the
 * already-running job returned by the API instead of leaving the user with a
 * conflict message and no way to follow its outcome.
 */
export async function submitSync(targetUserId?: string): Promise<SyncSubmission> {
  try {
    const endpoint = targetUserId ? `/sync/users/${targetUserId}` : "/sync/me";
    const { data } = await api.post<SyncJob>(endpoint);
    useAuthStore.getState().setActiveSyncJobId(data.id);
    return { jobId: data.id, alreadyActive: false };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      const data = error.response.data as
        | { error?: { details?: { job_id?: unknown } } }
        | undefined;
      const jobId = data?.error?.details?.job_id;
      if (typeof jobId === "string" && jobId) {
        useAuthStore.getState().setActiveSyncJobId(jobId);
        return { jobId, alreadyActive: true };
      }
    }
    throw error;
  }
}
