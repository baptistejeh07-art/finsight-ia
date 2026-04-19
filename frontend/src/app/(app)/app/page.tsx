"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, TrendingUp, Globe2, Landmark, Factory } from "lucide-react";
import toast from "react-hot-toast";
import { useI18n } from "@/i18n/provider";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const QUICK_TICKERS = ["AAPL", "TSLA", "MSFT", "MC.PA", "OR.PA", "NVDA"];
const QUICK_SECTORS = ["Technologie", "Santé", "Banques", "Énergie", "Industrie"];
const QUICK_INDICES = ["CAC 40", "S&P 500", "DAX 40", "FTSE 100", "Euro Stoxx 50"];

// Exemples SIREN — PME françaises connues qui publient leurs comptes
const QUICK_SIRENS = [
  { siren: "552081317", name: "EDF" },
  { siren: "542107651", name: "LVMH" },
  { siren: "552032534", name: "Danone" },
  { siren: "305520953", name: "Carrefour" },
  { siren: "542065479", name: "TF1" },
];

type AnalyseMode = "cote" | "non_cote";

const QUOTES = [
  {
    text: "Le prix est ce que vous payez. La décote, c'est votre marge de sécurité.",
    author: "Benjamin Graham · Security Analysis",
  },
  {
    text: "L'investissement est le plus intelligent quand il est le plus professionnel.",
    author: "Benjamin Graham · L'Investisseur Intelligent",
  },
  {
    text: "Connaissez votre cercle de compétence — et ne sortez jamais de ses limites sans raison impérieuse.",
    author: "Warren Buffett · Lettres annuelles",
  },
];

