import type { Metadata } from "next";
import { AlertTriangle } from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Avertissement — FinSight n'est pas un conseil en investissement",
  description:
    "FinSight fournit un outil d'aide à l'analyse, et non un conseil en investissement personnalisé au sens de l'AMF. Utilisateur seul responsable de ses décisions.",
};

export default function DisclaimerPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-2xs uppercase tracking-widest font-semibold mb-5">
              <AlertTriangle className="w-3 h-3" />
              Avertissement important
            </div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              FinSight n&apos;est pas un conseil en investissement.
            </h1>
            <p className="text-lg text-text-secondary leading-relaxed">
              Lisez attentivement ce document avant d&apos;utiliser FinSight
              pour prendre une décision financière.
            </p>
          </div>
        </section>

        <article className="container-vitrine py-16 md:py-20 max-w-3xl space-y-10">
          <Section title="Nature du service">
            <p>
              FinSight IA est une plateforme technologique d&apos;aide à
              l&apos;analyse financière. Elle agrège des données publiques
              de sources tierces (yfinance, Finnhub, FMP, news), exécute des
              calculs déterministes (DCF, ratios, valorisation par multiples)
              et produit une synthèse éditoriale assistée par intelligence
              artificielle.
            </p>
            <p>
              <strong>
                FinSight ne fournit aucun conseil en investissement
                personnalisé au sens de l&apos;article L.321-1 du code
                monétaire et financier.
              </strong>{" "}
              Le service ne tient pas compte de votre situation patrimoniale,
              de vos objectifs, de votre horizon de placement ou de votre
              tolérance au risque.
            </p>
          </Section>

          <Section title="Statut réglementaire">
            <p>
              FinSight n&apos;est ni un Conseiller en Investissement
              Financier (CIF), ni un Prestataire de Services
              d&apos;Investissement (PSI), ni un courtier, ni une société de
              gestion. Il n&apos;est immatriculé auprès d&apos;aucune de ces
              catégories à l&apos;Orias ou à l&apos;AMF.
            </p>
            <p>
              En conséquence, FinSight n&apos;est pas autorisé à fournir un
              conseil personnalisé en investissement, à recommander
              l&apos;achat ou la vente d&apos;instruments financiers à un
              client identifié, ni à exécuter des ordres de bourse pour le
              compte de tiers.
            </p>
          </Section>

          <Section title="Limites des analyses produites">
            <ul className="space-y-2">
              <li>
                Les analyses s&apos;appuient sur des données historiques. Les
                performances passées ne préjugent pas des performances
                futures.
              </li>
                <li>
                Les modèles de valorisation reposent sur des hypothèses
                (croissance, marges, taux d&apos;actualisation) qui peuvent
                s&apos;écarter de la réalité future.
              </li>
              <li>
                Les commentaires éditoriaux générés par IA sont contrôlés par
                quatre agents de gouvernance, mais aucun système ne garantit
                à 100 % l&apos;absence d&apos;erreur ou d&apos;omission.
              </li>
              <li>
                Les marchés financiers sont par nature incertains. Tout
                investissement comporte un risque de perte en capital,
                pouvant aller jusqu&apos;à la perte totale du capital
                investi.
              </li>
            </ul>
          </Section>

          <Section title="Votre responsabilité">
            <p>
              Vous restez seul juge de l&apos;opportunité et de
              l&apos;adéquation des décisions que vous prenez à partir des
              informations fournies par FinSight. Avant toute opération
              significative, nous vous recommandons fortement de :
            </p>
            <ul className="space-y-2 mt-3">
              <li>
                Consulter un conseiller en investissement financier (CIF)
                immatriculé à l&apos;Orias ;
              </li>
              <li>
                Vérifier indépendamment les données et hypothèses présentes
                dans nos analyses ;
              </li>
              <li>
                Évaluer si l&apos;investissement envisagé correspond à votre
                situation personnelle, votre horizon de placement et votre
                tolérance au risque ;
              </li>
              <li>
                Lire attentivement la documentation officielle (DICI,
                prospectus, rapport annuel) émise par l&apos;émetteur de
                l&apos;instrument financier.
              </li>
            </ul>
          </Section>

          <Section title="Limitation de responsabilité">
            <p>
              FinSight ne pourra en aucun cas être tenu responsable des
              pertes financières, manques à gagner, ou conséquences directes
              ou indirectes — patrimoniales, fiscales, juridiques —
              résultant de l&apos;usage que vous faites du service.
            </p>
            <p>
              Cette limitation s&apos;applique dans toute la mesure permise
              par la loi et n&apos;exclut pas les responsabilités qui ne
              peuvent légalement être limitées (faute lourde, dol, dommages
              corporels).
            </p>
          </Section>

          <Section title="En cas de doute">
            <p>
              Si vous avez le moindre doute sur le traitement à donner à une
              analyse FinSight ou sur l&apos;opportunité d&apos;une décision
              d&apos;investissement, ne prenez pas cette décision.
              Sollicitez un professionnel régulé.
            </p>
          </Section>
        </article>
      </main>

      <MarketingFooter />
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary leading-tight mb-5">
        {title}
      </h2>
      <div className="space-y-4 text-text-secondary leading-[1.75]">{children}</div>
    </section>
  );
}
