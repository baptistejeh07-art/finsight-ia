"use client";

import { Building2, Users, AlertTriangle, TrendingUp, ShieldCheck, FileX } from "lucide-react";
import type { AnalysisData } from "./types";
import { useI18n } from "@/i18n/provider";

function Row({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-xs border-b border-ink-100 last:border-b-0">
      <span className="text-ink-500">{label}</span>
      <span className={`text-ink-900 text-right ${mono ? "font-mono" : "font-medium"}`}>
        {value ?? "—"}
      </span>
    </div>
  );
}

/** Bloc Identité PME (toujours affiché) */
export function PmeIdentiteCard({ data }: { data: AnalysisData }) {
  const { t, fc } = useI18n();
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Building2 className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          {t("pme.identity")}
        </div>
      </div>
      <Row label={t("pme.siren")} value={data.siren} mono />
      <Row label={t("pme.legal_form")} value={data.forme_juridique} />
      <Row label={t("pme.naf_code")} value={data.code_naf ? `${data.code_naf}` : "—"} mono />
      <Row label={t("pme.activity")} value={data.libelle_naf} />
      <Row label={t("pme.head_office")} value={data.ville_siege} />
      <Row label={t("pme.share_capital")} value={fc(data.capital)} mono />
      <Row label={t("pme.sector_profile")} value={data.profile?.name} />
    </div>
  );
}

/** Bloc Dirigeants (toujours affiché si présents) */
export function PmeDirigeantsCard({ data }: { data: AnalysisData }) {
  const { t } = useI18n();
  const dirs = data.dirigeants || [];
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          {t("pme.directors")} ({dirs.length})
        </div>
      </div>
      {dirs.length === 0 ? (
        <div className="text-xs text-ink-400 italic">—</div>
      ) : (
        <div className="space-y-2">
          {dirs.slice(0, 12).map((d, i) => {
            const nom = [d.prenom, d.nom].filter(Boolean).join(" ").trim() || d.denomination || "—";
            return (
              <div key={i} className="border-b border-ink-100 pb-1.5 last:border-b-0">
                <div className="text-sm font-medium text-ink-900">{nom}</div>
                <div className="text-[11px] text-ink-500">
                  {d.qualite || "—"}
                  {d.date_prise_de_poste && <> · depuis {d.date_prise_de_poste}</>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Bloc BODACC (toujours affiché) */
export function PmeBodaccCard({ data }: { data: AnalysisData }) {
  const { t } = useI18n();
  const b = data.bodacc || {};
  const hasRisque = (b.procedures_collectives || 0) > 0 || b.radie;
  const color = hasRisque ? "text-signal-sell" : "text-signal-buy";
  const Icon = hasRisque ? AlertTriangle : ShieldCheck;
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-4 h-4 ${color}`} />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          {t("pme.bodacc")}
        </div>
      </div>
      <Row label={t("pme.bodacc")} value={b.total_annonces ?? 0} mono />
      <Row label="Procédures collectives" value={b.procedures_collectives ?? 0} mono />
      <Row label="Dernière procédure" value={b.derniere_procedure || "—"} />
      <Row label="Dernier dépôt de comptes" value={b.dernier_depot_comptes || "—"} />
      <Row label="Société radiée" value={b.radie ? t("common.yes") : t("common.no")} />
      {hasRisque && (
        <div className="mt-3 text-xs text-signal-sell/80 italic">
          ⚠ {b.penalty ?? 0}
        </div>
      )}
    </div>
  );
}

/** Bloc Scores (si has_accounts=True) */
export function PmeScoresCard({ data }: { data: AnalysisData }) {
  const { t, fc } = useI18n();
  const s = data.analysis_summary;
  if (!s) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-ink-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            {t("pme.scoring")}
          </div>
        </div>
        <div className="text-xs text-ink-400 italic">{t("pme.no_accounts")}</div>
      </div>
    );
  }
  const verdictColor = s.altman_verdict === "safe" ? "text-signal-buy"
    : s.altman_verdict === "distress" ? "text-signal-sell" : "text-amber-600";
  const scoreColor = (v: number | null | undefined) =>
    v == null ? "text-ink-500" : v >= 70 ? "text-signal-buy" : v >= 40 ? "text-amber-600" : "text-signal-sell";
  const verdictLabel = s.altman_verdict === "safe"
    ? `✓ ${t("pme.altman_verdict.safe")}`
    : s.altman_verdict === "distress"
    ? `⚠ ${t("pme.altman_verdict.distress")}`
    : s.altman_verdict === "grey"
    ? `~ ${t("pme.altman_verdict.grey")}`
    : "";

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          {t("pme.scoring")}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-ink-50 rounded-md p-2.5">
          <div className="text-[10px] text-ink-500">{t("pme.health_score")}</div>
          <div className={`text-xl font-bold font-mono ${scoreColor(s.health_score)}`}>
            {s.health_score != null ? `${s.health_score.toFixed(0)}/100` : "—"}
          </div>
        </div>
        <div className="bg-ink-50 rounded-md p-2.5">
          <div className="text-[10px] text-ink-500">{t("pme.bankability_score")}</div>
          <div className={`text-xl font-bold font-mono ${scoreColor(s.bankability_score)}`}>
            {s.bankability_score != null ? `${s.bankability_score.toFixed(0)}/100` : "—"}
          </div>
        </div>
      </div>
      <Row label={t("kpi.altman_z")} value={s.altman_z != null ? s.altman_z.toFixed(2) : "—"} mono />
      <div className={`text-[11px] font-medium mt-0.5 ${verdictColor}`}>{verdictLabel}</div>
      <Row label={t("pme.debt_capacity")} value={fc(s.debt_capacity_estimate)} mono />
    </div>
  );
}

/** Bloc "Comptes non publics" — affiché SI has_accounts=false */
export function PmeNoAccountsNotice({ data }: { data: AnalysisData }) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-2">
        <FileX className="w-5 h-5 text-amber-600" />
        <div className="text-sm font-semibold text-amber-900">
          Comptes annuels non disponibles
        </div>
      </div>
      <p className="text-xs text-amber-800 leading-relaxed">
        <strong>{data.denomination}</strong> n&apos;a pas de comptes annuels publiés accessibles
        via Pappers. Plusieurs raisons possibles :
      </p>
      <ul className="text-xs text-amber-800 mt-2 space-y-1 list-disc pl-5">
        <li>Confidentialité du compte de résultat activée (option légale pour PME)</li>
        <li>Société récente qui n&apos;a pas encore déposé</li>
        <li>Micro-entreprise sans obligation de dépôt commercial</li>
      </ul>
      <p className="text-xs text-amber-800 mt-3">
        L&apos;analyse ci-dessous se base sur l&apos;identité, les dirigeants et les
        publications BODACC uniquement. Pour une analyse financière complète,
        obtenez les liasses fiscales auprès du dirigeant et saisissez-les manuellement.
      </p>
    </div>
  );
}
