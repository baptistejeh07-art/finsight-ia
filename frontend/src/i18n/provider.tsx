"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
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

interface I18nCtx {
  locale: Locale;
  currency: CurrencyCode;
  t: (key: string) => string;
  fc: (value: number | null | undefined, opts?: { compact?: boolean; decimals?: number }) => string;
  fn: (value: number | null | undefined, opts?: { compact?: boolean; decimals?: number; suffix?: string }) => string;
  fp: (value: number | null | undefined, decimals?: number) => string;
  fd: (date: string | Date | null | undefined, opts?: Intl.DateTimeFormatOptions) => string;
}

const Ctx = createContext<I18nCtx>({
  locale: "fr",
  currency: "EUR",
  t: (k) => k,
  fc: () => "—",
  fn: () => "—",
  fp: () => "—",
  fd: () => "—",
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const { prefs } = useUserPreferences();
  const locale = (prefs.language || "fr") as Locale;
  const currency = (prefs.currency || "EUR") as CurrencyCode;

  const value = useMemo<I18nCtx>(
    () => ({
      locale,
      currency,
      t: (key: string) => translate(locale, key),
      fc: (v, opts) => formatCurrency(v, currency, locale, opts),
      fn: (v, opts) => formatNumber(v, locale, opts),
      fp: (v, decimals) => formatPercent(v, locale, decimals),
      fd: (d, opts) => formatDate(d, locale, opts),
    }),
    [locale, currency]
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
