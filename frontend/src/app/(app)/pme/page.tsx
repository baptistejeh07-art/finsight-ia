"use client";

import { useEffect, useRef, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, Info, Building2, MapPin } from "lucide-react";
import { analyzePmeSync, searchPme, type PmeSearchResult } from "@/lib/api";
import { useI18n } from "@/i18n/provider";

function PmePageContent() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [siren, setSiren] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<PmeSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searching, setSearching] = useState(false);
  const [pendingName, setPendingName] = useState<string | null>(null);
  const autoLaunched = useRef(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Auto-launch si ?siren=XXX&auto=1 (venant de /app toggle PME)
  useEffect(() => {
    if (autoLaunched.current) return;
    const urlSiren = params.get("siren");
    const auto = params.get("auto");
    if (urlSiren && auto === "1") {
      autoLaunched.current = true;
      setSiren(urlSiren);
      void launchAnalyze(urlSiren);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Autocomplete : si saisie texte (pas 9 chiffres), debounce 300ms → /search/pme
  useEffect(() => {
    const v = siren.trim();
    const cleanDigits = v.replace(/\s/g, "");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (v.length < 2 || /^\d{9}$/.test(cleanDigits)) {
      setSuggestions([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await searchPme(v, 8);
        setSuggestions(res.results);
        setShowDropdown(true);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [siren]);

  function handleSelectSuggestion(s: PmeSearchResult) {
    setShowDropdown(false);
    setSuggestions([]);
    setSiren(s.siren);
    const displayName = s.denomination || s.siren;
    setPendingName(displayName);
    console.info("[pme] select", { siren: s.siren, name: s.denomination });
    void launchAnalyze(s.siren, displayName);
  }

  async function launchAnalyze(inputSiren: string, knownName?: string) {
    const cleanSiren = inputSiren.replace(/\s/g, "");
    if (!/^\d{9}$/.test(cleanSiren)) {
      setError("Le SIREN doit contenir exactement 9 chiffres.");
      return;
    }
    setError(null);
    setLoading(true);
    console.info("[pme] launchAnalyze", { siren: cleanSiren, knownName });
    try {
      const res = await analyzePmeSync(cleanSiren);
      if (res.success) {
        const returnedName = (res.data as { denomination?: string })?.denomination;
        const label = returnedName || knownName || cleanSiren;
        // Garde-fou : alerte si le backend retourne une dénomination qui ne correspond
        // clairement pas au nom sélectionné (ex: on a cliqué TF1 mais reçu STELLANTIS).
        if (
          knownName &&
          returnedName &&
          returnedName.toUpperCase().slice(0, 4) !== knownName.toUpperCase().slice(0, 4)
        ) {
          console.warn("[pme] MISMATCH", { clicked: knownName, returned: returnedName, siren: cleanSiren });
        }
        try {
          sessionStorage.setItem(
            `analysis_${res.request_id}`,
            JSON.stringify({
              success: true,
              request_id: res.request_id,
              elapsed_ms: res.elapsed_ms,
              data: res.data,
              files: res.files,
              kind: "pme",
              label,
            })
          );
        } catch {}
        router.push(
          `/resultats/${res.request_id}?ticker=${encodeURIComponent(label)}&kind=pme`
        );
      } else {
        setError(res.error || "Erreur inconnue");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur API");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    await launchAnalyze(siren);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-md bg-navy-50 flex items-center justify-center">
          <Building2 className="w-5 h-5 text-navy-500" />
        </div>
        <h1 className="text-3xl font-bold text-ink-900">{t("analyze.pme")}</h1>
      </div>
      <p className="text-ink-600 mb-8 max-w-2xl">{t("analyze.pme_subtitle")}</p>

      <form onSubmit={handleAnalyze} className="bg-white border border-ink-200 rounded-md p-6 mb-6">
        <label className="block text-sm font-medium text-ink-700 mb-2">
          {t("analyze.pme_input_label")}
        </label>
        <div className="flex gap-2 relative">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={siren}
              onChange={(e) => setSiren(e.target.value)}
              onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
              placeholder={t("analyze.pme_input_placeholder")}
              className="w-full px-4 py-3 border border-ink-200 rounded-md text-base focus:outline-none focus:border-navy-500"
              disabled={loading}
              autoComplete="off"
            />
            {searching && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-ink-200 border-t-navy-500 rounded-full animate-spin" />
            )}
            {showDropdown && suggestions.length > 0 && !loading && (
              <ul className="absolute z-10 left-0 right-0 mt-1 bg-white border border-ink-200 rounded-md shadow-lg max-h-80 overflow-auto">
                {suggestions.map((s) => (
                  <li
                    key={s.siren}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleSelectSuggestion(s);
                    }}
                    className="px-3 py-2 hover:bg-navy-50 cursor-pointer border-b border-ink-100 last:border-b-0"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold text-ink-900 truncate">
                        {s.denomination || s.siren}
                      </span>
                      <span className="text-[10px] font-mono text-ink-400 shrink-0">
                        {s.siren}
                      </span>
                    </div>
                    <div className="text-[11px] text-ink-500 flex items-center gap-2 mt-0.5">
                      {s.ville && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {s.ville}
                        </span>
                      )}
                      {s.code_naf && <span className="font-mono">NAF {s.code_naf}</span>}
                      {s.dirigeant && <span className="truncate">· {s.dirigeant}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || siren.replace(/\s/g, "").length < 9}
            className="px-6 py-3 rounded-md bg-navy-500 text-white font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {t("analyze.loading_short")}
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                {t("analyze.launch")}
              </>
            )}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-signal-sell">{error}</p>}
        {loading && pendingName && (
          <p className="mt-3 text-xs text-navy-600 font-mono">
            Analyse en cours — {pendingName} ({siren.replace(/\s/g, "")})
          </p>
        )}
        <p className="mt-2 text-xs text-ink-500">{t("analyze.pme_input_hint")}</p>
      </form>

      <div className="bg-navy-50 border border-navy-200 rounded-md p-5 flex items-start gap-3">
        <Info className="w-5 h-5 text-navy-500 shrink-0 mt-0.5" />
        <div className="text-sm text-ink-700">
          <p className="font-medium text-ink-900 mb-1">{t("analyze.pme_how_title")}</p>
          <ul className="space-y-1 text-ink-600">
            <li>• {t("analyze.pme_how_1")}</li>
            <li>• {t("analyze.pme_how_2")}</li>
            <li>• {t("analyze.pme_how_3")}</li>
            <li>• {t("analyze.pme_how_4")}</li>
            <li>• {t("analyze.pme_how_5")}</li>
          </ul>
          <p className="mt-2 text-xs text-ink-500">{t("analyze.pme_disclaimer_mifid")}</p>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-3 gap-4 text-center">
        <ExampleCard
          siren="552032534"
          name="Danone"
          sector="Holding"
          onClick={(s) => {
            setSiren(formatSirenDisplay(s));
            void launchAnalyze(s);
          }}
        />
        <ExampleCard
          siren="552081317"
          name="EDF"
          sector="Énergie"
          onClick={(s) => {
            setSiren(formatSirenDisplay(s));
            void launchAnalyze(s);
          }}
        />
        <ExampleCard
          siren="542107651"
          name="LVMH"
          sector="Luxe"
          onClick={(s) => {
            setSiren(formatSirenDisplay(s));
            void launchAnalyze(s);
          }}
        />
      </div>
    </div>
  );
}

function formatSirenDisplay(siren: string): string {
  const clean = siren.replace(/\D/g, "");
  if (clean.length !== 9) return siren;
  return `${clean.slice(0, 3)} ${clean.slice(3, 6)} ${clean.slice(6)}`;
}

function ExampleCard({
  siren,
  name,
  sector,
  onClick,
}: {
  siren: string;
  name: string;
  sector: string;
  onClick: (s: string) => void;
}) {
  const display = formatSirenDisplay(siren);
  return (
    <button
      type="button"
      onClick={() => onClick(siren)}
      className="bg-white border border-ink-200 rounded-md px-3 py-2 hover:border-navy-500 hover:bg-navy-50 transition-colors text-left"
    >
      <div className="text-xs text-ink-500 uppercase tracking-wider">{sector}</div>
      <div className="text-sm font-semibold text-ink-900">{name}</div>
      <div className="text-xs font-mono text-ink-500">{display}</div>
    </button>
  );
}

export default function PmePage() {
  return (
    <Suspense fallback={<div className="max-w-3xl mx-auto px-6 py-12 text-sm text-ink-500">Chargement…</div>}>
      <PmePageContent />
    </Suspense>
  );
}
