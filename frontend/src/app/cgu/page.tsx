import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Conditions générales d'utilisation",
  description:
    "CGU et CGV de FinSight IA : objet, accès, comptes utilisateurs, plans payants, propriété intellectuelle, responsabilité.",
};

export default function CguPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Conditions générales</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-4">
              CGU & CGV.
            </h1>
            <p className="text-text-muted text-sm">
              Version applicable à compter du 1er mai 2026
            </p>
          </div>
        </section>

        <article className="container-vitrine py-16 md:py-20 max-w-3xl space-y-12">
          <Section title="1. Objet">
            <p>
              Les présentes conditions générales (« CGU/CGV ») régissent
              l&apos;utilisation du service FinSight IA, accessible à
              l&apos;adresse finsight-ia.com, ainsi que la fourniture des
              prestations payantes associées. L&apos;utilisation du service
              implique l&apos;acceptation pleine et entière des présentes
              conditions.
            </p>
          </Section>

          <Section title="2. Définitions">
            <ul className="space-y-2">
              <li>
                <strong>Service</strong> : la plateforme FinSight IA et
                l&apos;ensemble de ses fonctionnalités (analyse, comparatif,
                portrait, livrables, API).
              </li>
              <li>
                <strong>Utilisateur</strong> : toute personne accédant au
                service, qu&apos;elle dispose ou non d&apos;un compte.
              </li>
              <li>
                <strong>Compte</strong> : espace personnel créé par
                l&apos;utilisateur pour accéder aux fonctionnalités payantes
                ou personnalisées.
              </li>
              <li>
                <strong>Livrables</strong> : les fichiers PDF, PowerPoint et
                Excel générés par le service à l&apos;issue d&apos;une analyse.
              </li>
              <li>
                <strong>Plan</strong> : formule d&apos;abonnement souscrite
                (Découverte, Essentiel, Pro, Équipe, Enterprise, API).
              </li>
            </ul>
          </Section>

          <Section title="3. Accès au service">
            <p>
              Le service est accessible 24 heures sur 24, 7 jours sur 7, sous
              réserve de toute interruption pour maintenance, mise à jour ou
              en cas de force majeure. FinSight ne garantit pas une
              disponibilité de 100 %, mais s&apos;engage à minimiser les
              interruptions et à les notifier dans la mesure du possible.
            </p>
            <p>
              Le service est destiné à un usage professionnel ou personnel
              légitime, à l&apos;exclusion de tout usage frauduleux, abusif
              ou contraire à la loi.
            </p>
          </Section>

          <Section title="4. Compte utilisateur">
            <p>
              L&apos;ouverture d&apos;un compte est nécessaire pour accéder
              aux plans payants et à l&apos;historique persistant.
              L&apos;utilisateur s&apos;engage à fournir des informations
              exactes et à les maintenir à jour.
            </p>
            <p>
              L&apos;utilisateur est seul responsable de la confidentialité
              de ses identifiants et de l&apos;usage qui en est fait. En cas
              de soupçon d&apos;usage frauduleux, il doit immédiatement en
              informer FinSight.
            </p>
          </Section>

          <Section title="5. Plans et tarifs">
            <p>
              Les plans payants et leurs tarifs sont décrits sur la{" "}
              <Link href="/#tarification" className="text-accent-primary underline">
                page Tarification
              </Link>
              . Les prix sont indiqués en euros, toutes taxes comprises (TTC).
              FinSight bénéficiant du régime de franchise en base de TVA
              (article 293 B du Code général des impôts), aucune TVA
              n&apos;est facturée et la mention « TVA non applicable, art.
              293 B du CGI » figure sur chaque facture.
            </p>
            <p>
              Tout abonnement est souscrit pour une durée d&apos;un mois ou
              d&apos;un an, renouvelable tacitement par périodes successives
              de même durée. L&apos;utilisateur peut résilier à tout moment
              depuis son espace compte ; la résiliation prend effet à la fin
              de la période en cours.
            </p>
          </Section>

          <Section title="6. Paiement">
            <p>
              Les paiements sont effectués par carte bancaire via le
              prestataire Stripe. FinSight ne stocke aucune donnée de carte
              bancaire. Les factures sont émises automatiquement à chaque
              échéance et accessibles dans l&apos;espace compte.
            </p>
            <p>
              En cas d&apos;échec de paiement, le service peut être suspendu
              après notification par email et un délai de régularisation de
              7 jours.
            </p>
          </Section>

          <Section title="7. Droit de rétractation">
            <p>
              Conformément à l&apos;article L221-28 du code de la
              consommation, le droit de rétractation ne s&apos;applique pas
              aux services pleinement exécutés avant la fin du délai de
              rétractation et dont l&apos;exécution a commencé avec
              l&apos;accord exprès du consommateur. Toute analyse lancée par
              l&apos;utilisateur est considérée comme une demande
              d&apos;exécution immédiate.
            </p>
            <p>
              Toutefois, si vous n&apos;avez lancé aucune analyse durant les
              14 jours suivant votre souscription, vous pouvez demander un
              remboursement intégral à{" "}
              <a
                href="mailto:contact@finsight-ia.com"
                className="text-accent-primary underline"
              >
                contact@finsight-ia.com
              </a>
              .
            </p>
          </Section>

          <Section title="8. Propriété intellectuelle">
            <p>
              FinSight reste propriétaire de l&apos;ensemble des éléments du
              service : code, méthodologies, modèles, design,
              chartes graphiques, marque. L&apos;utilisateur dispose
              d&apos;un droit d&apos;usage personnel et non transférable
              limité à la durée de son abonnement.
            </p>
            <p>
              Les livrables produits (PDF, PPTX, XLSX) à partir
              d&apos;analyses lancées par l&apos;utilisateur appartiennent à
              ce dernier, qui peut les utiliser librement dans son activité
              professionnelle ou personnelle, à l&apos;exclusion de tout
              usage de revente ou redistribution massive sans autorisation
              écrite préalable.
            </p>
          </Section>

          <Section title="9. Responsabilité — usage du service">
            <p className="font-medium text-text-primary">
              FinSight fournit un outil d&apos;aide à la décision, et non un
              conseil en investissement personnalisé.
            </p>
            <p>
              Les analyses produites s&apos;appuient sur des données et des
              modèles dont la qualité, bien que rigoureusement contrôlée, ne
              peut être garantie sans exception. L&apos;utilisateur reste
              seul juge de ses décisions d&apos;investissement et assume
              entièrement la responsabilité des actes qu&apos;il pose sur la
              base des informations fournies par le service.
            </p>
            <p>
              FinSight ne pourra en aucun cas être tenu responsable des
              pertes financières, manques à gagner, ou conséquences directes
              ou indirectes liées à l&apos;utilisation du service. Voir
              également la page{" "}
              <Link href="/disclaimer" className="text-accent-primary underline">
                Disclaimer
              </Link>
              .
            </p>
          </Section>

          <Section title="10. Force majeure">
            <p>
              Aucune des parties ne pourra être tenue responsable d&apos;un
              manquement aux présentes conditions résultant d&apos;un cas de
              force majeure tel que défini par la jurisprudence française.
            </p>
          </Section>

          <Section title="11. Modification des conditions">
            <p>
              FinSight se réserve le droit de modifier les présentes
              conditions à tout moment. Toute modification substantielle sera
              notifiée par email avec un préavis minimum de 30 jours. À
              défaut d&apos;acceptation, l&apos;utilisateur peut résilier
              son abonnement sans frais.
            </p>
          </Section>

          <Section title="12. Droit applicable et juridiction">
            <p>
              Les présentes conditions sont soumises au droit français. En
              cas de litige, les parties s&apos;efforceront de trouver une
              solution amiable. À défaut, le médiateur de la consommation
              compétent peut être saisi avant toute action judiciaire. En
              dernier ressort, les tribunaux du ressort de la cour
              d&apos;appel de Paris seront seuls compétents.
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
