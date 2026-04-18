/**
 * Mapping anglais -> français des secteurs/industries yfinance.
 * Standard FinSight pour affichage utilisateur.
 */

const SECTOR_FR: Record<string, string> = {
  // Sectors
  "Technology": "Technologie",
  "Communication Services": "Services de communication",
  "Financial Services": "Services financiers",
  "Financial": "Finance",
  "Healthcare": "Santé",
  "Consumer Cyclical": "Consommation cyclique",
  "Consumer Defensive": "Consommation défensive",
  "Consumer Discretionary": "Consommation discrétionnaire",
  "Consumer Staples": "Biens de consommation courante",
  "Energy": "Énergie",
  "Industrials": "Industrie",
  "Basic Materials": "Matériaux de base",
  "Materials": "Matériaux",
  "Real Estate": "Immobilier",
  "Utilities": "Services aux collectivités",

  // Quelques industries fréquentes
  "Consumer Electronics": "Électronique grand public",
  "Software—Application": "Logiciels — applications",
  "Software—Infrastructure": "Logiciels — infrastructure",
  "Internet Content & Information": "Contenu et information internet",
  "Internet Retail": "Commerce internet",
  "Auto Manufacturers": "Constructeurs automobiles",
  "Semiconductors": "Semi-conducteurs",
  "Semiconductor Equipment & Materials": "Équipements et matériaux semi-conducteurs",
  "Banks—Diversified": "Banques diversifiées",
  "Banks—Regional": "Banques régionales",
  "Insurance—Diversified": "Assurance diversifiée",
  "Asset Management": "Gestion d'actifs",
  "Drug Manufacturers—General": "Laboratoires pharmaceutiques",
  "Drug Manufacturers—Specialty & Generic": "Pharma spécialisée et générique",
  "Biotechnology": "Biotechnologie",
  "Medical Devices": "Dispositifs médicaux",
  "Health Information Services": "Services d'information santé",
  "Oil & Gas Integrated": "Pétrole & gaz intégré",
  "Oil & Gas E&P": "Pétrole & gaz E&P",
  "Aerospace & Defense": "Aérospatiale & défense",
  "Specialty Retail": "Commerce spécialisé",
  "Restaurants": "Restauration",
  "Beverages—Non-Alcoholic": "Boissons non alcoolisées",
  "Beverages—Wineries & Distilleries": "Vins & spiritueux",
  "Household & Personal Products": "Produits domestiques et soins personnels",
  "Luxury Goods": "Produits de luxe",
  "Apparel Manufacturing": "Fabrication d'habillement",
  "Footwear & Accessories": "Chaussures & accessoires",
  "Tobacco": "Tabac",
  "Packaged Foods": "Alimentaire conditionné",
  "Conglomerates": "Conglomérats",
  "Building Materials": "Matériaux de construction",
  "Engineering & Construction": "Ingénierie & construction",
  "Diagnostics & Research": "Diagnostics & recherche",
};

/**
 * Retourne le secteur/industrie en français si traduction connue,
 * sinon renvoie la valeur d'origine.
 */
export function trSector(s: string | undefined | null): string {
  if (!s) return "";
  return SECTOR_FR[s] || s;
}
