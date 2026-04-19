"use client";

import { Building2, Users, AlertTriangle, TrendingUp, ShieldCheck, FileX } from "lucide-react";
import type { AnalysisData } from "./types";

function fmtEur(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)} Md €`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)} M €`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)} k €`;
  return `${v.toLocaleString("fr-FR")} €`;
}

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
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Building2 className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Identité de la société
        </div>
      </div>
      <Row label="SIREN" value={data.siren} mono />
      <Row label="Forme juridique" value={data.forme_juridique} />
      <Row label="Code NAF" value={data.code_naf ? `${data.code_naf}` : "—"} mono />
      <Row label="Activité" value={data.libelle_naf} />
      <Row label="Ville du siège" value={data.ville_siege} />
      <Row label="Capital social" value={fmtEur(data.capital)} mono />
      <Row label="Profil sectoriel" value={data.profile?.name} />
    </div>
  );
}

/** Bloc Dirigeants (toujours affiché si présents) */
export function PmeDirigeantsCard({ data }: { data: AnalysisData }) {
  const dirs = data.dirigeants || [];
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Dirigeants ({dirs.length})
        </div>
      </div>
      {dirs.length === 0 ? (
        <div className="text-xs text-ink-400 italic">Aucun dirigeant listé via Pappers.</div>
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
  const b = data.bodacc || {};
  const hasRisque = (b.procedures_collectives || 0) > 0 || b.radie;
  const color = hasRisque ? "text-signal-sell" : "text-signal-buy";
  const Icon = hasRisque ? AlertTriangle : ShieldCheck;
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-4 h-4 ${color}`} />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Publications BODACC
        </div>
      </div>
      <Row label="Annonces légales (total)" value={b.total_annonces ?? 0} mono />
      <Row label="Procédures collectives" value={b.procedures_collectives ?? 0} mono />
      <Row label="Dernière procédure" value={b.derniere_procedure || "Aucune"} />
      <Row label="Dernier dépôt de comptes" value={b.dernier_depot_comptes || "—"} />
      <Row label="Société radiée" value={b.radie ? "Oui" : "Non"} />
      {hasRisque && (
        <div className="mt-3 text-xs text-signal-sell/80 italic">
          ⚠ Signaux d&apos;alerte BODACC détectés — pénalité scoring : {b.penalty ?? 0}
        </div>
      )}
    </div>
  );
}

/** Bloc Scores (si has_accounts=True) */
export function PmeScoresCard({ data }: { data: AnalysisData }) {
  const s = data.analysis_summary;
  if (!s) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-ink-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Scoring financier
          </div>
        </div>
        <div className="text-xs text-ink-400 italic">
          Comptes non disponibles publiquement — scoring non calculable.
        </div>
      </div>
    );
  }
  const verdictColor = s.altman_verdict === "safe" ? "text-signal-buy"
    : s.altman_verdict === "distress" ? "text-signal-sell" : "text-amber-600";
  const scoreColor = (v: number | null | undefined) =>
    v == null ? "text-ink-500" : v >= 70 ? "text-signal-buy" : v >= 40 ? "text-amber-600" : "text-signal-sell";

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Scoring financier FinSight
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-ink-50 rounded-md p-2.5">
          <div className="text-[10px] text-ink-500">Santé</div>
          <div className={`text-xl font-bold font-mono ${scoreColor(s.health_score)}`}>
            {s.health_score != null ? `${s.health_score.toFixed(0)}/100` : "—"}
          </div>
        </div>
        <div className="bg-ink-50 rounded-md p-2.5">
          <div className="text-[10px] text-ink-500">Bankabilité</div>
          <div className={`text-xl font-bold font-mono ${scoreColor(s.bankability_score)}`}>
            {s.bankability_score != null ? `${s.bankability_score.toFixed(0)}/100` : "—"}
          </div>
        </div>
      </div>
      <Row label="Altman Z-Score" value={s.altman_z != null ? s.altman_z.toFixed(2) : "—"} mono />
      <div className={`text-[11px] font-medium mt-0.5 ${verdictColor}`}>
        {s.altman_verdict === "safe" ? "✓ Zone saine" :
          s.altman_verdict === "distress" ? "⚠ Détresse probable" :
          s.altman_verdict === "grey" ? "~ Zone grise" : ""}
      </div>
      <Row label="Dette additionnelle accessible" value={fmtEur(s.debt_capacity_estimate)} mono />
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
