"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useUserPreferences } from "@/hooks/use-user-preferences";
import {
  translate,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatDate,
  type Locale,
  type CurrencyCode,
} from "./index";
import { getRate, getCachedRate } from "./fx";

interface I18nCtx {
  locale: Locale;
  currency: CurrencyCode;
  /** Taux de change EUR → currency. 1 si EUR. Null si pas encore chargé. */
  fxRate: number | null;
  t: (key: string) => string;
  /** Format devise. Si `fromCurrency` ≠ user.currency → conversion via fx. */
  fc: (value: number | null | undefined, opts?: { compact?: boolean; decimals?: number; fromCurrency?: CurrencyCode }) => string;
  fn: (value: number | null | undefined, opts?: { compact?: boolean; decimals?: number; suffix?: string }) => string;
  fp: (value: number | null | undefined, decimals?: number) => string;
  fd: (date: string | Date | null | undefined, opts?: Intl.DateTimeFormatOptions) => string;
  /** Convertit un montant EUR → user.currency synchrone (utilise cache fx). */
  convert: (value: number | null | undefined, fromCurrency?: CurrencyCode) => number | null;
}

const Ctx = createContext<I18nCtx>({
  locale: "fr",
  currency: "EUR",
  fxRate: 1,
  t: (k) => k,
  fc: () => "—",
  fn: () => "—",
  fp: () => "—",
  fd: () => "—",
  convert: (v) => v ?? null,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const { prefs } = useUserPreferences();
  const locale = (prefs.language || "fr") as Locale;
  const currency = (prefs.currency || "EUR") as CurrencyCode;
  const [fxRate, setFxRate] = useState<number | null>(currency === "EUR" ? 1 : getCachedRate("EUR", currency));

  // Précharge le taux EUR→currency dès qu'on connaît la devise user
  useEffect(() => {
    if (currency === "EUR") {
      setFxRate(1);
      return;
    }
    let cancelled = false;
    void getRate("EUR", currency).then((r) => {
      if (!cancelled) setFxRate(r);
    });
    return () => { cancelled = true; };
  }, [currency]);

  const value = useMemo<I18nCtx>(
    () => {
      const convert = (v: number | null | undefined, from: CurrencyCode = "EUR"): number | null => {
        if (v == null || !Number.isFinite(v)) return null;
        if (from === currency) return v;
        // Cas direct depuis EUR (le plus fréquent pour FinSight)
        if (from === "EUR" && fxRate != null) return v * fxRate;
        // Autre devise source : utilise le cache si disponible
        const r = getCachedRate(from, currency);
        return r != null ? v * r : v;
      };
      return {
        locale,
        currency,
        fxRate,
        t: (key: string) => translate(locale, key),
        fc: (v, opts = {}) => {
          const converted = convert(v, opts.fromCurrency || "EUR");
          return formatCurrency(converted, currency, locale, opts);
        },
        fn: (v, opts) => formatNumber(v, locale, opts),
        fp: (v, decimals) => formatPercent(v, locale, decimals),
        fd: (d, opts) => formatDate(d, locale, opts),
        convert,
      };
    },
    [locale, currency, fxRate]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  return useContext(Ctx);
}

/** Hook raccourci si tu n'as besoin que de t() */
export function useT() {
  return useI18n().t;
}
