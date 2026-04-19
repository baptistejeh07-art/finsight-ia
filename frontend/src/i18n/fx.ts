/**
 * Conversion de devise live (exchangerate.host — gratuit, no auth, no rate limit).
 * Cache localStorage 1h pour limiter les appels réseau.
 *
 * Usage :
 *   const eurToUsd = await getRate("EUR", "USD");
 *   const usdValue = (4_250_000) * eurToUsd;
 *
 * En cas d'échec API : fallback table statique (taux moyens approximatifs avril 2026).
 * Mieux qu'une erreur, mais ne pas s'y fier pour des montants critiques.
 */

import type { CurrencyCode } from "./index";

interface RatesCache {
  base: CurrencyCode;
  rates: Record<string, number>;
  ts: number;
}

const CACHE_KEY = "finsight-fx-cache";
const TTL_MS = 60 * 60 * 1000; // 1 heure

// Fallback statique (valeurs moyennes mars-avril 2026)
const FALLBACK_RATES: Record<CurrencyCode, Record<CurrencyCode, number>> = {
  EUR: { EUR: 1, USD: 1.08, GBP: 0.86, CHF: 0.95, JPY: 162, CAD: 1.47 },
  USD: { EUR: 0.93, USD: 1, GBP: 0.79, CHF: 0.88, JPY: 150, CAD: 1.36 },
  GBP: { EUR: 1.17, USD: 1.27, GBP: 1, CHF: 1.11, JPY: 189, CAD: 1.71 },
  CHF: { EUR: 1.05, USD: 1.14, GBP: 0.90, CHF: 1, JPY: 170, CAD: 1.55 },
  JPY: { EUR: 0.0062, USD: 0.0067, GBP: 0.0053, CHF: 0.0059, JPY: 1, CAD: 0.0091 },
  CAD: { EUR: 0.68, USD: 0.74, GBP: 0.59, CHF: 0.65, JPY: 110, CAD: 1 },
};

function readCache(base: CurrencyCode): RatesCache | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${CACHE_KEY}-${base}`);
    if (!raw) return null;
    const parsed: RatesCache = JSON.parse(raw);
    if (Date.now() - parsed.ts > TTL_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeCache(cache: RatesCache) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${CACHE_KEY}-${cache.base}`, JSON.stringify(cache));
  } catch {
    // localStorage plein → ignore
  }
}

async function fetchRates(base: CurrencyCode): Promise<RatesCache> {
  // Provider gratuit, pas d'auth. Si bloqué : fallback statique.
  try {
    const r = await fetch(
      `https://api.exchangerate.host/latest?base=${base}&symbols=EUR,USD,GBP,CHF,JPY,CAD`,
      { cache: "no-store" }
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    if (!data?.rates) throw new Error("no rates");
    const cache: RatesCache = { base, rates: data.rates, ts: Date.now() };
    writeCache(cache);
    return cache;
  } catch (e) {
    console.warn(`[fx] live rates failed, fallback static:`, e);
    return {
      base,
      rates: FALLBACK_RATES[base] as unknown as Record<string, number>,
      ts: Date.now(),
    };
  }
}

let inFlight: Record<string, Promise<RatesCache>> = {};

export async function getRate(
  from: CurrencyCode,
  to: CurrencyCode
): Promise<number> {
  if (from === to) return 1;
  const cached = readCache(from);
  if (cached?.rates[to]) return cached.rates[to];

  const key = `${from}`;
  if (!inFlight[key]) {
    inFlight[key] = fetchRates(from);
  }
  const fresh = await inFlight[key];
  delete inFlight[key];
  return fresh.rates[to] ?? FALLBACK_RATES[from]?.[to] ?? 1;
}

export async function convertAmount(
  amount: number,
  from: CurrencyCode,
  to: CurrencyCode
): Promise<number> {
  if (from === to || !Number.isFinite(amount)) return amount;
  const rate = await getRate(from, to);
  return amount * rate;
}

/** Synchrone : utilise uniquement le cache (renvoie null si pas en cache). */
export function getCachedRate(from: CurrencyCode, to: CurrencyCode): number | null {
  if (from === to) return 1;
  const cached = readCache(from);
  return cached?.rates[to] ?? null;
}
