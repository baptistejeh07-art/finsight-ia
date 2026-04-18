import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description:
    "Données collectées, finalités, durées de conservation, droits utilisateurs, cookies. Politique de confidentialité conforme RGPD.",
};

export default function PrivacyPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Politique de confidentialité</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-4">
              Vos données, votre contrôle.
            </h1>
            <p className="text-text-muted text-sm">
              Conforme RGPD — dernière mise à jour : avril 2026
            </p>
          </div>
        </section>

        <article className="container-vitrine py-16 md:py-20 max-w-3xl space-y-12">
          <Section title="1. Responsable du traitement">
            <p>
              Le responsable du traitement des données à caractère personnel
              collectées sur finsight-ia.com est l&apos;éditeur du site,
              Baptiste Jeh (voir{" "}
              <Link href="/mentions-legales" className="text-accent-primary underline">
                mentions légales
              </Link>
              ).
            </p>
            <p>
              Pour toute question relative à la protection de vos données,
              contactez le délégué à la protection des données :{" "}
              <a
                href="mailto:privacy@finsight-ia.com"
                className="text-accent-primary underline"
              >
                privacy@finsight-ia.com
              </a>
              .
            </p>
          </Section>

          <Section title="2. Données collectées">
            <p>
              FinSight collecte uniquement les données strictement nécessaires
              au fonctionnement du service, en application du principe de
              minimisation (article 5.1.c du RGPD).
            </p>
            <DataTable
              rows={[
                ["Compte utilisateur", "Email, mot de passe haché (bcrypt)", "Authentification, gestion du compte"],
                ["Préférences", "Plan souscrit, paramètres d'affichage, mode sombre/clair", "Personnalisation de l'expérience"],
                ["Analyses lancées", "Tickers/secteurs/indices analysés, dates, résultats", "Historique utilisateur, facturation à l'usage"],
                ["Conversation Q&A", "Texte des messages échangés avec l'assistant", "Fonctionnement du service Q&A"],
                ["Données techniques", "Adresse IP, user-agent, logs HTTP", "Sécurité, prévention de la fraude"],
                ["Paiement (à venir)", "Email, montant, identifiant de transaction Stripe", "Facturation, remboursements"],
              ]}
            />
          </Section>

          <Section title="3. Finalités et bases légales">
            <ul className="space-y-3">
              {[
                ["Exécution du contrat (art. 6.1.b RGPD)", "Création de compte, gestion des analyses, accès aux livrables, paiement."],
                ["Intérêt légitime (art. 6.1.f RGPD)", "Sécurité du service, prévention de la fraude, amélioration de la qualité des analyses."],
                ["Obligation légale (art. 6.1.c RGPD)", "Conservation des factures (10 ans, code de commerce)."],
                ["Consentement (art. 6.1.a RGPD)", "Cookies non essentiels, communications marketing."],
              ].map(([base, finalite]) => (
                <li key={base} className="flex flex-col">
                  <span className="text-text-primary font-medium">{base}</span>
                  <span className="text-sm text-text-muted">{finalite}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="4. Durées de conservation">
            <ul className="space-y-2">
              <li>
                <strong>Compte utilisateur</strong> : tant que le compte est
                actif. Suppression sous 30 jours après demande de fermeture.
              </li>
              <li>
                <strong>Historique d&apos;analyses</strong> : 36 mois après la
                dernière connexion, sauf demande de suppression anticipée.
              </li>
              <li>
                <strong>Factures</strong> : 10 ans, conformément à
                l&apos;article L.123-22 du code de commerce.
              </li>
              <li>
                <strong>Logs techniques</strong> : 12 mois, en application des
                recommandations de la CNIL.
              </li>
              <li>
                <strong>Données de paiement</strong> : non stockées par
                FinSight (intégralement gérées par Stripe).
              </li>
            </ul>
          </Section>

          <Section title="5. Destinataires et sous-traitants">
            <p>
              Vos données ne sont jamais vendues, louées ou échangées. Elles
              sont accessibles uniquement à l&apos;équipe FinSight (sous
              accord de confidentialité) et à nos sous-traitants techniques
              (hébergeurs, fournisseurs LLM, prestataire de paiement).
            </p>
            <p>
              La liste exhaustive et publique de nos sous-traitants est
              disponible sur la{" "}
              <Link href="/securite" className="text-accent-primary underline">
                page Sécurité & conformité
              </Link>
              .
            </p>
          </Section>

          <Section title="6. Transferts hors Union européenne">
            <p>
              Certains sous-traitants traitant vos données sont situés aux
              États-Unis (Anthropic, Groq, Stripe). Ces transferts
              s&apos;appuient sur le{" "}
              <strong>Data Privacy Framework (DPF)</strong>, cadre adéquat
              reconnu par la décision de la Commission européenne du 10 juillet
              2023, ainsi que sur les clauses contractuelles types adoptées
              par la Commission.
            </p>
          </Section>

          <Section title="7. Vos droits">
            <p>
              Conformément aux articles 15 à 22 du RGPD, vous disposez des
              droits suivants sur vos données personnelles :
            </p>
            <ul className="space-y-2">
              <li>
                <strong>Droit d&apos;accès</strong> : obtenir une copie de vos
                données.
              </li>
              <li>
                <strong>Droit de rectification</strong> : faire corriger des
                données inexactes.
              </li>
              <li>
                <strong>Droit à l&apos;effacement</strong> (« droit à
                l&apos;oubli ») : demander la suppression de vos données.
              </li>
              <li>
                <strong>Droit à la limitation du traitement</strong> : suspendre
                temporairement l&apos;usage de vos données.
              </li>
              <li>
                <strong>Droit à la portabilité</strong> : récupérer vos données
                dans un format structuré, lisible par machine.
              </li>
              <li>
                <strong>Droit d&apos;opposition</strong> : vous opposer au
                traitement de vos données pour motifs légitimes.
              </li>
              <li>
                <strong>Directives post-mortem</strong> : organiser le sort de
                vos données après votre décès.
              </li>
            </ul>
            <p>
              Pour exercer l&apos;un de ces droits, écrivez à{" "}
              <a
                href="mailto:privacy@finsight-ia.com"
                className="text-accent-primary underline"
              >
                privacy@finsight-ia.com
              </a>
              . Nous répondrons dans un délai maximum d&apos;un mois (article
              12 RGPD).
            </p>
          </Section>

          <Section title="8. Cookies">
            <p>
              FinSight utilise un strict minimum de cookies, strictement
              nécessaires au fonctionnement du site. Aucun cookie publicitaire
              ni de tracking comportemental n&apos;est déposé sans votre
              consentement explicite.
            </p>
            <ul className="space-y-2">
              <li>
                <strong>Cookies fonctionnels</strong> (exemptés de consentement)
                : authentification, préférence de mode sombre, panier en cours.
              </li>
              <li>
                <strong>Cookies analytiques</strong> (consentement requis,
                anonymisés) : mesure d&apos;audience interne (à venir).
              </li>
            </ul>
          </Section>

          <Section title="9. Sécurité">
            <p>
              FinSight applique des mesures techniques et organisationnelles
              proportionnées au niveau de risque (chiffrement TLS 1.3 en
              transit, AES-256 au repos, accès restreints, audit régulier).
              Voir la{" "}
              <Link href="/securite" className="text-accent-primary underline">
                page Sécurité
              </Link>{" "}
              pour le détail.
            </p>
          </Section>

          <Section title="10. Réclamations">
            <p>
              Vous pouvez à tout moment introduire une réclamation auprès de
              la <strong>CNIL</strong> (Commission nationale de
              l&apos;informatique et des libertés), 3 place de Fontenoy,
              75007 Paris, ou en ligne sur{" "}
              <a
                href="https://www.cnil.fr"
                className="text-accent-primary underline"
                target="_blank"
                rel="noreferrer"
              >
                cnil.fr
              </a>
              .
            </p>
          </Section>

          <Section title="11. Mise à jour de la politique">
            <p>
              FinSight peut être amené à modifier la présente politique. Toute
              modification substantielle vous sera notifiée par email ou
              bandeau in-app au moins 30 jours avant son entrée en vigueur.
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

function DataTable({ rows }: { rows: string[][] }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full text-sm border border-border-default rounded-lg overflow-hidden bg-surface-elevated">
        <thead>
          <tr className="bg-surface-muted border-b border-border-default">
            <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
              Catégorie
            </th>
            <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
              Données
            </th>
            <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
              Finalité
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-default">
          {rows.map(([cat, data, finality]) => (
            <tr key={cat}>
              <td className="py-3 px-4 text-text-primary font-medium">{cat}</td>
              <td className="py-3 px-4 text-text-secondary">{data}</td>
              <td className="py-3 px-4 text-text-muted">{finality}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
