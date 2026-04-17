/**
 * Utilitaires généraux frontend.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format un nombre en devise lisible (ex: 1234.5 → "1 234,50 €") */
export function fmtCurrency(value: number, currency = "EUR", decimals = 2): string {
  if (value == null || isNaN(value)) return "—";
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Format un pourcentage (ex: 0.156 → "+15,6 %") */
export function fmtPercent(value: number, signed = true, decimals = 1): string {
  if (value == null || isNaN(value)) return "—";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(decimals).replace(".", ",")} %`;
}

/** Format un multiple (ex: 12.34 → "12,3x") */
export function fmtMultiple(value: number, decimals = 1): string {
  if (value == null || isNaN(value)) return "—";
  return `${value.toFixed(decimals).replace(".", ",")}x`;
}

/** Format date courte FR (ex: 2026-04-18 → "18 avr. 2026") */
export function fmtDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(d);
}

/** Couleur signal BUY/HOLD/SELL */
export function signalColor(signal: string): string {
  const s = signal?.toUpperCase();
  if (s === "BUY" || s === "ACHETER") return "text-signal-buy";
  if (s === "SELL" || s === "VENDRE") return "text-signal-sell";
  return "text-signal-hold";
}

/** Label FR pour un signal */
export function signalLabel(signal: string): string {
  const s = signal?.toUpperCase();
  if (s === "BUY") return "ACHETER";
  if (s === "SELL") return "VENDRE";
  if (s === "HOLD") return "CONSERVER";
  return signal || "—";
}
