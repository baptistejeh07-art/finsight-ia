"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, ArrowUpRight, ArrowLeft } from "lucide-react";
import { LogoMark } from "./logo-mark";
import { ThemeToggle } from "../theme-toggle";

type MenuKey = "cas" | "produits" | "collab" | null;

export function MarketingNav() {
  const [open, setOpen] = useState<MenuKey>(null);
  const [scrolled, setScrolled] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  // Affiche le bouton "Retour" sur toutes les pages secondaires (pas /).
  const isSubpage = pathname !== "/" && pathname !== null;
  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/");
    }
  }

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function openMenu(key: MenuKey) {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(key);
  }
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(null), 120);
  }

  return (
    <header
      className={`sticky top-0 z-50 transition-colors backdrop-blur ${
        scrolled
          ? "bg-surface/85 border-b border-border-default"
          : "bg-surface/60 border-b border-transparent"
      }`}
    >
      <div className="container-vitrine h-16 flex items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          {isSubpage && (
            <button
              type="button"
              onClick={goBack}
              className="hidden sm:inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
              title="Retour à la page précédente"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Retour
            </button>
          )}
          <LogoMark />
        </div>

        <nav className="hidden lg:flex items-center gap-1" onMouseLeave={scheduleClose}>
          <NavMenuTrigger
            label="Cas d'utilisation"
            isOpen={open === "cas"}
            onOpen={() => openMenu("cas")}
          />
          <NavMenuTrigger
            label="Produits"
            isOpen={open === "produits"}
            onOpen={() => openMenu("produits")}
          />
          <NavMenuTrigger
            label="Collaboration"
            isOpen={open === "collab"}
            onOpen={() => openMenu("collab")}
          />
          <Link
            href="#tarification"
            onMouseEnter={() => openMenu(null)}
            className="px-3 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Tarification
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/app"
            className="btn-cta !py-2 !px-4 group"
          >
            Essayez FinSight
            <ArrowUpRight className="w-3.5 h-3.5 ml-1.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </div>
      </div>

      {/* Méga-menus */}
      {open === "cas" && (
        <MegaMenu onMouseEnter={() => openMenu("cas")} onMouseLeave={scheduleClose}>
          <CasUtilisationContent />
        </MegaMenu>
      )}
      {open === "produits" && (
        <MegaMenu onMouseEnter={() => openMenu("produits")} onMouseLeave={scheduleClose}>
          <ProduitsContent />
        </MegaMenu>
      )}
      {open === "collab" && (
        <MegaMenu onMouseEnter={() => openMenu("collab")} onMouseLeave={scheduleClose}>
          <CollabContent />
        </MegaMenu>
      )}
    </header>
  );
}

function NavMenuTrigger({
  label,
  isOpen,
  onOpen,
}: {
  label: string;
  isOpen: boolean;
  onOpen: () => void;
}) {
  return (
    <button
      onMouseEnter={onOpen}
      onFocus={onOpen}
      className={`flex items-center gap-1 px-3 py-2 text-sm transition-colors ${
        isOpen
          ? "text-text-primary"
          : "text-text-secondary hover:text-text-primary"
      }`}
    >
      {label}
      <ChevronDown
        className={`w-3.5 h-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`}
      />
    </button>
  );
}

function MegaMenu({
  children,
  onMouseEnter,
  onMouseLeave,
}: {
  children: React.ReactNode;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className="absolute left-0 right-0 top-full bg-surface-elevated border-b border-border-default shadow-sm animate-slide-down"
    >
      <div className="container-vitrine py-8">{children}</div>
    </div>
  );
}

/* === Contenus des méga-menus === */

