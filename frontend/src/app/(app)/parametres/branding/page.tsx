"use client";

import { useState, useEffect } from "react";
import { Palette, Image as ImageIcon, Building2, Save, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";

interface BrandingState {
  brand_logo_url: string;
  brand_primary_color: string;
  brand_secondary_color: string;
  brand_company_name: string;
}

const DEFAULT: BrandingState = {
  brand_logo_url: "",
  brand_primary_color: "#1B2A4A",
  brand_secondary_color: "#6B7280",
  brand_company_name: "",
};

export default function BrandingPage() {
  const [b, setB] = useState<BrandingState>(DEFAULT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { setLoading(false); return; }
      const { data } = await supabase
        .from("user_preferences")
        .select("brand_logo_url, brand_primary_color, brand_secondary_color, brand_company_name")
        .eq("user_id", user.id)
        .maybeSingle();
      if (data) {
        setB({
          brand_logo_url: data.brand_logo_url || "",
          brand_primary_color: data.brand_primary_color || DEFAULT.brand_primary_color,
          brand_secondary_color: data.brand_secondary_color || DEFAULT.brand_secondary_color,
          brand_company_name: data.brand_company_name || "",
        });
      }
      setLoading(false);
    })();
  }, []);

  async function save() {
    setSaving(true);
    const supabase = createClient();
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        toast.error("Non connecté");
        return;
      }
      const { error } = await supabase
        .from("user_preferences")
        .upsert({
          user_id: user.id,
          brand_logo_url: b.brand_logo_url || null,
          brand_primary_color: b.brand_primary_color,
          brand_secondary_color: b.brand_secondary_color,
          brand_company_name: b.brand_company_name || null,
        }, { onConflict: "user_id" });
      if (error) throw error;
      toast.success("Branding enregistré");
    } catch (e) {
      toast.error("Échec enregistrement");
      console.warn(e);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="text-sm text-ink-500 italic">Chargement…</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50 mb-1">
          Branding & White-label
        </h2>
        <p className="text-sm text-ink-600 dark:text-ink-400">
          Personnalisez le logo et les couleurs utilisés dans vos livrables PDF
          et PPTX. Idéal pour les CGP, cabinets et conseillers qui distribuent
          les analyses à leurs clients.
        </p>
      </header>

      {/* Note plan Pro */}
      <div className="bg-amber-50 border border-amber-200 rounded-md p-3 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-800">
          <strong>Plan Pro requis</strong> pour appliquer le branding aux livrables exportés.
          Configuration sauvegardée mais non encore appliquée tant que les writers PDF/PPTX
          ne sont pas mis à jour (livraison sprint suivant).
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Nom entreprise */}
        <div>
          <label className="text-xs font-semibold text-ink-700 dark:text-ink-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5" />
            Nom de votre entreprise
          </label>
          <input
            type="text"
            value={b.brand_company_name}
            onChange={(e) => setB({ ...b, brand_company_name: e.target.value })}
            placeholder="Ex: Cabinet Jeh & Associés"
            className="w-full px-3 py-2 border border-ink-200 rounded text-sm bg-white dark:bg-ink-900 dark:border-ink-700 dark:text-ink-50"
          />
          <p className="text-[10px] text-ink-500 mt-1">
            Affiché en bas de chaque slide / page PDF en mention légale.
          </p>
        </div>

        {/* Logo URL */}
        <div>
          <label className="text-xs font-semibold text-ink-700 dark:text-ink-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
            <ImageIcon className="w-3.5 h-3.5" />
            URL du logo (PNG / SVG)
          </label>
          <input
            type="url"
            value={b.brand_logo_url}
            onChange={(e) => setB({ ...b, brand_logo_url: e.target.value })}
            placeholder="https://votre-cabinet.fr/logo.png"
            className="w-full px-3 py-2 border border-ink-200 rounded text-sm bg-white dark:bg-ink-900 dark:border-ink-700 dark:text-ink-50"
          />
          <p className="text-[10px] text-ink-500 mt-1">
            URL accessible publiquement. Idéal : PNG transparent 600px de large.
          </p>
        </div>

        {/* Couleur primaire */}
        <div>
          <label className="text-xs font-semibold text-ink-700 dark:text-ink-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
            <Palette className="w-3.5 h-3.5" />
            Couleur principale (titres, accents)
          </label>
          <div className="flex gap-2 items-center">
            <input
              type="color"
              value={b.brand_primary_color}
              onChange={(e) => setB({ ...b, brand_primary_color: e.target.value })}
              className="h-10 w-14 border border-ink-200 rounded cursor-pointer"
            />
            <input
              type="text"
              value={b.brand_primary_color}
              onChange={(e) => setB({ ...b, brand_primary_color: e.target.value })}
              className="flex-1 px-3 py-2 border border-ink-200 rounded text-sm font-mono bg-white dark:bg-ink-900 dark:border-ink-700 dark:text-ink-50"
              maxLength={7}
            />
          </div>
        </div>

        {/* Couleur secondaire */}
        <div>
          <label className="text-xs font-semibold text-ink-700 dark:text-ink-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
            <Palette className="w-3.5 h-3.5" />
            Couleur secondaire (sous-titres, lignes)
          </label>
          <div className="flex gap-2 items-center">
            <input
              type="color"
              value={b.brand_secondary_color}
              onChange={(e) => setB({ ...b, brand_secondary_color: e.target.value })}
              className="h-10 w-14 border border-ink-200 rounded cursor-pointer"
            />
            <input
              type="text"
              value={b.brand_secondary_color}
              onChange={(e) => setB({ ...b, brand_secondary_color: e.target.value })}
              className="flex-1 px-3 py-2 border border-ink-200 rounded text-sm font-mono bg-white dark:bg-ink-900 dark:border-ink-700 dark:text-ink-50"
              maxLength={7}
            />
          </div>
        </div>
      </div>

      {/* Aperçu */}
      <div className="bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 rounded-md overflow-hidden">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-500 px-3 py-1.5 border-b border-ink-100 dark:border-ink-700">
          Aperçu
        </div>
        <div className="p-6">
          <div
            className="rounded-md p-5 text-white"
            style={{ background: b.brand_primary_color }}
          >
            <div className="flex items-center gap-3">
              {b.brand_logo_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={b.brand_logo_url}
                  alt=""
                  className="h-10 w-auto bg-white/10 rounded p-1"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              )}
              <div>
                <div className="text-xs uppercase tracking-widest opacity-75">Pitchbook</div>
                <div className="text-lg font-bold">{b.brand_company_name || "Votre cabinet"}</div>
              </div>
            </div>
          </div>
          <div
            className="px-5 py-3 text-xs"
            style={{ color: b.brand_secondary_color }}
          >
            Couleur secondaire — utilisée pour les sous-titres et bordures
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-2 bg-navy-500 hover:bg-navy-600 disabled:bg-ink-300 text-white text-sm font-semibold px-4 py-2 rounded transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? "Enregistrement…" : "Enregistrer le branding"}
        </button>
      </div>
    </div>
  );
}
