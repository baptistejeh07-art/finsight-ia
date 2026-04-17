import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata = { title: "À propos" };

export default function AboutPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-6 py-12 w-full">
        <div className="section-label mb-2">À propos</div>
        <h1 className="text-3xl font-bold text-ink-900 mb-6 tracking-tight">
          La plateforme d&apos;analyse financière nouvelle génération
        </h1>

        <div className="space-y-8 text-sm text-ink-700 leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-ink-900 mb-2">Notre mission</h2>
            <p>
              Démocratiser l&apos;accès à l&apos;analyse financière institutionnelle.
              Ce que des analystes sell-side font en plusieurs heures dans une banque d&apos;investissement,
              FinSight IA le délivre en 2 minutes — accessible à tous.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mb-2">Comment ça marche</h2>
            <p>
              Notre plateforme combine plusieurs agents d&apos;intelligence artificielle (Claude, Llama, Mistral, Gemini)
              avec des sources de données financières institutionnelles (yfinance, Financial Modeling Prep, Finnhub, FRED, EDGAR, Damodaran).
              Le résultat : des analyses cohérentes, chiffrées, contextualisées, livrées sous forme de :
            </p>
            <ul className="list-disc pl-6 mt-3 space-y-1">
              <li>Interface web interactive (verdict, KPIs, scénarios)</li>
              <li>Rapport PDF 20 pages format institutionnel</li>
              <li>Pitchbook PowerPoint Bloomberg-style</li>
              <li>Modèle Excel DCF complet</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mb-2">Couverture</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Sociétés</strong> : 4000+ sociétés cotées (US, EU, UK, Japan, etc.)</li>
              <li><strong>Secteurs</strong> : 11 secteurs GICS dans 5 indices majeurs</li>
              <li><strong>Indices</strong> : S&amp;P 500, CAC 40, DAX 40, FTSE 100, Euro Stoxx 50</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mb-2">Important</h2>
            <p className="bg-ink-50 border-l-2 border-ink-300 p-4 italic">
              FinSight IA est un outil d&apos;aide à la décision. Il ne constitue pas un conseil en investissement personnalisé.
              Les performances passées ne préjugent pas des performances futures. Consultez un conseiller agréé pour vos décisions d&apos;investissement.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
