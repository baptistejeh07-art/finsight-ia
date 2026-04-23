"use client";

import { useEffect, useState } from "react";
import { Gift, Share2, UserPlus, Star, Linkedin, Check } from "lucide-react";
import toast from "react-hot-toast";
import { useI18n } from "@/i18n/provider";

interface Mission {
  id: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  reward: string;
  action: string;
  onAction: () => void;
}

function openShare(url: string, title: string, text: string) {
  if (typeof navigator !== "undefined" && typeof (navigator as unknown as { share?: unknown }).share === "function") {
    const nav = navigator as unknown as { share: (d: { title: string; text: string; url: string }) => Promise<void> };
    nav.share({ title, text, url }).catch(() => {});
    return;
  }
  window.open(url, "_blank", "noopener");
}

export default function UtilisationPage() {
  const { t } = useI18n();
  const reset = t("settings.use_reset_in_days").replace("{days}", "22");
  const usage = [
    { label: t("settings.use_label_societe"), used: 4, total: 10, reset },
    { label: t("settings.use_label_secteur"), used: 1, total: 5, reset },
    { label: t("settings.use_label_indice"), used: 0, total: 2, reset },
    { label: t("settings.use_label_portrait"), used: 2, total: 5, reset },
  ];

  // Missions persistées en localStorage (trackage claim côté client, backend à câbler)
  const [claimed, setClaimed] = useState<Record<string, boolean>>({});
  const [bonusAnalyses, setBonusAnalyses] = useState(0);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("finsight-missions-claimed");
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, boolean>;
        setClaimed(parsed);
        setBonusAnalyses(
          Object.entries(parsed).reduce((acc, [id, done]) => {
            if (!done) return acc;
            if (id === "share-linkedin") return acc + 3;
            if (id === "invite-3") return acc + 5;
            if (id === "testimonial") return acc + 5;
            if (id === "connect-linkedin") return acc + 2;
            return acc;
          }, 0)
        );
      }
    } catch {
      // ignore
    }
  }, []);

  function claim(id: string, bonus: number) {
    const next = { ...claimed, [id]: true };
    setClaimed(next);
    setBonusAnalyses((v) => v + bonus);
    try {
      localStorage.setItem("finsight-missions-claimed", JSON.stringify(next));
    } catch {
      // ignore
    }
    toast.success(`+${bonus} analyses bonus créditées`);
  }

  const shareUrl = "https://finsight-ia.com/?ref=utilisation";
  const shareText =
    "Je teste FinSight IA — analyse financière auditable (DCF, ratios, scénarios) sur une société cotée ou PME française en 60 sec. Rapport PDF + pitchbook PowerPoint + modèle Excel. Recommandé.";

  const missions: Mission[] = [
    {
      id: "share-linkedin",
      icon: <Linkedin className="w-4 h-4" />,
      title: "Partagez FinSight sur LinkedIn",
      description:
        "Publiez un avis (ou partagez une analyse anonymisée) en mentionnant finsight-ia.com.",
      reward: "+3 analyses",
      action: "Partager sur LinkedIn",
      onAction: () => {
        openShare(
          `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
          "FinSight IA",
          shareText
        );
        claim("share-linkedin", 3);
      },
    },
    {
      id: "invite-3",
      icon: <UserPlus className="w-4 h-4" />,
      title: "Invitez 3 collègues via votre lien de parrainage",
      description:
        "Partagez le lien — chaque inscription compte. Bonus crédité après la 3e inscription confirmée.",
      reward: "+5 analyses / mois",
      action: "Copier mon lien",
      onAction: () => {
        navigator.clipboard.writeText(shareUrl).catch(() => {});
        toast.success("Lien de parrainage copié");
        claim("invite-3", 5);
      },
    },
    {
      id: "testimonial",
      icon: <Star className="w-4 h-4" />,
      title: "Écrivez un témoignage (3 lignes)",
      description:
        "Envoyez-nous un retour honnête sur votre usage — utilisé (avec votre accord) sur la page vitrine.",
      reward: "+5 analyses",
      action: "Envoyer un témoignage",
      onAction: () => {
        window.location.href = `mailto:contact@finsight-ia.com?subject=${encodeURIComponent("Témoignage FinSight")}&body=${encodeURIComponent("Voici mon retour sur FinSight après quelques analyses :\n\n")}`;
        claim("testimonial", 5);
      },
    },
    {
      id: "connect-linkedin",
      icon: <Share2 className="w-4 h-4" />,
      title: "Partagez votre première analyse générée",
      description:
        "Depuis l'écran résultats, utilisez le bouton « Partager » et publiez le lien sur LinkedIn ou X.",
      reward: "+2 analyses",
      action: "J'ai partagé",
      onAction: () => claim("connect-linkedin", 2),
    },
  ];

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-ink-900">{t("settings.use_title")}</h2>
          <span className="text-xs text-ink-500">{t("settings.bil_plan_name")}</span>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          {t("settings.use_intro")}
        </p>

        {bonusAnalyses > 0 && (
          <div className="mb-5 p-3 bg-signal-buy/10 border border-signal-buy/30 rounded-md text-sm text-ink-900 flex items-center gap-2">
            <Gift className="w-4 h-4 text-signal-buy" />
            <span>
              <strong>+{bonusAnalyses} analyses bonus</strong> créditées ce mois grâce aux missions accomplies.
            </span>
          </div>
        )}

        <div className="space-y-5">
          {usage.map((u) => {
            const pct = u.total > 0 ? Math.min((u.used / u.total) * 100, 100) : 0;
            return (
              <div key={u.label}>
                <div className="flex items-baseline justify-between mb-1">
                  <div>
                    <div className="text-sm text-ink-900">{u.label}</div>
                    <div className="text-[11px] text-ink-500">{u.reset}</div>
                  </div>
                  <div className="text-xs text-ink-600 font-mono">
                    {u.used} / {u.total}
                  </div>
                </div>
                <div className="h-1.5 w-full bg-ink-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-navy-500 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Gamification — Missions bonus */}
      <section className="border-t border-ink-200 pt-8">
        <div className="flex items-center gap-2 mb-1">
          <Gift className="w-4 h-4 text-navy-500" />
          <h3 className="text-base font-semibold text-ink-900">
            Missions — débloquez des analyses bonus
          </h3>
        </div>
        <p className="text-sm text-ink-600 mb-4">
          Accomplissez des actions simples pour créditer des analyses supplémentaires sur votre quota mensuel.
        </p>

        <div className="space-y-2">
          {missions.map((m) => {
            const done = !!claimed[m.id];
            return (
              <div
                key={m.id}
                className={`flex items-start gap-3 p-3 rounded-md border transition-colors ${
                  done ? "bg-signal-buy/5 border-signal-buy/30" : "bg-white border-ink-200 hover:border-navy-300"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-md shrink-0 flex items-center justify-center ${
                    done ? "bg-signal-buy/20 text-signal-buy" : "bg-navy-50 text-navy-500"
                  }`}
                >
                  {done ? <Check className="w-4 h-4" /> : m.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="text-sm font-semibold text-ink-900">{m.title}</div>
                    <span className="text-[11px] font-mono text-signal-buy shrink-0">{m.reward}</span>
                  </div>
                  <div className="text-xs text-ink-600 mt-0.5">{m.description}</div>
                </div>
                <button
                  onClick={m.onAction}
                  disabled={done}
                  className={`text-xs px-3 py-1.5 rounded shrink-0 transition-colors ${
                    done
                      ? "text-signal-buy bg-transparent cursor-default"
                      : "bg-navy-500 text-white hover:bg-navy-600"
                  }`}
                >
                  {done ? "Réclamé" : m.action}
                </button>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-[11px] text-ink-400">
          Les bonus sont crédités une fois par action. En cas d&apos;abus, les bonus peuvent être révoqués.
        </p>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">{t("settings.use_history")}</h3>
        <p className="text-sm text-ink-600">
          {t("settings.use_history_intro")}
        </p>
        <div className="mt-4 py-12 text-center text-sm text-ink-400 border border-dashed border-ink-200 rounded-md">
          {t("settings.use_chart_soon")}
        </div>
      </section>
    </div>
  );
}
