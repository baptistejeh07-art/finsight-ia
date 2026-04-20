"use client";

import { useEffect, useState } from "react";
import {
  X, Bell, TrendingUp, Calendar, DollarSign, Newspaper, FileText, Target,
} from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import { createAlert, type TriggerType, type Channel } from "@/hooks/use-alerts";
import { ensurePushSubscription } from "@/lib/push";

interface Props {
  open: boolean;
  onClose: () => void;
  historyId?: string | null;
  ticker?: string;
  defaultTargetPrice?: number;
}

const TRIGGERS: { value: TriggerType; label: string; icon: React.ComponentType<{ className?: string }>; help: string }[] = [
  { value: "price_target", label: "Cours cible atteint", icon: Target, help: "Je suis notifié quand le cours touche ma cible." },
  { value: "earnings_date", label: "Earnings call", icon: Calendar, help: "24h avant la prochaine publication de résultats." },
  { value: "dividend_exdate", label: "Ex-dividende", icon: DollarSign, help: "48h avant la date de détachement du dividende." },
  { value: "quarterly_results", label: "Résultats trimestriels", icon: FileText, help: "Quand de nouveaux résultats Q sont publiés." },
  { value: "news", label: "News importante", icon: Newspaper, help: "Quand une news sort sur le ticker (toutes les 6h)." },
  { value: "custom_date", label: "Date personnalisée", icon: Calendar, help: "Rappel à une date libre que je choisis." },
];