export default function HomePage() {
  const router = useRouter();
  const { t } = useI18n();
  const [mode, setMode] = useState<AnalyseMode>("cote");
  const [query, setQuery] = useState("");
  const quote = QUOTES[Math.floor(Math.random() * QUOTES.length)];

  // Pré-warming Railway : ping silencieux au mount pour réveiller le backend
  // pendant que l'utilisateur tape son ticker. Gain ~30s sur le cold start.
  useEffect(() => {
    if (!API_BASE) return;
    const ctrl = new AbortController();
    fetch(`${API_BASE}/health`, { signal: ctrl.signal, cache: "no-store" }).catch(() => {});
    return () => ctrl.abort();
  }, []);

  function handleAnalyze() {
    const q = query.trim();
    if (!q) {
      toast.error(
        mode === "cote"
          ? t("home.err_ticker_required")
          : t("home.err_siren_required")
      );
      return;
    }
    if (mode === "non_cote") {
      const clean = q.replace(/\s/g, "");
      if (!/^\d{9}$/.test(clean)) {
        toast.error(t("home.err_siren_format"));
        return;
      }
      router.push(`/pme?siren=${encodeURIComponent(clean)}&auto=1`);
      return;
    }
    router.push(`/analyse?q=${encodeURIComponent(q)}`);
  }

  function switchMode(m: AnalyseMode) {
    setMode(m);
    setQuery("");
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* min-h-screen : la page remplit toujours toute la hauteur du viewport,
          le bandeau réglementaire (du layout) reste sous le fold, visible au scroll */}
      <main className="min-h-screen max-w-5xl mx-auto px-6 py-24 w-full flex flex-col justify-center">
        {/* Bloc principal centré : Toggle + Hero + Search + Quick picks */}
        <div>
          {/* Toggle Coté / Non coté */}
          <div className="flex justify-center mb-6 animate-fade-in">
            <div className="inline-flex bg-ink-100 rounded-full p-1 border border-ink-200">
              <button
                type="button"
                onClick={() => switchMode("cote")}
                className={
                  "flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all " +
                  (mode === "cote"
                    ? "bg-white text-ink-900 shadow-sm"
                    : "text-ink-600 hover:text-ink-800")
                }
              >
                <Landmark className="w-4 h-4" />
                {t("home.listed_companies")}
              </button>
              <button
                type="button"
                onClick={() => switchMode("non_cote")}
                className={
                  "flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all " +
                  (mode === "non_cote"
                    ? "bg-white text-ink-900 shadow-sm"
                    : "text-ink-600 hover:text-ink-800")
                }
              >
                <Factory className="w-4 h-4" />
                {t("home.private_sme")}
              </button>
            </div>
          </div>

          {/* Hero */}
          <div className="text-center mb-10 animate-fade-in">
            <div className="section-label mb-3">{t("home.tag_ai_finance")}</div>
            <h1 className="text-2xl sm:text-3xl font-bold text-ink-900 tracking-tight">
              {mode === "cote" ? t("home.question_listed") : t("home.question_sme")}
            </h1>
            {mode === "non_cote" && (
              <p className="text-sm text-ink-500 mt-2 max-w-lg mx-auto">
                {t("home.sme_subtitle")}
              </p>
            )}
          </div>

          {/* Search bar */}
          <div className="space-y-3 max-w-2xl mx-auto">
            <input
              type="text"
              placeholder={
                mode === "cote"
                  ? t("home.placeholder_listed")
                  : t("home.placeholder_sme")
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
              className="input !text-base !py-3"
              autoFocus
            />
            <button
              onClick={handleAnalyze}
              className="btn-primary w-full !py-3 !text-base group"
            >
              {t("home.analyze_btn")}
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>

          {/* Quick picks — selon mode */}
          <div className="mt-10 space-y-6 animate-slide-up">
            {mode === "cote" ? (
              <>
                <QuickPickRow
                  icon={<Building2 className="w-3 h-3" />}
                  label={t("home.picks_companies")}
                  items={QUICK_TICKERS}
                  onPick={(t) => {
                    setQuery(t);
                    router.push(`/analyse?q=${encodeURIComponent(t)}`);
                  }}
                />
                <QuickPickRow
                  icon={<TrendingUp className="w-3 h-3" />}
                  label={t("home.picks_sectors")}
                  items={QUICK_SECTORS}
                  onPick={(t) => {
                    setQuery(t);
                    router.push(`/analyse?q=${encodeURIComponent(t)}`);
                  }}
                />
                <QuickPickRow
                  icon={<Globe2 className="w-3 h-3" />}
                  label={t("home.picks_indices")}
                  items={QUICK_INDICES}
                  onPick={(t) => {
                    setQuery(t);
                    router.push(`/analyse?q=${encodeURIComponent(t)}`);
                  }}
                />
              </>
            ) : (
              <QuickPickRow
                icon={<Factory className="w-3 h-3" />}
                label={t("home.picks_siren")}
                items={QUICK_SIRENS.map((s) => `${s.name} · ${s.siren}`)}
                onPick={(label) => {
                  const siren = label.split("·")[1]?.trim() || label;
                  setQuery(siren);
                  router.push(`/pme?siren=${encodeURIComponent(siren)}&auto=1`);
                }}
              />
            )}
          </div>
        </div>

        {/* Citation + fine bar en dessous */}
        <div className="mt-16 pt-10">
          <div className="text-center animate-fade-in">
            <p className="text-sm text-ink-500 italic max-w-lg mx-auto leading-relaxed">
              « {quote.text} »
            </p>
            <p className="text-2xs uppercase tracking-widest text-ink-400 mt-2">
              — {quote.author}
            </p>
          </div>
          {/* Fine bar passée SOUS la citation */}
          <div className="mt-10 border-t border-ink-200" />
        </div>
      </main>
    </div>
  );
}

interface QuickPickRowProps {
  icon: React.ReactNode;
  label: string;
  items: string[];
  onPick: (t: string) => void;
}

function QuickPickRow({ icon, label, items, onPick }: QuickPickRowProps) {
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1.5 section-label mb-3">
        {icon}
        {label}
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {items.map((t) => (
          <button
            key={t}
            onClick={() => onPick(t)}
            className="btn-secondary !py-2 !px-4 !text-sm hover:!border-navy-500 hover:!text-navy-500"
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
