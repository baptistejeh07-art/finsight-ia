/**
 * Catalogue de graphiques disponibles pour l'edit mode.
 *
 * Chaque ChartDef décrit un graphique qu'on peut insérer dynamiquement dans un
 * dashboard (EditableGrid). Utilisé par le modal picker en edit mode.
 *
 * Important : on ne référence PAS directement les composants ici car ils sont
 * "use client" et le catalogue doit rester neutre (importable server/client).
 * À la place on stocke un identifiant composantId que le renderer résout via
 * une map dans chart-catalog.client.tsx.
 */

export type ChartKind = "societe" | "secteur" | "indice" | "comparatif" | "pme";

export type ChartCategory = "performance" | "valuation" | "risk" | "composition" | "quality";

export interface ChartDef {
  id: string;
  category: ChartCategory;
  label: string;
  description: string;
  /** Identifiant résolu côté client vers un vrai composant React. */
  componentId: string;
  /** Clé de data requise dans result.data (dot-path : "raw_data.stock_history"). */
  requiredDataKey?: string;
  /** Kinds d'analyse compatibles. */
  availableFor: ChartKind[];
  /** Taille par défaut dans la grid 12 cols. */
  defaultSize?: { w: number; h: number };
}

export const CATEGORY_LABELS: Record<ChartCategory, string> = {
  performance: "Performance",
  valuation: "Valorisation",
  risk: "Risque",
  composition: "Composition",
  quality: "Qualité",
};

/**
 * Catalogue principal. On commence avec une sélection ciblée (3-4 par catégorie)
 * pour le MVP — extensible par la suite.
 */