export function AlertModal({ open, onClose, historyId, ticker, defaultTargetPrice }: Props) {
  const [trigger, setTrigger] = useState<TriggerType>("price_target");
  const [price, setPrice] = useState<string>(defaultTargetPrice ? String(defaultTargetPrice) : "");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [customDate, setCustomDate] = useState<string>("");
  const [channels, setChannels] = useState<Channel[]>(["email", "push"]);
  const [label, setLabel] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) {
      setTrigger("price_target");
      setPrice(defaultTargetPrice ? String(defaultTargetPrice) : "");
      setDirection("above");
      setCustomDate("");
      setChannels(["email", "push"]);
      setLabel("");
    }
  }, [open, defaultTargetPrice]);

  async function togglePushChannel(v: boolean) {
    if (!v) {
      setChannels((c) => c.filter((x) => x !== "push"));
      return;
    }
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) { toast.error("Connectez-vous"); return; }
    const res = await ensurePushSubscription(token);
    if (!res.ok) { toast.error(res.reason || "Push indisponible"); return; }
    setChannels((c) => Array.from(new Set([...c, "push" as Channel])));
    toast.success("Notifications activées");
  }

  async function save() {
    if (!channels.length) { toast.error("Choisissez au moins un canal"); return; }

    const trigger_value: Record<string, unknown> = {};
    if (trigger === "price_target") {
      const p = parseFloat(price);
      if (!p || p <= 0) { toast.error("Prix cible invalide"); return; }
      trigger_value.target = p;
      trigger_value.direction = direction;
    } else if (trigger === "custom_date") {
      if (!customDate) { toast.error("Date requise"); return; }
      trigger_value.date = customDate;
    }

    const computedLabel = label.trim() || buildLabel(trigger, ticker, trigger_value);

    setSaving(true);
    try {
      const alert = await createAlert({
        history_id: historyId || undefined,
        ticker: ticker || undefined,
        trigger_type: trigger,
        trigger_value,
        channels,
        label: computedLabel,
      });
      if (!alert) { toast.error("Échec création"); return; }
      toast.success("Rappel créé");
      window.dispatchEvent(new CustomEvent("finsight:alerts-changed"));
      onClose();
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  const selected = TRIGGERS.find((t) => t.value === trigger)!;
  const SelectedIcon = selected.icon;

  const needsTicker = trigger !== "custom_date";
  if (needsTicker && !ticker) {
    return (
      <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
        <div className="bg-white rounded-lg p-6 max-w-sm" onClick={(e) => e.stopPropagation()}>
          <div className="text-sm text-ink-700">Ce type de rappel nécessite un ticker (analyse société uniquement).</div>
          <button onClick={onClose} className="mt-4 w-full py-2 rounded-md bg-navy-500 text-white text-sm">OK</button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white dark:bg-ink-900 rounded-lg shadow-2xl w-full max-w-lg overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-accent-primary" />
            <h2 className="font-semibold text-text-primary">Créer un rappel</h2>
            {ticker && <span className="text-xs font-mono text-text-muted">· {ticker}</span>}
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Type trigger */}
          <div>
            <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">Événement</label>
            <div className="grid grid-cols-2 gap-2">
              {TRIGGERS.map((t) => {
                const Icon = t.icon;
                const active = trigger === t.value;
                const disabled = t.value !== "custom_date" && !ticker;
                return (
                  <button
                    key={t.value}
                    onClick={() => !disabled && setTrigger(t.value)}
                    disabled={disabled}
                    className={
                      "flex items-start gap-2 p-3 rounded-md border text-left transition-colors " +
                      (active ? "border-navy-500 bg-navy-50" : "border-ink-200 hover:bg-ink-50") +
                      (disabled ? " opacity-40 cursor-not-allowed" : "")
                    }
                  >
                    <Icon className={"w-4 h-4 mt-0.5 shrink-0 " + (active ? "text-navy-600" : "text-ink-500")} />
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-ink-900">{t.label}</div>
                      <div className="text-[10px] text-ink-500 leading-relaxed mt-0.5">{t.help}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Paramètres spécifiques */}
          {trigger === "price_target" && (
            <div>
              <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">
                Me prévenir quand le cours est
              </label>
              <div className="flex gap-2">
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value as "above" | "below")}
                  className="w-32 px-3 py-2 border border-ink-300 rounded-md text-sm bg-white focus:outline-none focus:border-navy-500"
                >
                  <option value="above">≥ supérieur à</option>
                  <option value="below">≤ inférieur à</option>
                </select>
                <input
                  type="number"
                  step="0.01"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="Ex : 200"
                  className="flex-1 px-3 py-2 border border-ink-300 rounded-md text-sm focus:outline-none focus:border-navy-500"
                />
              </div>
            </div>
          )}

          {trigger === "custom_date" && (
            <div>
              <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">Date et heure</label>
              <input
                type="datetime-local"
                value={customDate}
                onChange={(e) => setCustomDate(e.target.value)}
                className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm focus:outline-none focus:border-navy-500"
              />
            </div>
          )}

          {/* Label perso */}
          <div>
            <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">
              Libellé (optionnel)
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={buildLabel(trigger, ticker, {})}
              className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm focus:outline-none focus:border-navy-500"
            />
          </div>

          {/* Canaux */}
          <div>
            <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">Notifications</label>
            <div className="space-y-2">
              <ChannelToggle
                label="Email"
                help="Reçu sur votre adresse de compte"
                value={channels.includes("email")}
                onChange={(v) => setChannels((c) => (v ? Array.from(new Set([...c, "email"])) : c.filter((x) => x !== "email")))}
              />
              <ChannelToggle
                label="Notification navigateur"
                help="Push Web (Chrome/Firefox). Nécessite d'autoriser les notifications."
                value={channels.includes("push")}
                onChange={togglePushChannel}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border-default bg-surface-muted/30">
          <button onClick={onClose} className="px-4 py-2 rounded-md text-sm text-ink-700 hover:bg-ink-100">Annuler</button>
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-md bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 disabled:opacity-50 flex items-center gap-1.5"
          >
            <Bell className="w-3.5 h-3.5" />
            {saving ? "…" : "Créer le rappel"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ChannelToggle({ label, help, value, onChange }: {
  label: string; help: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 p-3 rounded-md border border-ink-200">
      <div className="flex-1">
        <div className="text-sm font-medium text-ink-900">{label}</div>
        <div className="text-xs text-ink-500 mt-0.5">{help}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={"relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors mt-1 " + (value ? "bg-navy-500" : "bg-ink-300")}
      >
        <span className={"inline-block h-4 w-4 transform rounded-full bg-white transition-transform " + (value ? "translate-x-4" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

function buildLabel(trigger: TriggerType, ticker: string | undefined, value: Record<string, unknown>): string {
  const tk = ticker || "—";
  switch (trigger) {
    case "price_target": {
      const p = value.target;
      const d = value.direction === "below" ? "≤" : "≥";
      return p ? `${tk} ${d} ${p}` : `${tk} atteint la cible`;
    }
    case "earnings_date": return `${tk} · Earnings call`;
    case "dividend_exdate": return `${tk} · Ex-dividende`;
    case "quarterly_results": return `${tk} · Résultats trimestriels`;
    case "news": return `${tk} · News importante`;
    case "custom_date": return `Rappel · ${value.date || ""}`;
    default: return tk;
  }
}
