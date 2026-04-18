import type { Metadata } from "next";
import Link from "next/link";
import { Lock, Server, Globe, ShieldCheck, KeyRound, FileWarning } from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Sécurité & conformité",
  description:
    "Hébergement européen, chiffrement TLS et au repos, sous-traitants RGPD listés, certifications en cours. Politique de sécurité FinSight IA.",
};

export default function SecuritePage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Sécurité & conformité</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              La sécurité n&apos;est pas une option.
            </h1>
            <p className="text-lg text-text-secondary leading-relaxed">
              FinSight traite des données financières professionnelles. Nous
              appliquons les standards de l&apos;industrie pour
              l&apos;hébergement, le chiffrement, la gestion des accès et la
              conformité RGPD. Cette page documente précisément où vivent vos
              données et qui y accède.
            </p>
          </div>
        </section>

        {/* Hébergement */}
        <section className="border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">01 · Hébergement</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Tout en Europe.
                </h2>
              </div>
              <div className="md:col-span-8 text-text-secondary leading-relaxed">
                <p>
                  L&apos;intégralité de l&apos;infrastructure FinSight est
                  hébergée dans l&apos;Union européenne, conforme RGPD by
                  design.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              <InfraCard
                icon={<Globe className="w-4 h-4" />}
                provider="Vercel"
                role="Frontend Next.js"
                region="Europe (Frankfurt) — fra1"
              />
              <InfraCard
                icon={<Server className="w-4 h-4" />}
                provider="Railway"
                role="Backend FastAPI"
                region="Europe (Amsterdam) — eu-west"
              />
              <InfraCard
                icon={<Lock className="w-4 h-4" />}
                provider="Supabase"
                role="Auth & base de données"
                region="Europe (Frankfurt) — eu-central-1"
              />
            </div>

            <p className="mt-6 text-sm text-text-muted leading-relaxed">
              Aucune donnée client n&apos;est traitée hors de l&apos;UE. Les
              CDN qui distribuent les assets statiques publics (images, CSS,
              JS) peuvent répliquer ces fichiers en edge mondial pour des
              raisons de performance, mais ils ne contiennent jamais de donnée
              personnelle.
            </p>
          </div>
        </section>

        {/* Chiffrement */}
        <section className="bg-surface-muted border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">02 · Chiffrement</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  En transit et au repos.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <ul className="space-y-3">
                  {[
                    [
                      "TLS 1.3 systématique",
                      "Toute communication entre votre navigateur, le frontend Vercel et le backend Railway est chiffrée en TLS 1.3 (HTTPS forcé, redirection HSTS, certificats Let's Encrypt renouvelés automatiquement).",
                    ],
                    [
                      "Chiffrement au repos",
                      "Les données stockées dans Supabase (auth, comptes, futurs historiques d'analyses) sont chiffrées AES-256 sur disque par défaut.",
                    ],
                    [
                      "Secrets isolés",
                      "Les clés API (Anthropic, Groq, yfinance, Finnhub, FMP) sont stockées exclusivement dans des variables d'environnement chiffrées côté Vercel et Railway. Elles ne sont jamais exposées dans le code source ou dans le bundle frontend.",
                    ],
                    [
                      "Aucun stockage de paiement",
                      "FinSight ne stocke aucune donnée de carte bancaire. Le traitement des paiements est délégué intégralement à un prestataire PCI-DSS niveau 1 (Stripe, à activer lors du lancement payant).",
                    ],
                  ].map(([title, desc]) => (
                    <li key={title} className="flex gap-3">
                      <KeyRound className="w-4 h-4 text-accent-primary shrink-0 mt-1" />
                      <div>
                        <div className="text-text-primary font-medium">{title}</div>
                        <div className="text-sm mt-1">{desc}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Sous-traitants */}
        <section className="border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-8">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">03 · Sous-traitants</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Liste exhaustive et publique.
                </h2>
              </div>
              <div className="md:col-span-8 text-text-secondary leading-relaxed">
                <p>
                  Conformément à l&apos;article 28 du RGPD, voici la liste
                  complète de nos sous-traitants traitant des données à
                  caractère personnel pour le compte de FinSight.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-border-default rounded-lg overflow-hidden bg-surface-elevated">
                <thead>
                  <tr className="bg-surface-muted border-b border-border-default">
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Sous-traitant
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Rôle
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Données traitées
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Localisation
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {[
                    ["Vercel Inc.", "Hébergement frontend", "Logs techniques, IP visiteurs", "UE (Frankfurt)"],
                    ["Railway Corp.", "Hébergement backend", "Logs techniques, requêtes API", "UE (Amsterdam)"],
                    ["Supabase Inc.", "Auth & base de données", "Email, mot de passe haché, métadonnées compte", "UE (Frankfurt)"],
                    ["Anthropic PBC", "LLM (synthèse, Q&A)", "Texte des prompts utilisateurs", "US (cadre DPF)"],
                    ["Groq Inc.", "LLM (synthèse principale)", "Texte des prompts utilisateurs", "US (cadre DPF)"],
                    ["Stripe (à venir)", "Paiements", "Email, montant, ID transaction", "UE & US (cadre DPF)"],
                    ["Resend (à venir)", "Emails transactionnels", "Email destinataire, contenu transactionnel", "UE"],
                  ].map(([name, role, data, loc]) => (
                    <tr key={name} className="hover:bg-surface-muted/50">
                      <td className="py-3 px-4 text-text-primary font-medium">{name}</td>
                      <td className="py-3 px-4 text-text-secondary">{role}</td>
                      <td className="py-3 px-4 text-text-muted">{data}</td>
                      <td className="py-3 px-4 text-text-muted">{loc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-6 text-sm text-text-muted leading-relaxed">
              Les transferts de données vers les États-Unis (Anthropic, Groq,
              Stripe) s&apos;appuient sur le Data Privacy Framework (DPF), cadre
              de transfert reconnu adéquat par la décision de la Commission
              européenne du 10 juillet 2023.
            </p>
          </div>
        </section>

        {/* Certifications */}
        <section className="bg-surface-muted border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">04 · Certifications</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  En cours de structuration.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  FinSight est une jeune plateforme. Nous travaillons à
                  l&apos;obtention progressive des certifications attendues par
                  nos clients institutionnels.
                </p>
                <ul className="space-y-3 mt-2">
                  {[
                    [
                      "ISO/IEC 27001",
                      "Démarche initiée. Audit blanc prévu fin 2026, certification visée pour 2027.",
                      "in-progress",
                    ],
                    [
                      "SOC 2 Type II",
                      "Évaluation en cours pour le marché US. Sans engagement de date à ce stade.",
                      "study",
                    ],
                    [
                      "RGPD",
                      "Conformité by-design respectée depuis l'origine du projet (registre de traitement, sous-traitants listés, droits utilisateurs implémentés).",
                      "compliant",
                    ],
                    [
                      "DSP2 / SCA",
                      "Non applicable : FinSight ne réalise aucun service de paiement régulé.",
                      "n/a",
                    ],
                  ].map(([title, desc, status]) => (
                    <li key={title} className="flex gap-3">
                      <ShieldCheck className="w-4 h-4 text-accent-primary shrink-0 mt-1" />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-text-primary font-medium">{title}</span>
                          <StatusBadge status={status as string} />
                        </div>
                        <div className="text-sm mt-1">{desc}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Signalement */}
        <section>
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">05 · Signaler une vulnérabilité</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Disclosure responsable.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Vous avez identifié une faille de sécurité ? Contactez-nous
                  immédiatement à{" "}
                  <a
                    href="mailto:security@finsight-ia.com"
                    className="text-accent-primary underline"
                  >
                    security@finsight-ia.com
                  </a>
                  . Nous traitons toute remontée sous 48 heures et tenons les
                  chercheurs informés de chaque étape de la résolution.
                </p>
                <p>
                  Aucune action en justice ne sera engagée contre les chercheurs
                  qui respectent ce cadre : pas d&apos;exfiltration de données
                  réelles, pas d&apos;atteinte à la disponibilité, signalement
                  responsable avant divulgation publique.
                </p>
                <div className="mt-6 inline-flex items-center gap-3 text-sm text-text-muted">
                  <FileWarning className="w-4 h-4" />
                  Pas de programme bug bounty rémunéré pour le moment, mais
                  reconnaissance publique pour les contributions valides.
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function InfraCard({
  icon,
  provider,
  role,
  region,
}: {
  icon: React.ReactNode;
  provider: string;
  role: string;
  region: string;
}) {
  return (
    <div className="card-vitrine">
      <div className="w-9 h-9 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center mb-3">
        {icon}
      </div>
      <div className="text-sm font-semibold text-text-primary">{provider}</div>
      <div className="text-xs text-text-muted mt-1">{role}</div>
      <div className="text-2xs uppercase tracking-widest text-text-muted mt-3">{region}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    "in-progress": { label: "En cours", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
    study: { label: "Étude", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
    compliant: { label: "Conforme", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" },
    "n/a": { label: "N/A", className: "bg-text-muted/15 text-text-muted" },
  };
  const conf = map[status] ?? map["n/a"];
  return (
    <span
      className={`text-2xs uppercase tracking-wider font-semibold px-2 py-0.5 rounded ${conf.className}`}
    >
      {conf.label}
    </span>
  );
}
