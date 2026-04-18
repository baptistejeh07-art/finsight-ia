export interface Annonce {
  slug: string;
  title: string;
  summary: string;
  body: string;
  date?: string; // ISO ou null si feature à venir
  dateLabel: string; // affichage (ex: "16 avril 2026" ou "Q2 2026")
  category: string;
  kind: "release" | "upcoming";
}

export const ANNONCES: Annonce[] = [
  // === Dernières sorties ===
  {
    slug: "dashboard-2-colonnes",
    title: "Dashboard 2 colonnes pour l'analyse société",
    summary:
      "Mise en page repensée : graphique multi-séries et valorisation à gauche, synthèse étoffée et Q&A à droite.",
    body:
      "L'écran de résultats société a été refondu pour faire tenir l'essentiel sans scroll. Cours de bourse multi-séries (target + S&P 500 + ETF secteur), KPI grid 6 colonnes, comparable peers et synthèse multi-blocs côte à côte. La conversation Q&A reste accessible en permanence.",
    date: "2026-04-16",
    dateLabel: "16 avril 2026",
    category: "Interface",
    kind: "release",
  },
  {
    slug: "logos-societe-logo-dev",
    title: "Logos société via Logo.dev",
    summary:
      "Chaque ticker affiche désormais le logo officiel de la société (top 50 mappés, fallback heuristique pour le reste).",
    body:
      "Migration de Clearbit Logo (déprécié) vers Logo.dev. Le top 50 des sociétés couvertes est mappé manuellement vers leur domaine officiel ; pour les autres, un fallback heuristique strip Inc./Corp. avant de tomber sur un carré navy avec les initiales.",
    date: "2026-04-11",
    dateLabel: "11 avril 2026",
    category: "Branding",
    kind: "release",
  },
  {
    slug: "pptx-indice-20-slides",
    title: "Pitchbook indice — 20 slides éditoriales",
    summary:
      "ERP, P/B, Dividend Yield, allocation optimale : 20 slides packagées prêtes pour comité d'investissement.",
    body:
      "Le pitchbook indice s'aligne désormais sur le format société : 20 slides exactement, avec une couverture ERP, des slides agrégées P/B + Dividend Yield, et une slide d'allocation optimale calculée par optimisation de portefeuille.",
    date: "2026-04-05",
    dateLabel: "5 avril 2026",
    category: "Livrables",
    kind: "release",
  },

  // === Features à venir ===
  {
    slug: "portrait-entreprise-pappers",
    title: "Portrait d'entreprise pour les sociétés non cotées",
    summary:
      "Branchement à Pappers V2 pour analyser les 3.5M+ d'entreprises françaises non cotées : PME, ETI, deals M&A.",
    body:
      "L'intégration Pappers V2 ouvre FinSight aux sociétés non cotées européennes. Pour les analystes M&A, advisors PME et CGP, c'est l'accès à un univers d'investissement qui était jusqu'ici hors radar des outils grand public.",
    dateLabel: "Q2 2026",
    category: "Données",
    kind: "upcoming",
  },
  {
    slug: "comptes-utilisateurs",
    title: "Comptes utilisateurs et historique persistant",
    summary:
      "Sauvegardez vos analyses, suivez vos sociétés favorites, retrouvez vos pitchbooks d'une session à l'autre.",
    body:
      "L'authentification Supabase passera en mode complet : historique d'analyses, watchlists par utilisateur, partage de pitchbooks et synchronisation cross-device.",
    dateLabel: "Courant 2026",
    category: "Plateforme",
    kind: "upcoming",
  },
  {
    slug: "score-finsight",
    title: "Score FinSight propriétaire",
    summary:
      "Une note d'investissement composite — qualité, valorisation, momentum, gouvernance — calculée par notre pipeline.",
    body:
      "À partir des centaines de signaux extraits par les agents (ratios, sentiment, devil's advocate, qualité comptable), nous publierons un score propriétaire FinSight comparable d'une société à l'autre, qui deviendra à terme un signal de référence.",
    dateLabel: "Fin 2026",
    category: "Recherche",
    kind: "upcoming",
  },
];

export const RELEASES = ANNONCES.filter((a) => a.kind === "release");
export const UPCOMING = ANNONCES.filter((a) => a.kind === "upcoming");

export function getAnnonceBySlug(slug: string): Annonce | undefined {
  return ANNONCES.find((a) => a.slug === slug);
}
