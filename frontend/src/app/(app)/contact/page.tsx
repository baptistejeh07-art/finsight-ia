import { Mail, MessageCircle, AlertTriangle } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata = { title: "Contact" };

export default function ContactPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-6 py-12 w-full">
        <div className="section-label mb-2">Contact</div>
        <h1 className="text-3xl font-bold text-ink-900 mb-2 tracking-tight">
          Une question ? Un retour ?
        </h1>
        <p className="text-sm text-ink-600 mb-10">
          Nous lisons tous les messages. Réponse sous 48h en jour ouvré.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
          <ContactCard
            icon={<MessageCircle className="w-5 h-5" />}
            label="Questions produit & support"
            description="Bugs, questions d'usage, suggestions d'amélioration."
            email="contact@finsight-ia.com"
          />
          <ContactCard
            icon={<AlertTriangle className="w-5 h-5" />}
            label="Données personnelles · RGPD"
            description="Accès, rectification, effacement de vos données."
            email="privacy@finsight-ia.com"
          />
        </div>

        <div className="card bg-ink-50 border-ink-200">
          <div className="section-label mb-3">Avant de nous écrire</div>
          <ul className="text-sm text-ink-700 space-y-2 list-disc pl-5">
            <li>
              FinSight IA est un <strong>outil d&apos;aide à la décision</strong>, pas un conseiller en investissement personnalisé.
              Pour toute décision financière, consultez un conseiller agréé.
            </li>
            <li>
              Les données financières proviennent de sources publiques (yfinance, FMP, Finnhub, FRED, EDGAR).
              Un ticker peut être indisponible temporairement — réessayez dans quelques minutes.
            </li>
            <li>
              Pour les signalements de bug, précisez le ticker/indice/secteur concerné, l&apos;heure de l&apos;analyse et le navigateur utilisé.
            </li>
          </ul>
        </div>

        <div className="mt-12 text-center">
          <div className="section-label mb-3">Adresse</div>
          <p className="text-sm text-ink-700">
            FinSight IA<br />
            France · UE
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function ContactCard({
  icon,
  label,
  description,
  email,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  email: string;
}) {
  return (
    <a
      href={`mailto:${email}`}
      className="card-hover flex items-start gap-3 group"
    >
      <div className="text-navy-500 mt-0.5 shrink-0">{icon}</div>
      <div className="flex-1">
        <div className="text-sm font-semibold text-ink-900 group-hover:text-navy-500 transition-colors">
          {label}
        </div>
        <div className="text-xs text-ink-500 mt-1 mb-2">{description}</div>
        <div className="text-xs text-navy-500 font-mono flex items-center gap-1.5">
          <Mail className="w-3 h-3" />
          {email}
        </div>
      </div>
    </a>
  );
}
