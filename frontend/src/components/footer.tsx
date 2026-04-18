import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-ink-200 bg-ink-50/50 mt-16">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-sm">
          <div>
            <div className="font-bold text-ink-900 mb-3 tracking-wider">FINSIGHT</div>
            <p className="text-ink-600 text-xs leading-relaxed">
              Plateforme d&apos;analyse financière institutionnelle propulsée par l&apos;IA.
            </p>
          </div>
          <div>
            <div className="section-label mb-3">Produit</div>
            <ul className="space-y-2">
              <li><Link href="/" className="text-ink-700 hover:text-ink-900">Analyse société</Link></li>
              <li><Link href="/" className="text-ink-700 hover:text-ink-900">Analyse secteur</Link></li>
              <li><Link href="/" className="text-ink-700 hover:text-ink-900">Analyse indice</Link></li>
              <li><Link href="/comparatif" className="text-ink-700 hover:text-ink-900">Comparatif</Link></li>
            </ul>
          </div>
          <div>
            <div className="section-label mb-3">Légal</div>
            <ul className="space-y-2">
              <li><Link href="/cgu" className="text-ink-700 hover:text-ink-900">CGU</Link></li>
              <li><Link href="/privacy" className="text-ink-700 hover:text-ink-900">Confidentialité</Link></li>
              <li><Link href="/about" className="text-ink-700 hover:text-ink-900">À propos</Link></li>
              <li><Link href="/contact" className="text-ink-700 hover:text-ink-900">Contact</Link></li>
            </ul>
          </div>
          <div>
            <div className="section-label mb-3">Sources</div>
            <ul className="space-y-2 text-ink-600 text-xs">
              <li>yfinance · FMP · Finnhub</li>
              <li>FRED · EDGAR · Damodaran</li>
              <li>FinBERT · Anthropic · Groq</li>
            </ul>
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