export const CHART_CATALOG: ChartDef[] = [
  // ─── PERFORMANCE ─────────────────────────────────────────────────
  {
    id: "perf-cours-12m",
    category: "performance",
    label: "Cours 12 mois",
    description: "Courbe de prix 1 an avec benchmark S&P 500 et ETF sectoriel.",
    componentId: "CoursChart12m",
    requiredDataKey: "raw_data.stock_history",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 6 },
  },
  {
    id: "perf-multi-periodes",
    category: "performance",
    label: "Performance multi-périodes",
    description: "Graphique interactif avec sélecteur 1J/5J/1M/3M/6M/YTD/1A/3A/5A.",
    componentId: "PerformanceCardSociete",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 7 },
  },
  {
    id: "perf-indice-tiles",
    category: "performance",
    label: "Tuiles de performance",
    description: "YTD, 1A, 3A, 5A, volatilité, Sharpe, Max Drawdown.",
    componentId: "IndicePerfTiles",
    availableFor: ["indice", "secteur"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "perf-cmp-indice",
    category: "performance",
    label: "Comparaison base 100",
    description: "Courbe comparative 2 indices base 100 sur 1 an.",
    componentId: "CmpIndicePerfChart",
    requiredDataKey: "perf_history",
    availableFor: ["comparatif"],
    defaultSize: { w: 8, h: 6 },
  },

  // ─── VALORISATION ────────────────────────────────────────────────
  {
    id: "valo-cards",
    category: "valuation",
    label: "Valorisation triangulaire",
    description: "Targets Bull / Base / Bear avec cours actuel.",
    componentId: "ValorisationCards",
    availableFor: ["societe"],
    defaultSize: { w: 4, h: 4 },
  },
  {
    id: "valo-indice-tiles",
    category: "valuation",
    label: "Valorisation agrégée",
    description: "P/E médian, P/B, rendement dividende, prime de risque.",
    componentId: "IndiceValuationTiles",
    availableFor: ["indice", "secteur"],
    defaultSize: { w: 4, h: 5 },
  },
  {
    id: "valo-bench-sp500",
    category: "valuation",
    label: "Valorisation vs S&P 500",
    description: "P/E, P/B, DY de l'indice comparés au S&P 500.",
    componentId: "IndiceValuationBench",
    availableFor: ["indice", "secteur"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "valo-cmp-stats",
    category: "valuation",
    label: "Statistiques A vs B",
    description: "Tableau comparatif performance / risque / valorisation.",
    componentId: "CmpIndiceStatTiles",
    availableFor: ["comparatif"],
    defaultSize: { w: 6, h: 8 },
  },

  // ─── RISQUE ──────────────────────────────────────────────────────
  {
    id: "risk-volatility",
    category: "risk",
    label: "Volatilité glissante",
    description: "Volatilité annualisée sur fenêtre 6 mois (rendements mensuels, √12).",
    componentId: "VolatilityChart",
    requiredDataKey: "raw_data.stock_history",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "risk-drawdown",
    category: "risk",
    label: "Drawdown historique",
    description: "Chute vs plus-haut glissant — max drawdown visible sur l'aire.",
    componentId: "DrawdownChart",
    requiredDataKey: "raw_data.stock_history",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },

  // ─── COMPOSITION ─────────────────────────────────────────────────
  {
    id: "comp-indice-donut",
    category: "composition",
    label: "Donut sectoriel",
    description: "Pondération sectorielle en anneau interactif.",
    componentId: "IndiceSectorsDonut",
    requiredDataKey: "secteurs",
    availableFor: ["indice"],
    defaultSize: { w: 6, h: 7 },
  },
  {
    id: "comp-indice-map",
    category: "composition",
    label: "Cartographie sectorielle",
    description: "Table : secteur, poids, performance, top sociétés.",
    componentId: "IndiceSecteursTable",
    requiredDataKey: "secteurs",
    availableFor: ["indice"],
    defaultSize: { w: 12, h: 7 },
  },
  {
    id: "comp-top10",
    category: "composition",
    label: "Top 10 constituants",
    description: "Tableau des 10 premières sociétés d'un indice par pondération.",
    componentId: "IndiceTopConstituents",
    requiredDataKey: "tickers",
    availableFor: ["indice", "secteur"],
    defaultSize: { w: 6, h: 7 },
  },
  {
    id: "comp-cmp-sector",
    category: "composition",
    label: "Composition A vs B",
    description: "Pondération sectorielle comparée de 2 indices.",
    componentId: "CmpIndiceSectorTable",
    requiredDataKey: "sector_comparison",
    availableFor: ["comparatif"],
    defaultSize: { w: 8, h: 7 },
  },
  {
    id: "comp-cmp-top5",
    category: "composition",
    label: "Top 5 A et B",
    description: "Top 5 constituants côte à côte.",
    componentId: "CmpIndiceTop5",
    availableFor: ["comparatif"],
    defaultSize: { w: 8, h: 6 },
  },

  // ─── QUALITÉ ─────────────────────────────────────────────────────
  {
    id: "quality-capex-fcf",
    category: "quality",
    label: "CapEx vs Dividendes",
    description: "Barres d'allocation de capital 4 dernières années.",
    componentId: "CapexFcfChart",
    requiredDataKey: "raw_data.years",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "quality-roe-roic",
    category: "quality",
    label: "Historique ROE / ROIC",
    description: "ROE (barres) vs ROIC (ligne) par exercice — gap = effet de levier financier.",
    componentId: "RoeRoicHistoryChart",
    requiredDataKey: "ratios.years",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "quality-income-statement",
    category: "quality",
    label: "Compte de résultat simplifié",
    description: "Waterfall CA → Marge brute → EBITDA → Résultat net avec taux de conversion.",
    componentId: "IncomeStatementWaterfall",
    requiredDataKey: "raw_data.years",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 6 },
  },
  {
    id: "quality-revenue-margins",
    category: "quality",
    label: "Évolution CA et marges",
    description: "CA en barres + marges EBITDA et nette en lignes (5 exercices).",
    componentId: "RevenueMarginTrend",
    requiredDataKey: "raw_data.years",
    availableFor: ["societe"],
    defaultSize: { w: 8, h: 5 },
  },
  {
    id: "valo-multiples-history",
    category: "valuation",
    label: "Multiples historiques",
    description: "P/E, EV/EBITDA et EV/Revenue par exercice — détecte l'expansion ou contraction.",
    componentId: "ValuationMultiplesHistory",
    requiredDataKey: "ratios.years",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "risk-balance-health",
    category: "risk",
    label: "Santé du bilan",
    description: "ND/EBITDA, Altman Z et Current Ratio sur plusieurs exercices (proxy bilan).",
    componentId: "BalanceHealthTrend",
    requiredDataKey: "ratios.years",
    availableFor: ["societe"],
    defaultSize: { w: 6, h: 5 },
  },

  // ─── SECTEUR / INDICE ────────────────────────────────────────────
  {
    id: "perf-indice-benchmark",
    category: "performance",
    label: "Indice vs S&P 500 / Bonds / Or",
    description: "Comparaison base 100 de l'indice contre 3 classes d'actifs référence (~12 mois).",
    componentId: "IndicePerfBenchmark",
    requiredDataKey: "perf_history",
    availableFor: ["indice"],
    defaultSize: { w: 8, h: 6 },
  },
  {
    id: "quality-score-distribution",
    category: "quality",
    label: "Distribution des scores FinSight",
    description: "Histogramme des scores par bucket de recommandation (SELL / HOLD / BUY).",
    componentId: "SectorScoreDistribution",
    requiredDataKey: "tickers",
    availableFor: ["secteur", "indice"],
    defaultSize: { w: 6, h: 5 },
  },
  {
    id: "valo-value-quality-scatter",
    category: "valuation",
    label: "Valeur × Qualité (scatter)",
    description: "EV/EBITDA vs marge EBITDA, taille bulle = capitalisation. Pépites en haut-gauche.",
    componentId: "SectorValueQualityScatter",
    requiredDataKey: "tickers",
    availableFor: ["secteur", "indice"],
    defaultSize: { w: 6, h: 6 },
  },
  {
    id: "perf-momentum-leaders",
    category: "performance",
    label: "Leaders et retardataires",
    description: "Top 5 / bottom 5 sur momentum 52 semaines.",
    componentId: "SectorMomentumLeaders",
    requiredDataKey: "tickers",
    availableFor: ["secteur", "indice"],
    defaultSize: { w: 6, h: 6 },
  },
  {
    id: "perf-indice-sector-perf",
    category: "performance",
    label: "Performance par secteur",
    description: "Bar chart horizontal des perfs sectorielles, tri décroissant, spread visible.",
    componentId: "IndiceSectorPerformance",
    requiredDataKey: "secteurs",
    availableFor: ["indice"],
    defaultSize: { w: 8, h: 6 },
  },

  // ─── COMPARATIF ──────────────────────────────────────────────────
  {
    id: "cmp-multiples-radar",
    category: "quality",
    label: "Radar 6 dimensions",
    description: "Radar comparant marges, ROE, croissance et multiples A vs B (normalisé 0-100).",
    componentId: "CmpMultiplesRadar",
    availableFor: ["comparatif"],
    defaultSize: { w: 6, h: 7 },
  },
  {
    id: "cmp-return-profile",
    category: "performance",
    label: "Profil de rendement A vs B",
    description: "Barres côte à côte YTD / 1A / 3A / 5A pour les deux entités.",
    componentId: "CmpReturnProfile",
    availableFor: ["comparatif"],
    defaultSize: { w: 8, h: 5 },
  },
  {
    id: "cmp-risk-profile",
    category: "risk",
    label: "Profil de risque A vs B",
    description: "Volatilité, Sharpe et Max Drawdown comparés côte à côte.",
    componentId: "CmpRiskProfile",
    availableFor: ["comparatif"],
    defaultSize: { w: 8, h: 5 },
  },
];

/**
 * Utilitaire : lit une clé en dot-notation dans un objet. Retourne undefined si
 * un segment est null/undefined. Gère les arrays : truthy si length > 0.
 */
export function hasDataAtKey(
  data: Record<string, unknown> | undefined | null,
  key: string | undefined
): boolean {
  if (!key) return true;
  if (!data) return false;
  const parts = key.split(".");
  let cur: unknown = data;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return false;
    cur = (cur as Record<string, unknown>)[p];
  }
  if (cur == null) return false;
  if (Array.isArray(cur)) return cur.length > 0;
  if (typeof cur === "object") return Object.keys(cur as object).length > 0;
  return true;
}

/**
 * Filtre le catalogue selon le kind d'analyse et la data disponible.
 */
export function filterCatalog(
  kind: ChartKind,
  data: Record<string, unknown> | undefined | null
): ChartDef[] {
  return CHART_CATALOG.filter((c) => {
    if (!c.availableFor.includes(kind)) return false;
    if (c.requiredDataKey && !hasDataAtKey(data, c.requiredDataKey)) return false;
    return true;
  });
}
