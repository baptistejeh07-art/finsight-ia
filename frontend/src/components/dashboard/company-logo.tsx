"use client";

import { useState } from "react";

// Mapping ticker → domain pour Logo.dev (extension simple à enrichir)
const TICKER_DOMAINS: Record<string, string> = {
  AAPL: "apple.com",
  MSFT: "microsoft.com",
  GOOGL: "google.com",
  GOOG: "google.com",
  AMZN: "amazon.com",
  META: "meta.com",
  TSLA: "tesla.com",
  NVDA: "nvidia.com",
  NFLX: "netflix.com",
  ORCL: "oracle.com",
  IBM: "ibm.com",
  ADBE: "adobe.com",
  CRM: "salesforce.com",
  INTC: "intel.com",
  AMD: "amd.com",
  CSCO: "cisco.com",
  AVGO: "broadcom.com",
  QCOM: "qualcomm.com",
  TXN: "ti.com",
  TSM: "tsmc.com",
  ASML: "asml.com",
  // Finance
  JPM: "jpmorgan.com",
  BAC: "bankofamerica.com",
  WFC: "wellsfargo.com",
  GS: "goldmansachs.com",
  MS: "morganstanley.com",
  C: "citigroup.com",
  BLK: "blackrock.com",
  V: "visa.com",
  MA: "mastercard.com",
  AXP: "americanexpress.com",
  PYPL: "paypal.com",
  // Consumer
  WMT: "walmart.com",
  COST: "costco.com",
  HD: "homedepot.com",
  NKE: "nike.com",
  MCD: "mcdonalds.com",
  SBUX: "starbucks.com",
  KO: "coca-cola.com",
  PEP: "pepsi.com",
  PG: "pg.com",
  // Health
  JNJ: "jnj.com",
  UNH: "unitedhealth.com",
  PFE: "pfizer.com",
  MRK: "merck.com",
  LLY: "lilly.com",
  ABBV: "abbvie.com",
  // Energy
  XOM: "exxonmobil.com",
  CVX: "chevron.com",
  // Industry
  BA: "boeing.com",
  CAT: "caterpillar.com",
  GE: "ge.com",
  // Europe
  "MC.PA": "lvmh.com",
  "OR.PA": "loreal.com",
  "AIR.PA": "airbus.com",
  "TTE.PA": "totalenergies.com",
  "BNP.PA": "bnpparibas.com",
  "SAN.PA": "sanofi.com",
  "DG.PA": "vinci.com",
  "EL.PA": "essilorluxottica.com",
  "ABBN.SW": "abb.com",
  "NESN.SW": "nestle.com",
  "ROG.SW": "roche.com",
  "NOVN.SW": "novartis.com",
  "AIR.DE": "airbus.com",
  "SAP.DE": "sap.com",
  "BAS.DE": "basf.com",
  "ALV.DE": "allianz.com",
  // Asia
  "7203.T": "toyota-global.com",
  "7974.T": "nintendo.com",
  "6758.T": "sony.com",
};

const LOGO_DEV_TOKEN = process.env.NEXT_PUBLIC_LOGO_DEV_TOKEN || "pk_X-1ZO13GSgeOoUrIuJ6GMQ";

interface Props {
  ticker: string;
  companyName?: string;
  size?: number;
  className?: string;
}

function tickerInitials(ticker: string, name?: string): string {
  // Pour tickers genre "MC.PA" → "MC"; "AAPL" → "AA"; sinon premières lettres du nom
  const cleanTicker = ticker.split(".")[0].split("-")[0];
  if (cleanTicker.length >= 2) return cleanTicker.slice(0, 2).toUpperCase();
  if (name) {
    const words = name.split(/\s+/).filter(Boolean);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  }
  return cleanTicker.toUpperCase() || "??";
}

function guessDomain(ticker: string, name?: string): string | null {
  const t = ticker.toUpperCase();
  if (TICKER_DOMAINS[t]) return TICKER_DOMAINS[t];
  if (TICKER_DOMAINS[ticker]) return TICKER_DOMAINS[ticker];
  if (!name) return null;
  // Heuristique : transformer "Apple Inc." → "apple.com"
  const cleaned = name
    .toLowerCase()
    .replace(/\b(inc|corp|corporation|ltd|sa|plc|nv|ag|se|the|co)\b\.?/g, "")
    .replace(/[^a-z0-9]/g, "")
    .trim();
  if (!cleaned) return null;
  return `${cleaned}.com`;
}

export function CompanyLogo({ ticker, companyName, size = 48, className = "" }: Props) {
  const domain = guessDomain(ticker, companyName);
  const [errored, setErrored] = useState(false);

  if (domain && !errored) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`https://img.logo.dev/${domain}?token=${LOGO_DEV_TOKEN}&size=${size * 2}&format=png`}
        alt={companyName || ticker}
        width={size}
        height={size}
        className={`rounded-md object-contain bg-white border border-ink-100 ${className}`}
        style={{ width: size, height: size }}
        onError={() => setErrored(true)}
      />
    );
  }

  // Fallback : carré navy avec initiales
  const initials = tickerInitials(ticker, companyName);
  return (
    <div
      className={`rounded-md bg-navy-500 text-white font-bold flex items-center justify-center shrink-0 ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials}
    </div>
  );
}
