import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata = { title: "Conditions d'utilisation" };

export default function CGUPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-6 py-12 w-full">
        <div className="section-label mb-2">Légal</div>
        <h1 className="text-3xl font-bold text-ink-900 mb-2 tracking-tight">
          Conditions générales d&apos;utilisation
        </h1>
        <p className="text-sm text-ink-500 mb-8">Version du {new Date().toLocaleDateString("fr-FR")}</p>

        <article className="prose prose-sm max-w-none space-y-6 text-ink-700">
          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">1. Objet</h2>
            <p>
              Les présentes Conditions générales d&apos;utilisation (« CGU ») régissent l&apos;accès et l&apos;utilisation de la plateforme FinSight IA (« la Plateforme »),
              accessible à l&apos;adresse <strong>finsight-ia.com</strong>, éditée par FinSight IA.
              En accédant à la Plateforme ou en créant un compte, l&apos;utilisateur accepte sans réserve les présentes CGU.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">2. Description du service</h2>
            <p>
              FinSight IA est une plateforme d&apos;analyse financière propulsée par l&apos;intelligence artificielle.
              Elle propose des rapports d&apos;analyse sur des sociétés cotées, secteurs et indices boursiers, basés sur des données publiques (yfinance, Financial Modeling Prep, Finnhub, FRED, EDGAR, Damodaran)
              et des modèles d&apos;intelligence artificielle (LLM).
            </p>
            <p className="mt-3">
              <strong>FinSight IA est un outil d&apos;aide à la décision et NE constitue PAS un conseil en investissement personnalisé au sens des articles L.541-1 et suivants du Code monétaire et financier français.</strong>
              L&apos;utilisateur reste seul juge de ses décisions d&apos;investissement.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">3. Création de compte</h2>
            <p>
              L&apos;accès aux fonctionnalités complètes nécessite la création d&apos;un compte. L&apos;utilisateur s&apos;engage à fournir des informations exactes
              et à maintenir la confidentialité de ses identifiants. Un compte invité est disponible pour découvrir le service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">4. Propriété intellectuelle</h2>
            <p>
              Le contenu des analyses générées par la Plateforme (textes, graphiques, ratios, fichiers PDF/PPTX/Excel) est mis à disposition de l&apos;utilisateur pour son usage personnel.
              La revente ou redistribution publique sans accord écrit préalable est interdite. Les marques, logos et code source de la Plateforme demeurent la propriété exclusive de FinSight IA.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">5. Limitation de responsabilité</h2>
            <p>
              FinSight IA met en œuvre tous les moyens raisonnables pour assurer la qualité des analyses, mais ne garantit ni leur exactitude absolue, ni leur exhaustivité,
              ni leur adéquation à une situation particulière. <strong>FinSight IA ne pourra en aucun cas être tenue responsable des pertes financières directes ou indirectes
              résultant de décisions d&apos;investissement prises sur la base de la Plateforme.</strong>
            </p>
            <p className="mt-3">
              Les données financières provenant de tiers (yfinance, FMP, etc.) peuvent comporter des erreurs, retards ou indisponibilités. FinSight IA ne saurait être tenue responsable de tels dysfonctionnements.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">6. Disponibilité du service</h2>
            <p>
              La Plateforme est accessible 24h/24, 7j/7, sous réserve de maintenances programmées ou d&apos;événements extérieurs (panne réseau, attaque informatique, etc.).
              FinSight IA s&apos;engage à informer les utilisateurs des interruptions majeures dans la mesure du possible.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">7. Données personnelles</h2>
            <p>
              Le traitement des données personnelles est régi par notre <a href="/privacy" className="text-navy-500 underline">Politique de confidentialité</a>.
              L&apos;utilisateur dispose d&apos;un droit d&apos;accès, de rectification, d&apos;effacement et d&apos;opposition conformément au RGPD.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">8. Modification des CGU</h2>
            <p>
              FinSight IA se réserve le droit de modifier les présentes CGU à tout moment. Les utilisateurs seront informés des modifications substantielles par notification ou email.
              La poursuite de l&apos;utilisation de la Plateforme après notification vaut acceptation des nouvelles CGU.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">9. Loi applicable et juridiction</h2>
            <p>
              Les présentes CGU sont soumises au droit français. Tout litige relatif à leur interprétation ou leur exécution relève de la compétence exclusive des tribunaux de Paris,
              sauf disposition légale impérative contraire.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">10. Contact</h2>
            <p>
              Pour toute question relative aux présentes CGU : <a href="mailto:contact@finsight-ia.com" className="text-navy-500 underline">contact@finsight-ia.com</a>
            </p>
          </section>
        </article>
      </main>
      <Footer />
    </div>
  );
}
