import { fmtCurrency } from "@/lib/utils";

interface Props {
  bull?: number;
  base?: number;
  bear?: number;
  sharePrice?: number;
  currency: string;
}

export function ValorisationCards({ bull, base, bear, sharePrice, currency }: Props) {
  const cards = [
    { label: "Bull case", value: bull, color: "text-signal-buy", border: "border-signal-buy/30" },
    { label: "Base case", value: base, color: "text-ink-900", border: "border-ink-200" },
    { label: "Bear case", value: bear, color: "text-signal-sell", border: "border-signal-sell/30" },
  ];

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        Valorisation — distribution triangulaire
      </div>
      <div className="grid grid-cols-3 gap-3">
        {cards.map((c) => {
          const upside =
            c.value && sharePrice ? ((c.value - sharePrice) / sharePrice) * 100 : null;
          const upStr =
            upside == null
              ? "—"
              : `${upside >= 0 ? "▲" : "▼"} ${Math.abs(upside).toFixed(1).replace(".", ",")} %`;
          const upColor =
            upside == null
              ? "text-ink-400"
              : upside >= 0
              ? "text-signal-buy"
              : "text-signal-sell";

          return (
            <div key={c.label} className={`border ${c.border} rounded-md p-3 text-center`}>
              <div className="text-[10px] font-semibold uppercase tracking-[1.2px] text-ink-500 mb-1">
                {c.label}
              </div>
              <div className={`text-lg font-bold font-mono ${c.color}`}>
                {c.value ? fmtCurrency(c.value, currency, 0) : "—"}
              </div>
              <div className={`text-xs font-mono mt-1 ${upColor}`}>{upStr}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
