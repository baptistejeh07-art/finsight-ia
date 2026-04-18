import type { Metadata } from "next";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Mentions légales",
  description:
    "Éditeur, hébergeurs, directeur de la publication, propriété intellectuelle. Mentions légales du site finsight-ia.com.",
};

export default function MentionsLegalesPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Mentions légales</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              Mentions légales.
            </h1>
            <p className="text-text-muted">Dernière mise à jour : avril 2026</p>
          </div>
        </section>

        <article className="container-vitrine py-16 md:py-20 max-w-3xl space-y-12">
          <Section title="1. Éditeur du site">
            <p>
              Le site <strong>finsight-ia.com</strong> est édité par Baptiste
              Jeh, étudiant entrepreneur en BTS Comptabilité et Gestion en
              alternance, en cours d&apos;immatriculation sous statut
              entrepreneur individuel à la rentrée 2026.
            </p>
            <KeyVal label="Nom de l'éditeur">Baptiste Jeh</KeyVal>
            <KeyVal label="Statut">Entrepreneur individuel (en cours)</KeyVal>
            <KeyVal label="Adresse de contact">contact@finsight-ia.com</KeyVal>
            <KeyVal label="Email du DPO">privacy@finsight-ia.com</KeyVal>
            <p className="text-sm text-text-muted">
              Le site est édité à titre personnel dans l&apos;attente de
              l&apos;immatriculation officielle. Les mentions ci-dessus seront
              complétées (numéro SIREN, code APE, capital social) dès
              l&apos;ouverture du statut juridique en 2026.
            </p>
          </Section>

          <Section title="2. Directeur de la publication">
            <p>Baptiste Jeh, en sa qualité d&apos;éditeur du site.</p>
          </Section>

          <Section title="3. Hébergeurs">
            <p>
              Le site et ses services sont hébergés par les prestataires
              suivants. Pour le détail des données traitées par chacun, se
              référer à la{" "}
              <a href="/securite" className="text-accent-primary underline">
                page Sécurité
              </a>
              .
            </p>
            <div className="space-y-4 mt-4">
              <Hebergeur
                name="Vercel Inc."
                role="Frontend (Next.js)"
                address="440 N Barranca Ave #4133, Covina, CA 91723, États-Unis — datacenter UE Frankfurt"
              />
              <Hebergeur
                name="Railway Corp."
                role="Backend API (FastAPI)"
                address="2261 Market Street #4382, San Francisco, CA 94114, États-Unis — datacenter UE Amsterdam"
              />
              <Hebergeur
                name="Supabase Inc."
                role="Authentification et base de données"
                address="970 Toa Payoh North #07-04, Singapore 318992 — datacenter UE Frankfurt"
              />
            </div>
          </Section>

          <Section title="4. Propriété intellectuelle">
            <p>
              L&apos;ensemble des contenus présents sur le site
              finsight-ia.com (textes, graphismes, logos, icônes, code source,
              méthodologies, algorithmes propriétaires) est la propriété
              exclusive de l&apos;éditeur, à l&apos;exception des contenus
              relevant de prestataires tiers explicitement identifiés.
            </p>
            <p>
              Toute reproduction, représentation, modification, publication ou
              adaptation totale ou partielle de ces contenus, par quelque
              procédé que ce soit et sur quelque support que ce soit, est
              interdite sans autorisation écrite préalable de l&apos;éditeur,
              à l&apos;exception des usages prévus par les conditions
              d&apos;utilisation du service.
            </p>
            <p>
              Les marques mentionnées (yfinance, Anthropic, Groq, Vercel,
              Supabase, etc.) appartiennent à leurs détenteurs respectifs.
            </p>
          </Section>

          <Section title="5. Données financières et marques tierces">
            <p>
              Les données financières affichées par le service proviennent de
              fournisseurs tiers (Yahoo Finance, Finnhub, FMP) et sont
              utilisées dans le cadre de leurs conditions générales
              d&apos;utilisation respectives. Les noms et logos de sociétés
              cotées affichés à des fins d&apos;identification dans le service
              restent la propriété de leurs détenteurs.
            </p>
          </Section>

          <Section title="6. Liens hypertextes">
            <p>
              Le site finsight-ia.com peut contenir des liens vers
              d&apos;autres sites internet ou ressources externes.
              L&apos;éditeur ne peut être tenu responsable du contenu de ces
              sites tiers ni des dommages susceptibles d&apos;y être liés.
            </p>
          </Section>

          <Section title="7. Signalement de contenu">
            <p>
              Tout contenu du site susceptible de porter atteinte aux droits
              d&apos;un tiers peut être signalé par email à{" "}
              <a
                href="mailto:legal@finsight-ia.com"
                className="text-accent-primary underline"
              >
                legal@finsight-ia.com
              </a>
              . Les signalements seront traités sous 7 jours ouvrés.
            </p>
          </Section>

          <Section title="8. Droit applicable et juridiction">
            <p>
              Les présentes mentions légales sont régies par le droit
              français. En cas de litige et à défaut de résolution amiable, les
              tribunaux français seront seuls compétents.
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

function KeyVal({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-12 gap-4 py-2 border-b border-border-default last:border-0">
      <div className="col-span-4 text-2xs uppercase tracking-widest text-text-muted">
        {label}
      </div>
      <div className="col-span-8 text-text-primary">{children}</div>
    </div>
  );
}

function Hebergeur({
  name,
  role,
  address,
}: {
  name: string;
  role: string;
  address: string;
}) {
  return (
    <div className="card-vitrine !p-4">
      <div className="text-sm font-semibold text-text-primary">{name}</div>
      <div className="text-xs text-text-muted mt-0.5">{role}</div>
      <div className="text-xs text-text-muted mt-2 leading-relaxed">{address}</div>
    </div>
  );
}
