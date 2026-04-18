/**
 * Client API pour appeler le backend FastAPI.
 * Gère auth (JWT Supabase) + erreurs.
 */
import { createClient } from "./supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AnalyseResponse {
  success: boolean;
  request_id: string;
  elapsed_ms: number;
  data?: Record<string, unknown>;
  files?: { pdf?: string; pptx?: string; xlsx?: string };
  error?: string;
}

async function getAuthHeader(): Promise<HeadersInit> {
  try {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
  } catch {
    // Pas connecté = mode invité, OK
  }
  return {};
}

async function apiPost<T>(endpoint: string, body: unknown): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${endpoint} failed (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

async function apiGet<T>(endpoint: string): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}${endpoint}`, {
    headers: { ...authHeader },
  });
  if (!res.ok) {
    throw new Error(`API ${endpoint} failed (${res.status})`);
  }
  return res.json();
}

// ─── Analyses (sync — bloquant) ────────────────────────────────────────────

export async function analyzeSociete(
  ticker: string,
  devise = "USD",
  scope = "interface"
): Promise<AnalyseResponse> {
  return apiPost<AnalyseResponse>("/analyze/societe", { ticker, devise, scope });
}

export async function analyzeSecteur(
  secteur: string,
  univers: string
): Promise<AnalyseResponse> {
  return apiPost<AnalyseResponse>("/analyze/secteur", { secteur, univers });
}

export async function analyzeIndice(indice: string): Promise<AnalyseResponse> {
  return apiPost<AnalyseResponse>("/analyze/indice", { indice });
}

// ─── Jobs (async — recommandé pour analyses longues) ───────────────────────

export interface JobSubmitResponse {
  job_id: string;
  status: "queued";
  kind: string;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  progress_message?: string;
  result?: {
    data?: Record<string, unknown>;
    files?: { pdf?: string; pptx?: string; xlsx?: string };
  };
  error?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

export async function submitSocieteJob(
  ticker: string,
  devise = "USD",
  scope = "interface"
): Promise<JobSubmitResponse> {
  return apiPost("/jobs/analyze/societe", { ticker, devise, scope });
}

export async function submitSecteurJob(
  secteur: string,
  univers: string
): Promise<JobSubmitResponse> {
  return apiPost("/jobs/analyze/secteur", { secteur, univers });
}

export async function submitIndiceJob(indice: string): Promise<JobSubmitResponse> {
  return apiPost("/jobs/analyze/indice", { indice });
}

export async function submitCmpSocieteJob(
  ticker_a: string,
  ticker_b: string
): Promise<JobSubmitResponse> {
  return apiPost("/jobs/cmp/societe", { ticker_a, ticker_b });
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return apiGet(`/jobs/${jobId}`);
}

/**
 * Poll le job toutes les `intervalMs` jusqu'à fin (done|error).
 * Appelle `onTick` à chaque update.
 */
export async function waitForJob(
  jobId: string,
  onTick?: (job: JobStatus) => void,
  intervalMs = 5000,
  maxWaitMs = 15 * 60 * 1000  // 15 min hard cap
): Promise<JobStatus> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const job = await getJob(jobId);
    onTick?.(job);
    if (job.status === "done" || job.status === "error") return job;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Job timeout (>15 min)");
}

// ─── User ──────────────────────────────────────────────────────────────────

export async function getMe(): Promise<{ id: string; email: string }> {
  return apiGet("/me");
}

export interface HistoryJob {
  job_id: string;
  kind: string;
  label?: string;
  created_at: string;
  finished_at?: string;
}

export async function getHistory(): Promise<{ user_id: string; history: HistoryJob[] }> {
  return apiGet("/history");
}

// ─── Tickers ───────────────────────────────────────────────────────────────

export async function resolveTicker(query: string): Promise<{ ticker: string | null }> {
  return apiGet(`/tickers/resolve/${encodeURIComponent(query)}`);
}

export interface ResolveResult {
  query: string;
  kind: "societe" | "secteur" | "indice" | "unknown";
  ticker?: string;
  universe?: string;
  sector?: string;
}

export async function resolveQuery(query: string): Promise<ResolveResult> {
  return apiGet<ResolveResult>(`/resolve/${encodeURIComponent(query)}`);
}

// ─── Files ─────────────────────────────────────────────────────────────────

export function getFileUrl(filePath: string): string {
  return `${API_URL}/file/${encodeURIComponent(filePath)}`;
}
