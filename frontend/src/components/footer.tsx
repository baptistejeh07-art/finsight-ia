import Link from "next/link";
import Image from "next/image";

const SOURCES: { label: string; href: string }[] = [
  { label: "yfinance", href: "https://finance.yahoo.com" },
  { label: "FMP", href: "https://financialmodelingprep.com" },
  { label: "Finnhub", href: "https://finnhub.io" },
  { label: "FRED", href: "https://fred.stlouisfed.org" },
  { label: "EDGAR", href: "https://www.sec.gov/edgar" },
  { label: "Damodaran", href: "https://pages.stern.nyu.edu/~adamodar/" },
  { label: "FinBERT", href: "https://huggingface.co/ProsusAI/finbert" },
  { label: "Anthropic", href: "https://www.anthropic.com" },
  { label: "Groq", href: "https://groq.com" },
  { label: "Mistral", href: "https://mistral.ai" },
  { label: "Wikipedia", href: "https://en.wikipedia.org" },
];

function SourcesList() {
  return (
    <div className="text-xs text-ink-600 leading-relaxed">
      {SOURCES.map((s, i) => (
        <span key={s.label}>
          <a
            href={s.href}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-ink-900 hover:underline"
          >
            {s.label}
          </a>
          {i < SOURCES.length - 1 && <span className="text-ink-400"> · </span>}
        </span>
      ))}
    </div>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-ink-200 bg-ink-50/50 mt-16">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-sm">
          <div>
            <Image
              src="/logo.svg"
              alt="FinSight IA"
              width={1398}
              height={752}
              priority
              unoptimized
              className="object-contain h-10 w-auto mb-3"
            />
            <p className="text-ink-600 text-xs leading-relaxed">
              Plateforme d&apos;analyse financière institutionnelle propulsée par l&apos;IA.
            </p>
          </div>
          <div>
            <div className="section-label mb-3">Produit</div>
            <ul className="space-y-2">
              <li><Link href="/app" className="text-ink-700 hover:text-ink-900">Analyse société</Link></li>
              <li><Link href="/app" className="text-ink-700 hover:text-ink-900">Analyse secteur</Link></li>
              <li><Link href="/app" className="text-ink-700 hover:text-ink-900">Analyse indice</Link></li>
              <li><Link href="/comparatif" className="text-ink-700 hover:text-ink-900">Comparatif</Link></li>
            </ul>
          </div>
          <div>
            <div className="section-label mb-3">Légal</div>
            <ul className="space-y-2">
              <li><Link href="/cgu" className="text-ink-700 hover:text-ink-900">CGU</Link></li>
              <li><Link href="/privacy" className="text-ink-700 hover:text-ink-900">Confidentialité</Link></li>
              <li><Link href="/mentions-legales" className="text-ink-700 hover:text-ink-900">Mentions légales</Link></li>
              <li><Link href="/disclaimer" className="text-ink-700 hover:text-ink-900">Avertissement</Link></li>
              <li><Link href="/contact" className="text-ink-700 hover:text-ink-900">Contact</Link></li>
            </ul>
          </div>
          <div>
            <div className="section-label mb-3">Sources</div>
            <SourcesList />
          </div>
        </div>
        <div className="border-t border-ink-200 mt-8 pt-6 flex flex-col md:flex-row justify-between items-center gap-3 text-xs text-ink-500">
          <div>© {new Date().getFullYear()} FinSight IA · Tous droits réservés</div>
          <div className="flex items-center gap-1">
            <span>Outil d&apos;aide à la décision uniquement.</span>
            <span className="hidden md:inline">Pas un conseil en investissement.</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
