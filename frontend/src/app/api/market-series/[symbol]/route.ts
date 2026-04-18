import { NextResponse } from "next/server";

interface YahooQuote {
  meta?: { symbol?: string };
  timestamp?: number[];
  indicators?: {
    quote?: Array<{ close?: (number | null)[] }>;
  };
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ symbol: string }> }
) {
  const { symbol } = await params;
  const range = new URL(request.url).searchParams.get("range") || "1y";
  const interval = new URL(request.url).searchParams.get("interval") || "1mo";

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`;
    const r = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 FinSight" },
      next: { revalidate: 3600 }, // cache 1h
    });
    if (!r.ok) {
      return NextResponse.json({ error: `Yahoo ${r.status}` }, { status: r.status });
    }
    const data = await r.json();
    const result: YahooQuote | undefined = data?.chart?.result?.[0];
    if (!result) {
      return NextResponse.json({ error: "No data" }, { status: 404 });
    }

    const timestamps = result.timestamp || [];
    const closes = result.indicators?.quote?.[0]?.close || [];

    const points = timestamps
      .map((ts, i) => {
        const px = closes[i];
        if (px == null) return null;
        const d = new Date(ts * 1000);
        const month = d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
        return { month, price: px };
      })
      .filter((p): p is { month: string; price: number } => p !== null);

    return NextResponse.json({ symbol, points });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
