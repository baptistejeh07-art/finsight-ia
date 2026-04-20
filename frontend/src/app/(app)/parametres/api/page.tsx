"use client";

import { useEffect, useState } from "react";
import { Key, Plus, Trash2, Copy, Check, Eye, EyeOff, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface ApiKey {
  id: string;
  key_prefix: string;
  name: string;
  rate_limit_per_min: number;
  rate_limit_per_day: number;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

async function getToken(): Promise<string | null> {
  const s = createClient();
  const { data } = await s.auth.getSession();
  return data.session?.access_token || null;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [rateMin, setRateMin] = useState(30);
  const [rateDay, setRateDay] = useState(1000);
  const [revealed, setRevealed] = useState<{ id: string; plain: string } | null>(null);
  const [copied, setCopied] = useState(false);

  async function load() {
    setLoading(true);
    const t = await getToken();
    if (!t) { setLoading(false); return; }
    const r = await fetch(`${API}/me/api-keys`, { headers: { Authorization: `Bearer ${t}` } });
    if (r.ok) setKeys((await r.json()).keys || []);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!newKeyName.trim()) { toast.error("Nom requis"); return; }
    setCreating(true);
    try {
      const t = await getToken();
      if (!t) return;
      const r = await fetch(`${API}/me/api-keys`, {
        method: "POST",
        headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName, rate_limit_per_min: rateMin, rate_limit_per_day: rateDay }),
      });
      const j = await r.json();
      if (!r.ok) { toast.error(j.detail || "Échec"); return; }
      toast.success("Clé créée — copiez-la maintenant !");
      setRevealed({ id: j.key_row?.id || "", plain: j.key });
      setNewKeyName("");
      load();
    } finally {
      setCreating(false);
    }
  }

  async function revoke(id: string) {
    if (!confirm("Révoquer cette clé ? Cette action est irréversible.")) return;
    const t = await getToken();
    if (!t) return;
    const r = await fetch(`${API}/me/api-keys/${id}/revoke`, {
      method: "POST", headers: { Authorization: `Bearer ${t}` },
    });
    if (r.ok) { toast.success("Clé révoquée"); load(); }
    else toast.error("Échec révocation");
  }

  async function copyKey() {
    if (!revealed) return;
    await navigator.clipboard.writeText(revealed.plain);
    setCopied(true);
    toast.success("Clé copiée");
    setTimeout(() => setCopied(false), 2000);
  }

  const active = keys.filter(k => !k.revoked_at);
  const revoked = keys.filter(k => k.revoked_at);

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center gap-2 mb-2">
          <Key className="w-5 h-5 text-ink-700" />
          <h2 className="text-lg font-semibold text-ink-900">Clés API</h2>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          Accédez à FinSight en programmation via <code className="bg-ink-100 px-1 rounded text-2xs font-mono">POST /api/v1/analyze/*</code>.
          Authentification : header <code className="bg-ink-100 px-1 rounded text-2xs font-mono">X-API-Key: fsk_...</code>.
          Doc OpenAPI : <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="text-navy-500 underline">/docs</a>.
        </p>

        {revealed && (
          <div className="bg-amber-50 border border-amber-300 rounded-md p-4 mb-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-900 mb-2">
              <AlertTriangle className="w-4 h-4" />
              Nouvelle clé — copiez-la maintenant, elle ne sera plus jamais affichée.
            </div>
            <div className="flex gap-2">
              <input readOnly value={revealed.plain}
                className="flex-1 px-3 py-2 border border-amber-400 rounded-md text-xs font-mono bg-white" />
              <button onClick={copyKey} className="px-3 py-2 rounded-md border border-amber-400 bg-white hover:bg-amber-100">
                {copied ? <Check className="w-4 h-4 text-signal-buy" /> : <Copy className="w-4 h-4" />}
              </button>
              <button onClick={() => setRevealed(null)} className="px-3 py-2 rounded-md bg-amber-800 text-white text-xs">
                J&apos;ai copié
              </button>
            </div>
          </div>
        )}

        {/* Create */}
        <div className="bg-white border border-ink-200 rounded-md p-4 mb-6">
          <div className="text-sm font-semibold text-ink-900 mb-3">Créer une nouvelle clé</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input type="text" value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Ex : Prod backend"
              className="px-3 py-2 border border-ink-300 rounded-md text-sm focus:outline-none focus:border-navy-500" />
            <div>
              <label className="block text-2xs uppercase text-ink-500 mb-1">Req/min</label>
              <input type="number" value={rateMin} onChange={(e) => setRateMin(Number(e.target.value))}
                className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm" />
            </div>
            <div>
              <label className="block text-2xs uppercase text-ink-500 mb-1">Req/jour</label>
              <input type="number" value={rateDay} onChange={(e) => setRateDay(Number(e.target.value))}
                className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm" />
            </div>
          </div>
          <button onClick={create} disabled={creating} className="mt-3 flex items-center gap-1.5 px-4 py-2 rounded-md bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 disabled:opacity-50">
            <Plus className="w-3.5 h-3.5" /> {creating ? "Création…" : "Créer la clé"}
          </button>
        </div>

        {/* Active keys */}
        {loading ? (
          <div className="text-sm text-ink-500">Chargement…</div>
        ) : active.length === 0 ? (
          <div className="rounded-md border border-dashed border-ink-300 p-6 text-center text-sm text-ink-500">
            Aucune clé active. Créez-en une ci-dessus.
          </div>
        ) : (
          <div className="border border-ink-200 rounded-md divide-y divide-ink-100 bg-white">
            {active.map((k) => (
              <div key={k.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink-900">{k.name}</div>
                  <div className="text-xs text-ink-500 mt-0.5 flex items-center gap-2 flex-wrap font-mono">
                    <span>{k.key_prefix}••••••••</span>
                    <span>·</span>
                    <span>{k.rate_limit_per_min}/min</span>
                    <span>·</span>
                    <span>{k.rate_limit_per_day}/jour</span>
                    {k.last_used_at && <><span>·</span><span>utilisée {new Date(k.last_used_at).toLocaleDateString("fr-FR")}</span></>}
                  </div>
                </div>
                <button onClick={() => revoke(k.id)} className="p-1.5 rounded hover:bg-red-50 text-signal-sell" title="Révoquer">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {revoked.length > 0 && (
          <details className="mt-6">
            <summary className="text-xs text-ink-500 cursor-pointer hover:text-ink-700">
              Clés révoquées ({revoked.length})
            </summary>
            <div className="mt-2 border border-ink-200 rounded-md divide-y divide-ink-100 bg-ink-50/50">
              {revoked.map((k) => (
                <div key={k.id} className="px-4 py-2 text-xs text-ink-500">
                  <span className="font-mono">{k.key_prefix}</span> · {k.name} · révoquée {new Date(k.revoked_at!).toLocaleDateString("fr-FR")}
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      <section className="border-t border-ink-200 pt-6">
        <h3 className="text-base font-semibold text-ink-900 mb-3">Exemple d&apos;appel</h3>
        <pre className="bg-ink-900 text-ink-100 text-xs p-4 rounded-md overflow-x-auto font-mono leading-relaxed">{`curl -X POST ${API || "https://api.finsight-ia.com"}/api/v1/analyze/societe \\
  -H "X-API-Key: fsk_votrecleici..." \\
  -H "Content-Type: application/json" \\
  -d '{"ticker": "AAPL", "language": "fr", "currency": "EUR"}'`}</pre>
      </section>
    </div>
  );
}