function CasUtilisationContent() {
  return (
    <div className="grid grid-cols-12 gap-8">
      <div className="col-span-3">
        <div className="label-vitrine mb-4">Cas d&apos;utilisation</div>
        <p className="text-sm text-text-muted leading-relaxed">
          Découvrez comment des analystes, gérants et étudiants utilisent
          FinSight au quotidien.
        </p>
      </div>
      <div className="col-span-4">
        <div className="label-vitrine mb-4">Catégories</div>
        <ul className="space-y-2.5">
          {[
            ["Investissement", "/cas-usage/investissement"],
            ["Conseil & M&A", "/cas-usage/conseil"],
            ["Finance d'entreprise", "/cas-usage/finance-entreprise"],
            ["Recherche actions", "/cas-usage/recherche"],
            ["Éducation & formation", "/cas-usage/education"],
          ].map(([label, href]) => (
            <li key={href}>
              <Link
                href={href}
                className="text-sm text-text-primary hover:text-accent-primary transition-colors"
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div className="col-span-4">
        <div className="label-vitrine mb-4">Rôles</div>
        <ul className="space-y-2.5">
          {[
            ["Analyste financier", "/cas-usage/analyste"],
            ["Gérant de portefeuille", "/cas-usage/gerant"],
            ["CFO / DAF", "/cas-usage/cfo"],
            ["Investisseur particulier", "/cas-usage/particulier"],
            ["Étudiant en finance", "/cas-usage/etudiant"],
          ].map(([label, href]) => (
            <li key={href}>
              <Link
                href={href}
                className="text-sm text-text-primary hover:text-accent-primary transition-colors"
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div className="col-span-1 flex items-end justify-end">
        <Link
          href="/cas-usage"
          className="text-xs text-text-muted hover:text-text-primary inline-flex items-center gap-1"
        >
          Tout voir <ArrowUpRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}

function ProduitsContent() {
  const items = [
    {
      title: "Analyse Société",
      desc: "DCF, ratios, scénarios, comparables — pitchbook 20 slides.",
      href: "/app",
    },
    {
      title: "Analyse Secteur",
      desc: "Drivers macro, positionnement concurrentiel, top performers.",
      href: "/app",
    },
    {
      title: "Analyse Indice",
      desc: "ERP, allocation optimale, valorisations agrégées.",
      href: "/app",
    },
    {
      title: "Comparatif Société",
      desc: "Benchmark côte à côte de 2 à 6 sociétés.",
      href: "/comparatif",
    },
    {
      title: "Comparatif Secteur",
      desc: "Deux couples secteur/univers en parallèle, allocation Markowitz.",
      href: "/comparatif/secteur",
    },
    {
      title: "Veille IA",
      desc: "Articles d'analyse automatiques, téléchargement PDF.",
      href: "/veille",
    },
    {
      title: "Portrait d'entreprise",
      desc: "Sociétés non cotées européennes (à venir).",
      href: "/cas-usage/portrait",
      soon: true,
    },
  ];
  return (
    <div className="grid grid-cols-12 gap-8">
      <div className="col-span-3">
        <div className="label-vitrine mb-4">Produits</div>
        <p className="text-sm text-text-muted leading-relaxed">
          Tous les livrables FinSight, alimentés par un pipeline d&apos;agents
          spécialisés.
        </p>
      </div>
      <div className="col-span-9 grid grid-cols-2 gap-x-8 gap-y-4">
        {items.map((it) => (
          <Link
            key={it.title}
            href={it.href}
            className="group flex flex-col gap-1 py-1"
          >
            <span className="text-sm font-medium text-text-primary group-hover:text-accent-primary transition-colors flex items-center gap-2">
              {it.title}
              {it.soon && (
                <span className="text-2xs uppercase tracking-wider text-text-muted border border-border-default rounded px-1.5 py-0.5">
                  Bientôt
                </span>
              )}
            </span>
            <span className="text-xs text-text-muted leading-relaxed">
              {it.desc}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function CollabContent() {
  return (
    <div className="grid grid-cols-12 gap-8">
      <div className="col-span-4">
        <div className="label-vitrine mb-4">Collaboration</div>
        <p className="text-sm text-text-muted leading-relaxed">
          FinSight s&apos;ouvre à des partenariats stratégiques avec
          institutions, cabinets et écoles.
        </p>
        <Link
          href="/collaboration"
          className="mt-4 inline-flex items-center gap-1 text-sm text-accent-primary hover:underline"
        >
          En savoir plus <ArrowUpRight className="w-3.5 h-3.5" />
        </Link>
      </div>
      <div className="col-span-8 grid grid-cols-2 gap-x-8 gap-y-3">
        {[
          ["Banques & gestion d'actifs", "Intégration buy-side"],
          ["Cabinets comptables", "FEC, défaillance, financement"],
          ["Conseillers en gestion (CGP)", "White-label & reporting client"],
          ["Hedge funds & recherche", "API & signaux alternatifs"],
          ["Écoles & universités", "Programmes pédagogiques"],
          ["Médias financiers", "Données enrichies"],
        ].map(([title, desc]) => (
          <div key={title}>
            <div className="text-sm font-medium text-text-primary">{title}</div>
            <div className="text-xs text-text-muted">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
