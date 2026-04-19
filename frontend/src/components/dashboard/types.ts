export interface CompanyInfo {
  company_name: string;
  ticker: string;
  sector: string;
  industry?: string;
  base_year?: number;
  currency: string;
  units?: string;
  analysis_date?: string;
}

export interface YearData {
  year: string;
  revenue?: number | null;
  capex?: number | null;
  dividends?: number | null;
  fcf?: number | null;
  ebitda?: number | null;
  net_income?: number | null;
  [k: string]: unknown;
}

export interface YearRatios {
  year: string;
  pe_ratio?: number | null;
  ev_ebitda?: number | null;
  ev_revenue?: number | null;
  ebitda_margin?: number | null;
  net_margin?: number | null;
  gross_margin?: number | null;
  roe?: number | null;
  roic?: number | null;
  net_debt_ebitda?: number | null;
  fcf_yield?: number | null;
  current_ratio?: number | null;
  revenue_growth?: number | null;
  altman_z?: number | null;
  market_cap?: number | null;
  ev?: number | null;
  fcf?: number | null;
  dividends_paid_abs?: number | null;
  [k: string]: unknown;
}

export interface StockPoint {
  month: string;
  price: number;
}

export interface MarketData {
  share_price?: number;
  shares_diluted?: number;
  beta_levered?: number;
  wacc?: number;
  dividend_yield?: number;
  [k: string]: unknown;
}

export interface RawData {
  ticker: string;
  company_info: CompanyInfo;
  years: Record<string, YearData>;
  market: MarketData;
  stock_history: StockPoint[];
  [k: string]: unknown;
}

export interface RatiosData {
  ticker: string;
  years: Record<string, YearRatios>;
  latest_year: string;
  [k: string]: unknown;
}

export interface PeerData {
  name: string;
  ticker: string;
  market_cap_mds?: number | null;
  ev_ebitda?: number | null;
  ev_revenue?: number | null;
  pe?: number | null;
  gross_margin?: number | null;
  ebitda_margin?: number | null;
}

export interface FootballFieldEntry {
  label: string;
  range_low: number;
  range_high: number;
  midpoint: number;
}

export interface Catalyst {
  title: string;
  description: string;
}

export interface Synthesis {
  ticker: string;
  company_name?: string;
  recommendation: string;
  conviction: number;
  target_base?: number;
  target_bull?: number;
  target_bear?: number;
  summary?: string;
  thesis?: string;
  company_description?: string;
  bull_hypothesis?: string;
  base_hypothesis?: string;
  bear_hypothesis?: string;
  comparable_peers?: PeerData[];
  football_field?: FootballFieldEntry[];
  catalysts?: Catalyst[];
  strengths?: string[] | string;
  risks?: string[] | string;
  valuation_comment?: string;
  financial_commentary?: string;
  ratio_commentary?: string;
  dcf_commentary?: string;
  peers_commentary?: string;
  invalidation_list?: string[] | string;
  invalidation_conditions?: string[];
  buy_trigger?: string;
  sell_trigger?: string;
  conclusion?: string;
  [k: string]: unknown;
}

export interface SectorTicker {
  ticker?: string;
  name?: string;
  market_cap?: number;
  ratios?: Record<string, number | null>;
}

export interface IndiceSector {
  name?: string;
  weight?: number;
  performance?: number;
  top_tickers?: string[];
}

export interface AnalysisData {
  ticker?: string;
  raw_data?: RawData;
  ratios?: RatiosData;
  synthesis?: Synthesis;
  recommendation?: string;
  // Secteur/indice payload (kind = "secteur" | "indice")
  kind?: string;
  sector?: string;
  universe?: string;
  tickers?: SectorTicker[];
  sector_analytics?: Record<string, unknown>;
  secteurs?: IndiceSector[];
  indice_stats?: Record<string, unknown>;
  macro?: Record<string, unknown>;
  allocation?: Record<string, unknown>;
  top_performers?: string[];
  // backward-compat with old shape
  snapshot?: { company_info?: CompanyInfo; market?: MarketData };
  [k: string]: unknown;
}
