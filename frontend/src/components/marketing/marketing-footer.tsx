import Link from "next/link";
import { Linkedin, Twitter, Github } from "lucide-react";
import { LogoMark } from "./logo-mark";

const COLUMNS = [
  {
    title: "Produits",
    links: [
      ["Analyse Société", "/app"],
      ["Analyse Secteur", "/app"],
      ["Analyse Indice", "/app"],
      ["Comparatif", "/comparatif"],
      ["Portrait d'entreprise", "/cas-usage/portrait"],
      ["API", "/contact?plan=api"],
    ],
  },
  {
    title: "Solutions",
    links: [
      ["Banques d'investissement", "/cas-usage/conseil"],
      ["Cabinets comptables", "/cas-usage/finance-entreprise"],
      ["Conseillers en gestion", "/cas-usage/gerant"],
      ["Hedge funds", "/cas-usage/investissement"],
      ["Écoles & universités", "/cas-usage/education"],
    ],
  },
  {
    title: "Ressources",
    links: [
      ["FinSight expliqué", "/analyste"],
      ["Méthodologie", "/methodologie"],
      ["Annonces", "/#sorties"],
      ["Cas d'utilisation", "/cas-usage"],
      ["FAQ", "/#faq"],
      ["Contact", "/contact"],
    ],
  },
  {
    title: "Entreprise",
    links: [
      ["À propos", "/about"],
      ["Collaboration", "/collaboration"],
      ["Tarification", "/#tarification"],
      ["Sécurité & conformité", "/securite"],
      ["Mentions légales", "/mentions-legales"],
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="bg-surface-inverse text-text-inverse border-t border-border-default/30">
      <div className="container-vitrine py-16">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10">
          <div className="md:col-span-3">
            <LogoMark variant="inverse" size="xl" />

            <p className="mt-4 text-sm text-text-inverse/60 leading-relaxed max-w-xs">
              Analyses financières institutionnelles, livrées en quelques
              minutes.
            </p>
            <div className="mt-6 flex items-center gap-3">
              <SocialLink href="https://www.linkedin.com" label="LinkedIn">
                <Linkedin className="w-4 h-4" />
              </SocialLink>
              <SocialLink href="https://twitter.com" label="X / Twitter">
                <Twitter className="w-4 h-4" />
              </SocialLink>
              <SocialLink href="https://github.com" label="GitHub">
                <Github className="w-4 h-4" />
              </SocialLink>
            </div>
          </div>

          <div className="md:col-span-9 grid grid-cols-2 md:grid-cols-4 gap-8">
            {COLUMNS.map((col) => (
              <div key={col.title}>
                <div className="text-xs font-semibold tracking-widest uppercase text-text-inverse/50 mb-4">
                  {col.title}
                </div>
                <ul className="space-y-2.5">
                  {col.links.map(([label, href]) => (
                    <li key={href}>
                      <Link
                        href={href}
                        className="text-sm text-text-inverse/80 hover:text-text-inverse transition-colors"
                      >
                        {label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Avertissement réglementaire — toujours visible */}
        <div className="mt-12 pt-8 border-t border-text-inverse/10">
          <div className="rounded-lg border border-text-inverse/15 bg-text-inverse/5 p-4 text-xs text-text-inverse/70 leading-relaxed">
            <span className="font-semibold text-text-inverse/90">Avertissement.</span>{" "}
            FinSight IA fournit un outil d&apos;aide à l&apos;analyse, et non
            un conseil en investissement personnalisé au sens de
            l&apos;article L.321-1 du code monétaire et financier. Aucune
            information du service ne constitue une recommandation
            d&apos;achat ou de vente. L&apos;utilisateur reste seul juge de
            ses décisions et assume entièrement les risques associés.{" "}
            <Link
              href="/disclaimer"
              className="underline hover:text-text-inverse"
            >
              Lire l&apos;avertissement complet
            </Link>
            .
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-text-inverse/10 flex flex-col md:flex-row md:items-center justify-between gap-4 text-2xs text-text-inverse/50">
          <div>© {new Date().getFullYear()} FinSight IA. Tous droits réservés.</div>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Link href="/mentions-legales" className="hover:text-text-inverse">
              Mentions légales
            </Link>
            <Link href="/cgu" className="hover:text-text-inverse">
              CGU
            </Link>
            <Link href="/privacy" className="hover:text-text-inverse">
              Confidentialité
            </Link>
            <Link href="/securite" className="hover:text-text-inverse">
              Sécurité
            </Link>
            <Link href="/disclaimer" className="hover:text-text-inverse">
              Avertissement
            </Link>
            <Link href="/contact" className="hover:text-text-inverse">
              Contact
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

function SocialLink({
  href,
  label,
  children,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      className="w-8 h-8 flex items-center justify-center rounded-md border border-text-inverse/20 text-text-inverse/70 hover:text-text-inverse hover:border-text-inverse/50 transition-colors"
    >
      {children}
    </a>
  );
}
