"use client";

/**
 * Résolution componentId (chart-catalog.ts) → composant React concret.
 * Tous les composants exposés ici acceptent le shape {data, ticker, kind}.
 *
 * Chaque fonction renvoie un ReactNode avec un garde "pas de data" intégré,
 * pour que l'insertion depuis le picker ne crashe jamais.
 */

import type { ReactNode } from "react";
import type { AnalysisData, RawData, Synthesis, RatiosData } from "./types";
import { CoursChart } from "./cours-chart";
import { CapexFcfChart } from "./capex-fcf-chart";
import { ValorisationCards } from "./valorisation-cards";
import { PerformanceCard } from "./performance-card";
import { IndiceSectorsDonut } from "./indice-sectors-donut";
import { IndiceSecteursTable } from "./indice-secteurs-table";
import { IndicePerfTiles } from "./indice-perf-tiles";
import { IndiceValuationTiles } from "./indice-valuation-tiles";
import { IndiceValuationBench } from "./indice-valuation-bench";
import { IndiceTopConstituents } from "./indice-top-constituents";
import { CmpIndicePerfChart } from "./cmp-indice-perf-chart";
import { CmpIndiceSectorTable } from "./cmp-indice-sector-table";
import { CmpIndiceStatTiles } from "./cmp-indice-stat-tiles";
import { CmpIndiceTop5 } from "./cmp-indice-top5";

export interface RendererCtx {
  data: AnalysisData | undefined;
  ticker?: string;
  label?: string;
  kind?: string;
}

function Placeholder({ reason }: { reason: string }) {
  return (
    <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
      <span className="text-xs text-ink-400 italic">{reason}</span>
    </div>
  );
}

export function renderChart(componentId: string, ctx: RendererCtx): ReactNode {
  const data = ctx.data || {};
  const raw = (data.raw_data as RawData | undefined) || undefined;
  const ratios = (data.ratios as RatiosData | undefined) || undefined;
  const synthesis = (data.synthesis as Synthesis | undefined) || undefined;
  const ci = raw?.company_info || data.snapshot?.company_info;
  const market = raw?.market || data.snapshot?.market;
  const tickerStr = data.ticker || ci?.ticker || ctx.ticker || "";
  const currency = ci?.currency || "EUR";
  const latestYear =
    ratios?.latest_year || (ratios?.years ? Object.keys(ratios.years).sort().pop() : undefined);
  const latestRatios = latestYear && ratios?.years ? ratios.years[latestYear] : null;

  switch (componentId) {
    case "CoursChart12m":
      if (!raw?.stock_history) return <Placeholder reason="Historique de cours indisponible" />;
      return (
        <CoursChart ticker={tickerStr} history={raw.stock_history} sector={ci?.sector} />
      );

    case "PerformanceCardSociete":
      if (!tickerStr) return <Placeholder reason="Ticker manquant" />;
      return (
        <PerformanceCard ticker={tickerStr} currency={currency} sector={ci?.sector || ""} />
      );

    case "ValorisationCards":
      return (
        <ValorisationCards
          bull={synthesis?.target_bull}
          base={synthesis?.target_base}
          bear={synthesis?.target_bear}
          sharePrice={market?.share_price as number | undefined}
          currency={currency}
        />
      );

    case "CapexFcfChart":
      if (!raw?.years) return <Placeholder reason="Historique annuel indisponible" />;
      return (
        <CapexFcfChart years={raw.years} ratios={ratios?.years} currency={currency} />
      );

    case "IndicePerfTiles":
      return (
        <IndicePerfTiles
          stats={(data.indice_stats as Record<string, unknown>) || data as unknown as Record<string, unknown>}
          label={(data.universe as string) || (data.sector as string)}
        />
      );

    case "IndiceValuationTiles":
      return (
        <IndiceValuationTiles
          stats={(data.indice_stats as Record<string, unknown>) || data as unknown as Record<string, unknown>}
          label={(data.universe as string) || (data.sector as string)}
        />
      );

    case "IndiceValuationBench":
      return (
        <IndiceValuationBench
          stats={(data.indice_stats as Record<string, unknown>) || data as unknown as Record<string, unknown>}
          universe={data.universe as string}
        />
      );

    case "IndiceTopConstituents":
      if (!data.tickers) return <Placeholder reason="Liste des constituants indisponible" />;
      return (
        <IndiceTopConstituents
          tickers={data.tickers}
          label={(data.universe as string) || (data.sector as string)}
        />
      );

    case "IndiceSectorsDonut":
      if (!data.secteurs) return <Placeholder reason="Pondération sectorielle indisponible" />;
      return <IndiceSectorsDonut secteurs={data.secteurs} universe={data.universe as string} />;

    case "IndiceSecteursTable":
      if (!data.secteurs) return <Placeholder reason="Pondération sectorielle indisponible" />;
      return <IndiceSecteursTable secteurs={data.secteurs} universe={data.universe as string} />;

    case "CmpIndicePerfChart": {
      const ph = (data.perf_history as { dates: string[]; indice_a: number[]; indice_b: number[] } | null);
      const nameA = (data.name_a as string) || "Indice A";
      const nameB = (data.name_b as string) || "Indice B";
      return <CmpIndicePerfChart perfHistory={ph} nameA={nameA} nameB={nameB} />;
    }

    case "CmpIndiceSectorTable": {
      const rows = data.sector_comparison as Array<[string, number | null, number | null]> | undefined;
      const nameA = (data.name_a as string) || "A";
      const nameB = (data.name_b as string) || "B";
      return <CmpIndiceSectorTable sectorComparison={rows} nameA={nameA} nameB={nameB} />;
    }

    case "CmpIndiceStatTiles": {
      const nameA = (data.name_a as string) || "A";
      const nameB = (data.name_b as string) || "B";
      return <CmpIndiceStatTiles data={data as Record<string, unknown>} nameA={nameA} nameB={nameB} />;
    }

    case "CmpIndiceTop5": {
      const top5A = data.top5_a as Array<[string, string, number | null, string]> | undefined;
      const top5B = data.top5_b as Array<[string, string, number | null, string]> | undefined;
      const nameA = (data.name_a as string) || "A";
      const nameB = (data.name_b as string) || "B";
      return <CmpIndiceTop5 top5A={top5A} top5B={top5B} nameA={nameA} nameB={nameB} />;
    }

    case "StubRisk":
      return (
        <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex flex-col items-center justify-center gap-2">
          <div className="text-xs text-ink-400 italic">Chart risque — bientôt disponible</div>
          <div className="text-[10px] text-ink-400">Placeholder</div>
        </div>
      );

    case "StubQuality":
      return (
        <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex flex-col items-center justify-center gap-2">
          <div className="text-xs text-ink-400 italic">Chart qualité — bientôt disponible</div>
          <div className="text-[10px] text-ink-400">Placeholder</div>
        </div>
      );

    default:
      // Éviter les warnings sur variables non utilisées
      void latestRatios;
      return <Placeholder reason={`Composant inconnu : ${componentId}`} />;
  }
}
