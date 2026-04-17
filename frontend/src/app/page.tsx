"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, TrendingUp, Globe2 } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import toast from "react-hot-toast";

const QUICK_TICKERS = ["AAPL", "TSLA", "MSFT", "MC.PA", "OR.PA", "NVDA"];
const QUICK_SECTORS = ["Technologie", "Santé", "Banques", "Énergie", "Industrie"];
const QUICK_INDICES = ["CAC 40", "S&P 500", "DAX 40", "FTSE 100", "Euro Stoxx 50"];

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
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<"interface" | "files">("interface");
  const [devise, setDevise] = useState("USD");
  const quote = QUOTES[Math.floor(Math.random() * QUOTES.length)];

  function handleAnalyze() {
    const q = query.trim();
    if (!q) {
      toast.error("Saisissez un ticker, secteur ou indice");
      return;
    }
    router.push(`/analyse?q=${encodeURIComponent(q)}&devise=${devise}&scope=${scope}`);
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-5xl mx-auto px-6 py-12 w-full">
        {/* Hero */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="section-label mb-3">Analyse Financière IA</div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-900 mb-2 tracking-tight">
            Société, indice ou secteur ?
          </h1>
          <p className="text-sm text-ink-600 max-w-md mx-auto">
            Analyse institutionnelle complète en 2 minutes. DCF, ratios, scénarios, comparatifs.
          </p>
        </div>

        {/* Search bar */}
        <div className="space-y-3 max-w-2xl mx-auto">
          <input
            type="text"
            placeholder="AAPL, CAC 40, Technology…"
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
            Analyser
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Options sous la barre */}
          <div className="flex items-center justify-between text-xs text-ink-500 mt-3 px-1">
            <div className="flex items-center gap-3">
              <span className="section-label">Devise</span>
              <select
                value={devise}
                onChange={(e) => setDevise(e.target.value)}
                className="bg-transparent border-b border-ink-300 text-ink-900 font-medium focus:outline-none focus:border-navy-500"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="JPY">JPY</option>
              </select>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  checked={scope === "interface"}
                  onChange={() => setScope("interface")}
                />
                <span>Interface uniquement</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  checked={scope === "files"}
                  onChange={() => setScope("files")}
                />
                <span>Interface + PDF/PPTX</span>
              </label>
            </div>
          </div>
        </div>

        {/* Quick picks */}
        <div className="mt-10 space-y-6 animate-slide-up">
          <QuickPickRow
            icon={<Building2 className="w-3 h-3" />}
            label="Sociétés"
            items={QUICK_TICKERS}
            onPick={(t) => {
              setQuery(t);
              router.push(`/analyse?q=${encodeURIComponent(t)}&devise=${devise}&scope=${scope}`);
            }}
          />
          <QuickPickRow
            icon={<TrendingUp className="w-3 h-3" />}
            label="Secteurs"
            items={QUICK_SECTORS}
            onPick={(t) => {
              setQuery(t);
              router.push(`/analyse?q=${encodeURIComponent(t)}&devise=${devise}&scope=${scope}`);
            }}
          />
          <QuickPickRow
            icon={<Globe2 className="w-3 h-3" />}
            label="Indices"
            items={QUICK_INDICES}
            onPick={(t) => {
              setQuery(t);
              router.push(`/analyse?q=${encodeURIComponent(t)}&devise=${devise}&scope=${scope}`);
            }}
          />
        </div>

        {/* Quote */}
        <div className="text-center mt-16 mb-8 animate-fade-in">
          <p className="text-sm text-ink-500 italic max-w-lg mx-auto leading-relaxed">
            « {quote.text} »
          </p>
          <p className="text-2xs uppercase tracking-widest text-ink-400 mt-2">
            — {quote.author}
          </p>
        </div>
      </main>

      <Footer />
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
