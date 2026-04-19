/**
 * Système i18n maison léger pour FinSight IA.
 *
 * - Pas de next-intl pour éviter le refactor des routes en /[locale]/
 * - Context React qui propage la langue + devise depuis useUserPreferences
 * - Lookup dot-notation : t("nav.home") → "Accueil" / "Home"
 * - Helpers format : formatCurrency, formatNumber, formatDate via Intl natif
 * - Fallback automatique vers FR si une clé manque dans la langue choisie
 */
import frMessages from "./messages/fr.json";
import enMessages from "./messages/en.json";
import esMessages from "./messages/es.json";
import deMessages from "./messages/de.json";
import itMessages from "./messages/it.json";
import ptMessages from "./messages/pt.json";

export type Locale = "fr" | "en" | "es" | "de" | "it" | "pt";
export type CurrencyCode = "EUR" | "USD" | "GBP" | "CHF" | "JPY" | "CAD";

type MessageDict = Record<string, unknown>;

const MESSAGES: Record<Locale, MessageDict> = {
  fr: frMessages,
  en: enMessages,
  es: esMessages,
  de: deMessages,
  it: itMessages,
  pt: ptMessages,
};

const FALLBACK_LOCALE: Locale = "fr";

/**
 * Récupère une string par clé dot-notation.
 * t("nav.home") → "Accueil" en FR, "Home" en EN
 * Si la clé manque dans la locale → fallback FR.
 * Si totalement absente → renvoie la clé brute (utile pour debug).
 */
export function tFromDict(dict: MessageDict, key: string): string {
  const parts = key.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else {
      return "";
    }
  }
  return typeof cur === "string" ? cur : "";
}

export function translate(locale: Locale, key: string): string {
  const dict = MESSAGES[locale] || MESSAGES[FALLBACK_LOCALE];
  const found = tFromDict(dict, key);
  if (found) return found;
  // Fallback: EN puis FR (EN plus universel pour es/de/it/pt manquants)
  if (locale !== "en") {
    const en = tFromDict(MESSAGES.en, key);
    if (en) return en;
  }
  if (locale !== FALLBACK_LOCALE) {
    const fr = tFromDict(MESSAGES[FALLBACK_LOCALE], key);
    if (fr) return fr;
  }
  // Affichage debug : la clé brute
  return key;
}

// ─── Format helpers via Intl ─────────────────────────────────────────────

/** Map langue UI → locale BCP-47 pour Intl */
const INTL_LOCALES: Record<Locale, string> = {
  fr: "fr-FR",
  en: "en-US",
  es: "es-ES",
  de: "de-DE",
  it: "it-IT",
  pt: "pt-PT",
};

export function formatCurrency(
  value: number | null | undefined,
  currency: CurrencyCode,
  locale: Locale = "fr",
  opts: { compact?: boolean; decimals?: number } = {}
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const intlLoc = INTL_LOCALES[locale];
  try {
    return new Intl.NumberFormat(intlLoc, {
      style: "currency",
      currency,
      notation: opts.compact ? "compact" : "standard",
      maximumFractionDigits: opts.decimals ?? (opts.compact ? 1 : 0),
      minimumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value.toLocaleString(intlLoc)} ${currency}`;
  }
}

export function formatNumber(
  value: number | null | undefined,
  locale: Locale = "fr",
  opts: { compact?: boolean; decimals?: number; suffix?: string } = {}
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const intlLoc = INTL_LOCALES[locale];
  const formatted = new Intl.NumberFormat(intlLoc, {
    notation: opts.compact ? "compact" : "standard",
    maximumFractionDigits: opts.decimals ?? (opts.compact ? 1 : 2),
    minimumFractionDigits: 0,
  }).format(value);
  return opts.suffix ? `${formatted}${opts.suffix}` : formatted;
}

export function formatPercent(
  value: number | null | undefined,
  locale: Locale = "fr",
  decimals = 1
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(INTL_LOCALES[locale], {
    style: "percent",
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value / 100);
}

export function formatDate(
  date: string | Date | null | undefined,
  locale: Locale = "fr",
  opts: Intl.DateTimeFormatOptions = { day: "2-digit", month: "2-digit", year: "numeric" }
): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(INTL_LOCALES[locale], opts).format(d);
}
