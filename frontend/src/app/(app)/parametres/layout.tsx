"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { slug: "general", label: "Général" },
  { slug: "compte", label: "Compte" },
  { slug: "confidentialite", label: "Confidentialité" },
  { slug: "facturation", label: "Facturation" },
  { slug: "utilisation", label: "Utilisation" },
  { slug: "capacites", label: "Capacités" },
  { slug: "connecteurs", label: "Connecteurs" },
];

export default function ParametresLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#FAFAF5]">
      <div className="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-12">
        {/* Titre Paramètres (serif, grand) */}
        <h1 className="text-3xl md:text-4xl font-semibold text-ink-900 mb-8 md:mb-12 tracking-tight"
            style={{ fontFamily: "'Copernicus', 'Libre Caslon Text', Georgia, serif" }}>
          Paramètres
        </h1>

        <div className="flex flex-col md:flex-row gap-6 md:gap-12">
          {/* Sidebar secondaire : onglets */}
          <aside className="w-full md:w-52 shrink-0">
            <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible">
              {TABS.map((t) => {
                const href = `/parametres/${t.slug}`;
                const active = pathname === href || (pathname === "/parametres" && t.slug === "general");
                return (
                  <Link
                    key={t.slug}
                    href={href}
                    className={
                      "px-3 py-2 rounded-md text-sm font-semibold transition-colors whitespace-nowrap " +
                      (active
                        ? "bg-ink-100 text-ink-900"
                        : "text-ink-700 hover:bg-ink-100/50 hover:text-ink-900")
                    }
                  >
                    {t.label}
                  </Link>
                );
              })}
            </nav>
          </aside>

          {/* Contenu principal */}
          <div className="flex-1 min-w-0">{children}</div>
        </div>
      </div>
    </div>
  );
}
