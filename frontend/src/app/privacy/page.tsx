import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata = { title: "Politique de confidentialité" };

export default function PrivacyPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-6 py-12 w-full">
        <div className="section-label mb-2">Légal</div>
        <h1 className="text-3xl font-bold text-ink-900 mb-2 tracking-tight">
          Politique de confidentialité
        </h1>
        <p className="text-sm text-ink-500 mb-8">
          Conforme RGPD · Version du {new Date().toLocaleDateString("fr-FR")}
        </p>

        <article className="prose prose-sm max-w-none space-y-6 text-ink-700">
          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">1. Responsable du traitement</h2>
            <p>
              FinSight IA, dont le siège social est situé en France, est responsable du traitement des données personnelles
              collectées via la plateforme finsight-ia.com.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">2. Données collectées</h2>
            <p>Nous collectons les données suivantes :</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Compte utilisateur</strong> : email, mot de passe (hashé), photo de profil (si Google OAuth)</li>
              <li><strong>Données d&apos;usage</strong> : tickers analysés, secteurs consultés, dates des analyses</li>
              <li><strong>Données techniques</strong> : adresse IP, type de navigateur, OS (logs serveur, conservés 30 jours)</li>
            </ul>
            <p className="mt-3">
              <strong>Aucune donnée bancaire</strong> n&apos;est collectée par FinSight IA (les paiements éventuels seront gérés par un prestataire tiers conforme PCI-DSS).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">3. Finalités du traitement</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li>Création et gestion du compte utilisateur</li>
              <li>Fourniture du service d&apos;analyse financière</li>
              <li>Personnalisation de l&apos;expérience (historique, préférences)</li>
              <li>Amélioration du service (statistiques agrégées et anonymisées)</li>
              <li>Communication avec les utilisateurs (notifications produit, support)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">4. Base légale</h2>
            <p>
              Les traitements sont fondés sur :
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Exécution du contrat</strong> (CGU) pour la fourniture du service</li>
              <li><strong>Consentement</strong> pour les communications marketing optionnelles</li>
              <li><strong>Intérêt légitime</strong> pour les statistiques d&apos;usage agrégées et la sécurité</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">5. Destinataires</h2>
            <p>Vos données sont accessibles uniquement par :</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>L&apos;équipe FinSight IA (administration technique et support)</li>
              <li>Nos sous-traitants techniques :
                <ul className="list-disc pl-6 mt-1">
                  <li><strong>Supabase</strong> (hébergement DB + auth) — UE</li>
                  <li><strong>Vercel</strong> (hébergement frontend) — global</li>
                  <li><strong>Railway</strong> (hébergement backend) — global</li>
                  <li><strong>Google</strong> (authentification OAuth optionnelle) — global</li>
                </ul>
              </li>
            </ul>
            <p className="mt-3">
              Aucune donnée n&apos;est revendue à des tiers à des fins commerciales.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">6. Durée de conservation</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Compte actif</strong> : jusqu&apos;à la suppression du compte par l&apos;utilisateur</li>
              <li><strong>Compte inactif</strong> : suppression automatique après 3 ans d&apos;inactivité</li>
              <li><strong>Logs serveur</strong> : 30 jours</li>
              <li><strong>Statistiques anonymisées</strong> : illimitée</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">7. Vos droits (RGPD)</h2>
            <p>Conformément au RGPD, vous disposez des droits suivants :</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Droit d&apos;accès</strong> : obtenir copie de vos données</li>
              <li><strong>Droit de rectification</strong> : corriger les données inexactes</li>
              <li><strong>Droit à l&apos;effacement</strong> (« droit à l&apos;oubli ») : supprimer votre compte</li>
              <li><strong>Droit d&apos;opposition</strong> : refuser certains traitements (marketing notamment)</li>
              <li><strong>Droit à la portabilité</strong> : récupérer vos données dans un format structuré</li>
              <li><strong>Droit de limitation</strong> : geler temporairement le traitement</li>
            </ul>
            <p className="mt-3">
              Pour exercer ces droits : <a href="mailto:privacy@finsight-ia.com" className="text-navy-500 underline">privacy@finsight-ia.com</a>
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">8. Cookies</h2>
            <p>
              FinSight IA utilise uniquement des cookies <strong>strictement nécessaires</strong> au fonctionnement
              (session d&apos;authentification, préférences utilisateur). <strong>Aucun cookie publicitaire ou de tracking tiers</strong> n&apos;est utilisé.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">9. Sécurité</h2>
            <p>
              Nous mettons en œuvre des mesures techniques et organisationnelles appropriées pour protéger vos données :
              chiffrement TLS, mots de passe hashés (bcrypt), accès restreint, audits réguliers.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-ink-900 mt-6 mb-2">10. Réclamations</h2>
            <p>
              Si vous estimez que vos droits ne sont pas respectés, vous pouvez introduire une réclamation auprès de la
              <strong> Commission nationale de l&apos;informatique et des libertés (CNIL)</strong> :
              <a href="https://www.cnil.fr" className="text-navy-500 underline ml-1">cnil.fr</a>
            </p>
          </section>
        </article>
      </main>
      <Footer />
    </div>
  );
}
