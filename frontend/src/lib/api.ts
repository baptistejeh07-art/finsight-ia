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

/** Lit la langue + devise depuis localStorage (mirror de useUserPreferences).
 * Renvoie les headers à ajouter à toute requête API pour propager les prefs.
 */
function getLocaleHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem("finsight-user-preferences");
    if (!raw) return {};
    const p = JSON.parse(raw);
    const headers: Record<string, string> = {};
    if (p.language) headers["X-User-Language"] = String(p.language);
    if (p.currency) headers["X-User-Currency"] = String(p.currency);
    if (p.explanatory_mode) headers["X-Explanatory-Mode"] = "1";
    return headers;
  } catch {
    return {};
  }
}

async function apiPost<T>(endpoint: string, body: unknown): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...getLocaleHeaders(),
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
    headers: { ...authHeader, ...getLocaleHeaders() },
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

export async function submitCmpSecteurJob(
  secteur_a: string,
  univers_a: string,
  secteur_b: string,
  univers_b?: string,
): Promise<JobSubmitResponse> {
  return apiPost("/jobs/cmp/secteur", {
    secteur_a, univers_a, secteur_b, univers_b: univers_b || univers_a,
  });
}

export async function submitPmeJob(siren: string): Promise<JobSubmitResponse> {
  return apiPost("/jobs/analyze/pme", { siren, use_pappers_comptes: true });
}

export async function analyzePmeSync(siren: string): Promise<{
  success: boolean;
  request_id: string;
  elapsed_ms: number;
  data?: unknown;
  files?: { pdf?: string; pptx?: string; xlsx?: string };
  error?: string;
}> {
  return apiPost("/analyze/pme", { siren, use_pappers_comptes: true });
}

export interface PmeSearchResult {
  siren: string;
  denomination: string | null;
  ville: string | null;
  code_postal: string | null;
  code_naf: string | null;
  nature_juridique: string | null;
  categorie: string | null;
  date_creation: string | null;
  dirigeant: string | null;
}

export async function searchPme(
  q: string,
  limit = 8
): Promise<{ results: PmeSearchResult[]; total?: number }> {
  if (!q || q.trim().length < 2) return { results: [] };
  return apiGet(`/search/pme?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ─── Documents uploadés (extraction Gemini Vision) ─────────────────────────

export interface UserDocument {
  id: string;
  analysis_id: string | null;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  type_detected: string | null;
  status: "uploaded" | "extracting" | "extracted" | "validated" | "error";
  validated: boolean;
  extracted_data: Record<string, unknown> | null;
  extraction_error: string | null;
  created_at: string;
}

export async function uploadDocument(
  file: File,
  analysisId?: string | null
): Promise<{
  id: string;
  status: string;
  filename: string;
  cached?: boolean;
  extracted_data?: Record<string, unknown>;
  type_detected?: string;
}> {
  const fd = new FormData();
  fd.append("file", file);
  if (analysisId) fd.append("analysis_id", analysisId);

  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}/documents/upload`, {
    method: "POST",
    headers: { ...authHeader },
    body: fd,
  });
  if (!res.ok) {
    throw new Error(`Upload failed (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

export async function extractDocument(docId: string): Promise<{
  id: string;
  type_detected: string;
  extracted_data: Record<string, unknown>;
  confidence?: number;
  source?: string;
  cached?: boolean;
}> {
  return apiPost(`/documents/${docId}/extract`, {});
}

export async function validateDocument(
  docId: string,
  extractedData: Record<string, unknown>,
  validated = true
): Promise<UserDocument> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}/documents/${docId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeader },
    body: JSON.stringify({ extracted_data: extractedData, validated }),
  });
  if (!res.ok) {
    throw new Error(`Validate failed (${res.status})`);
  }
  return res.json();
}

export async function listAnalysisDocuments(
  analysisId: string
): Promise<{ documents: UserDocument[] }> {
  return apiGet(`/analyses/${analysisId}/documents`);
}

// ─── QA Streaming SSE ────────────────────────────────────────────────────

export interface QAStreamCallbacks {
  onChunk: (text: string) => void;
  onReplace?: (full: string) => void;  // post-stream accent restore
  onDone?: () => void;
  onError?: (err: string) => void;
  signal?: AbortSignal;
}

/**
 * Pose une question avec streaming SSE.
 * Onglet Network : `/qa/stream` retourne text/event-stream.
 * Chaque event : `data: {"chunk": "mot"}` puis `data: {"done": true}`.
 */
export async function askQAStream(
  jobId: string,
  messages: { role: "user" | "assistant"; content: string }[],
  callbacks: QAStreamCallbacks
): Promise<void> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}/qa/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader, ...getLocaleHeaders() },
    body: JSON.stringify({ job_id: jobId, messages }),
    signal: callbacks.signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`QA stream failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE events séparés par \n\n
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const ev of events) {
      const line = ev.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        const obj = JSON.parse(payload);
        if (obj.chunk) callbacks.onChunk(obj.chunk);
        else if (obj.replace && callbacks.onReplace) callbacks.onReplace(obj.replace);
        else if (obj.done && callbacks.onDone) callbacks.onDone();
        else if (obj.error && callbacks.onError) callbacks.onError(obj.error);
      } catch {
        // ignore JSON malformé
      }
    }
  }
  if (callbacks.onDone) callbacks.onDone();
}

export async function deleteDocument(docId: string): Promise<void> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}/documents/${docId}`, {
    method: "DELETE",
    headers: { ...authHeader },
  });
  if (!res.ok) throw new Error(`Delete failed (${res.status})`);
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

// ─── Q&A chatbot ───────────────────────────────────────────────────────────

export async function askQA(
  jobId: string,
  messages: { role: "user" | "assistant"; content: string }[]
): Promise<{ answer: string }> {
  return apiPost("/qa", { job_id: jobId, messages });
}

export async function resolveQuery(query: string): Promise<ResolveResult> {
  return apiGet<ResolveResult>(`/resolve/${encodeURIComponent(query)}`);
}

// ─── Files ─────────────────────────────────────────────────────────────────

export function getFileUrl(filePath: string): string {
  return `${API_URL}/file/${encodeURIComponent(filePath)}`;
}
