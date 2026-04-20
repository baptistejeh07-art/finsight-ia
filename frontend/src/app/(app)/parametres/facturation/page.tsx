"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, Sparkles, CreditCard, ExternalLink } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import { useI18n } from "@/i18n/provider";

const API = process.env.NEXT_PUBLIC_API_URL || "";

type Interval = "month" | "year";

interface PlanDef {
  slug: "decouverte" | "pro" | "enterprise";
  name: string;
  monthly: number;
  annual: number;
  features: string[];
  highlight?: boolean;
}

const PLANS: PlanDef[] = [
  {
    slug: "decouverte",
    name: "Découverte",
    monthly: 34.99,
    annual: 336,
    features: [
      "Analyses société cotée",
      "Analyses sectorielles & indices",
      "Livrables PDF / PPTX / Excel",
      "Commentaires IA en français ou anglais",
    ],
  },
  {
    slug: "pro",
    name: "Pro",
    monthly: 44.99,
    annual: 432,
    features: [
      "Tout Découverte +",
      "PME non cotées (Pappers + INPI)",
      "Portraits entreprise (15 pages)",
      "Analyses comparatives",
      "i18n — 6 langues / 6 devises",
      "Streaming SSE Q&A",
    ],
    highlight: true,
  },
  {
    slug: "enterprise",
    name: "Enterprise",
    monthly: 299,
    annual: 2870,
    features: [
      "Tout Pro +",
      "API access + rate limits élevés",
      "White-label (votre branding)",
      "Team seats multi-utilisateurs",
      "Support dédié + onboarding",
      "Intégrations custom (CRM, Slack)",
    ],
  },
];

export default function FacturationPage() {
  const { t, fc } = useI18n();
  const searchParams = useSearchParams();
  const [interval, setIntervalState] = useState<Interval>("month");
  const [currentPlan, setCurrentPlan] = useState<string>("free");
  const [periodEnd, setPeriodEnd] = useState<string | null>(null);
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);

  useEffect(() => {
    // Toasts de retour checkout
    const status = searchParams.get("status");
    if (status === "success") toast.success("Abonnement activé !");
    if (status === "cancel") toast("Paiement annulé");
  }, [searchParams]);

  useEffect(() => {
    async function loadCurrent() {
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();
      if (!data.user) return;
      const { data: prefs } = await supabase
        .from("user_preferences")
        .select("plan, plan_current_period_end, is_admin")
        .eq("user_id", data.user.id)
        .single();
      if (prefs?.is_admin) {
        setCurrentPlan("admin");
      } else {
        setCurrentPlan(prefs?.plan || "free");
        setPeriodEnd(prefs?.plan_current_period_end || null);
      }
    }
    loadCurrent();
  }, []);

  async function getToken() {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  }

  async function onSubscribe(plan: string) {
    setLoadingPlan(plan);
    try {
      const token = await getToken();
      if (!token) { toast.error("Connectez-vous d'abord"); return; }
      const r = await fetch(`${API}/stripe/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ plan, interval }),
      });
      const j = await r.json();
      if (!r.ok) {
        toast.error(j.detail || "Erreur checkout");
        return;
      }
      window.location.href = j.checkout_url;
    } catch (e) {
      toast.error("Erreur réseau");
    } finally {
      setLoadingPlan(null);
    }
  }

  async function onPortal() {
    try {
      const token = await getToken();
      if (!token) return;
      const r = await fetch(`${API}/stripe/portal`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      const j = await r.json();
      if (!r.ok) { toast.error(j.detail || "Erreur portail"); return; }
      window.location.href = j.portal_url;
    } catch {
      toast.error("Erreur réseau");
    }
  }

  const isAdmin = currentPlan === "admin";

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Plan actuel */}
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-2">Abonnement</h2>
        {isAdmin ? (
          <div className="bg-navy-50 border border-navy-200 rounded-md p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-navy-700">
              <Sparkles className="w-4 h-4" />
              Accès administrateur — analyses illimitées
            </div>
            <p className="text-xs text-ink-600 mt-1">
              Tu es admin FinSight. Tu bypasses les quotas et accèdes à toutes les features.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-ink-200 rounded-md p-4 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-ink-900">
                Plan actuel : <span className="text-navy-500 capitalize">{currentPlan}</span>
              </div>
              {periodEnd && (
                <div className="text-xs text-ink-500 mt-0.5">
                  Prochain renouvellement : {new Date(periodEnd).toLocaleDateString("fr-FR")}
                </div>
              )}
            </div>
            {currentPlan !== "free" && (
              <button
                onClick={onPortal}
                className="flex items-center gap-1.5 text-xs text-navy-500 border border-navy-200 rounded px-3 py-1.5 hover:bg-navy-50"
              >
                <CreditCard className="w-3 h-3" /> Gérer
                <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </section>

      {/* Plans + toggle mensuel/annuel */}
      {!isAdmin && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-ink-900">Choisir un plan</h3>
            <div className="inline-flex bg-ink-100 rounded-full p-0.5">
              <button
                onClick={() => setIntervalState("month")}
                className={`text-xs px-3 py-1 rounded-full transition-colors ${
                  interval === "month" ? "bg-white text-ink-900 font-semibold shadow-sm" : "text-ink-600"
                }`}
              >
                Mensuel
              </button>
              <button
                onClick={() => setIntervalState("year")}
                className={`text-xs px-3 py-1 rounded-full transition-colors ${
                  interval === "year" ? "bg-white text-ink-900 font-semibold shadow-sm" : "text-ink-600"
                }`}
              >
                Annuel <span className="text-signal-buy">-20%</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLANS.map((p) => {
              const price = interval === "month" ? p.monthly : p.annual;
              const priceLabel = interval === "month"
                ? `${price.toFixed(2)} € /mois`
                : `${price.toFixed(0)} € /an`;
              const isCurrent = currentPlan === p.slug;
              return (
                <div
                  key={p.slug}
                  className={`rounded-md border p-5 ${
                    p.highlight ? "border-navy-500 shadow-md ring-1 ring-navy-500" : "border-ink-200"
                  }`}
                >
                  {p.highlight && (
                    <div className="text-[10px] uppercase tracking-widest text-navy-500 font-bold mb-2">
                      Recommandé
                    </div>
                  )}
                  <div className="text-lg font-bold text-ink-900">{p.name}</div>
                  <div className="text-2xl font-mono text-ink-900 mt-2">{priceLabel}</div>
                  {interval === "year" && (
                    <div className="text-[10px] text-ink-500 mt-0.5">
                      (soit {(price / 12).toFixed(2)} €/mois)
                    </div>
                  )}
                  <ul className="mt-4 space-y-2">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-xs text-ink-700">
                        <Check className="w-3.5 h-3.5 text-signal-buy mt-0.5 shrink-0" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => onSubscribe(p.slug)}
                    disabled={isCurrent || loadingPlan === p.slug}
                    className={`mt-5 w-full py-2 rounded-md text-sm font-semibold transition-colors ${
                      p.highlight
                        ? "bg-navy-500 text-white hover:bg-navy-600"
                        : "border border-ink-300 text-ink-800 hover:bg-ink-50"
                    } ${isCurrent ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    {loadingPlan === p.slug
                      ? "…"
                      : isCurrent
                        ? "Plan actuel"
                        : "S'abonner"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="border-t border-ink-200 pt-6">
        <p className="text-xs text-ink-500">
          Paiement sécurisé par Stripe. Annulable à tout moment depuis le portail « Gérer ».
          TVA ajustée selon votre pays de facturation.
        </p>
      </section>
    </div>
  );
}
