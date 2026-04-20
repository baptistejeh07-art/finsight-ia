"use client";

import { useState } from "react";
import {
  Bell, Target, Calendar, DollarSign, Newspaper, FileText, Trash2, Mail, Smartphone, CheckCircle2, XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { useAlerts, patchAlert, deleteAlert, type Alert } from "@/hooks/use-alerts";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  price_target: Target,
  earnings_date: Calendar,
  dividend_exdate: DollarSign,
  news: Newspaper,
  custom_date: Calendar,
  quarterly_results: FileText,
};

const TYPE_LABELS: Record<string, string> = {
  price_target: "Cours cible",
  earnings_date: "Earnings call",
  dividend_exdate: "Ex-dividende",
  news: "News ticker",
  custom_date: "Date perso",
  quarterly_results: "Résultats Q",
};

export default function RappelsPage() {
  const { alerts, loading, reload } = useAlerts();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function toggle(a: Alert) {
    setBusyId(a.id);
    const ok = await patchAlert(a.id, { enabled: !a.enabled });
    setBusyId(null);
    if (ok) { toast.success(a.enabled ? "Rappel désactivé" : "Rappel activé"); reload(); }
    else toast.error("Échec");
  }
  async function remove(a: Alert) {
    if (!confirm(`Supprimer le rappel « ${a.label || a.ticker} » ?`)) return;
    setBusyId(a.id);
    const ok = await deleteAlert(a.id);
    setBusyId(null);
    if (ok) { toast.success("Supprimé"); reload(); }
    else toast.error("Échec");
  }

  const active = alerts.filter((a) => a.enabled && !a.fired_at);
  const fired = alerts.filter((a) => a.fired_at);
  const paused = alerts.filter((a) => !a.enabled && !a.fired_at);

  if (loading) return <div className="text-sm text-ink-500">Chargement…</div>;

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center gap-2 mb-2">
          <Bell className="w-5 h-5 text-ink-700" />
          <h2 className="text-lg font-semibold text-ink-900">Mes rappels</h2>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          Configurez des rappels pour être notifié quand une condition est atteinte (cours cible,
          earnings call, ex-dividende, résultats trimestriels…). Vérifications toutes les 6 h.
          Email + notifications navigateur au choix.
        </p>

        {alerts.length === 0 && (
          <div className="rounded-md border border-dashed border-ink-300 p-8 text-center">
            <Bell className="w-6 h-6 text-ink-400 mx-auto mb-2" />
            <div className="text-sm text-ink-700 font-medium">Aucun rappel pour le moment</div>
            <div className="text-xs text-ink-500 mt-1">
              Créez-en un depuis la page de résultats d&apos;une analyse.
            </div>
          </div>
        )}

        {active.length > 0 && (
          <Block title={`Actifs (${active.length})`}>
            {active.map((a) => (
              <AlertRow key={a.id} alert={a} busy={busyId === a.id} onToggle={() => toggle(a)} onDelete={() => remove(a)} />
            ))}
          </Block>
        )}
        {paused.length > 0 && (
          <Block title={`En pause (${paused.length})`}>
            {paused.map((a) => (
              <AlertRow key={a.id} alert={a} busy={busyId === a.id} onToggle={() => toggle(a)} onDelete={() => remove(a)} />
            ))}
          </Block>
        )}
        {fired.length > 0 && (
          <Block title={`Déclenchés (${fired.length})`}>
            {fired.map((a) => (
              <AlertRow key={a.id} alert={a} busy={busyId === a.id} onDelete={() => remove(a)} fired />
            ))}
          </Block>
        )}
      </section>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <div className="text-2xs uppercase tracking-widest text-ink-500 font-semibold mb-2">{title}</div>
      <div className="border border-ink-200 rounded-md divide-y divide-ink-100 bg-white">{children}</div>
    </div>
  );
}

function AlertRow({ alert, busy, onToggle, onDelete, fired }: {
  alert: Alert; busy: boolean; onToggle?: () => void; onDelete: () => void; fired?: boolean;
}) {
  const Icon = ICONS[alert.trigger_type] || Bell;
  const typeLabel = TYPE_LABELS[alert.trigger_type] || alert.trigger_type;
  const hasEmail = alert.channels.includes("email");
  const hasPush = alert.channels.includes("push");

  const value = alert.trigger_value as { target?: number; direction?: string; date?: string };
  const detail = alert.trigger_type === "price_target" && value.target
    ? `${value.direction === "below" ? "≤" : "≥"} ${value.target}`
    : value.date
    ? new Date(value.date).toLocaleString("fr-FR")
    : "";

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className={"shrink-0 w-8 h-8 rounded-md flex items-center justify-center " + (fired ? "bg-signal-buy/15 text-signal-buy" : "bg-ink-100 text-ink-600")}>
        {fired ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink-900 truncate">
          {alert.label || `${alert.ticker || ""} · ${typeLabel}`}
        </div>
        <div className="text-xs text-ink-500 mt-0.5 flex items-center gap-2 flex-wrap">
          <span>{typeLabel}</span>
          {detail && <><span>·</span><span className="font-mono">{detail}</span></>}
          {hasEmail && <><span>·</span><Mail className="w-3 h-3" /></>}
          {hasPush && <><span>·</span><Smartphone className="w-3 h-3" /></>}
          {fired && <><span>·</span><span className="text-signal-buy font-medium">Déclenché le {new Date(alert.fired_at!).toLocaleDateString("fr-FR")}</span></>}
        </div>
      </div>
      {onToggle && !fired && (
        <button
          onClick={onToggle}
          disabled={busy}
          className={"relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors " + (alert.enabled ? "bg-navy-500" : "bg-ink-300")}
          title={alert.enabled ? "Désactiver" : "Activer"}
        >
          <span className={"inline-block h-4 w-4 transform rounded-full bg-white transition-transform " + (alert.enabled ? "translate-x-4" : "translate-x-0.5")} />
        </button>
      )}
      <button onClick={onDelete} disabled={busy} className="shrink-0 p-1.5 rounded hover:bg-ink-100 text-ink-500 hover:text-signal-sell" title="Supprimer">
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
