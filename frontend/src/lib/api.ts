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

// ─── Analyses ──────────────────────────────────────────────────────────────

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

// ─── User ──────────────────────────────────────────────────────────────────

export async function getMe(): Promise<{ id: string; email: string }> {
  return apiGet("/me");
}

export async function getHistory(): Promise<{ history: unknown[] }> {
  return apiGet("/history");
}

// ─── Tickers ───────────────────────────────────────────────────────────────

export async function resolveTicker(query: string): Promise<{ ticker: string | null }> {
  return apiGet(`/tickers/resolve/${encodeURIComponent(query)}`);
}

// ─── Files ─────────────────────────────────────────────────────────────────

export function getFileUrl(filePath: string): string {
  return `${API_URL}/file/${encodeURIComponent(filePath)}`;
}
