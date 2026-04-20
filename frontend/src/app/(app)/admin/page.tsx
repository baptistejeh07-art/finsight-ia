"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  BarChart3, Users, Activity, TrendingUp, TrendingDown, Minus,
  Ban, CheckCircle2, RefreshCw, Shield, DollarSign, Globe2,
} from "lucide-react";
import toast from "react-hot-toast";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface AdminStats {
  analyses: {
    day: number; week: number; month: number; total: number;
    by_kind: Record<string, number>;
    by_recommendation: Record<string, number>;
    top_tickers_30d: Array<{ ticker: string; company_name: string | null; count: number }>;
  };
  users: { total: number; banned: number; active: number };
  revenues: { mrr_eur: number; arr_eur: number; note: string };
  generated_at: string;
}

interface UserRow {
  user_id: string;
  email: string | null;
  created_at: string | null;
  is_admin: boolean;
  banned_at: string | null;
  banned_reason: string | null;
}

export default function AdminDashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  async function getToken(): Promise<string | null> {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  }

  async function checkAdmin() {
    const supabase = createClient();
    const { data } = await supabase.auth.getUser();
    if (!data.user) { router.push("/"); return; }
    const { data: prefs } = await supabase
      .from("user_preferences")
      .select("is_admin")
      .eq("user_id", data.user.id)
      .single();
    const admin = !!prefs?.is_admin;
    setIsAdmin(admin);
    if (!admin) router.push("/app");
    return admin;
  }

  async function loadStats() {
    const token = await getToken();
    if (!token) return;
    try {
      const r = await fetch(`${API}/admin/stats`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) setStats(await r.json());
      else toast.error(`Erreur stats: ${r.status}`);
    } catch (e) { toast.error(`Erreur réseau`); }
  }

  async function loadUsers() {
    const token = await getToken();
    if (!token) return;
    try {
      const r = await fetch(`${API}/admin/users?limit=200`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) {
        const j = await r.json();
        setUsers(j.users || []);
      }
    } catch {}
  }

  useEffect(() => {
    (async () => {
      const admin = await checkAdmin();
      if (admin) {
        await Promise.all([loadStats(), loadUsers()]);
      }
      setLoading(false);
    })();
  }, []);

  async function banUser(userId: string) {
    const reason = prompt("Raison du bannissement ?");
    if (reason === null) return;
    const token = await getToken();
    const r = await fetch(`${API}/admin/ban`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, reason }),
    });
    if (r.ok) { toast.success("Utilisateur banni"); loadUsers(); loadStats(); }
    else toast.error("Échec ban");
  }

  async function unbanUser(userId: string) {
    const token = await getToken();
    const r = await fetch(`${API}/admin/unban`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (r.ok) { toast.success("Utilisateur débanni"); loadUsers(); loadStats(); }
    else toast.error("Échec unban");
  }

  if (loading) {
    return <div className="p-8 text-sm text-ink-500">Chargement…</div>;
  }

  if (!isAdmin) {
    return <div className="p-8 text-sm text-signal-sell">Accès admin uniquement.</div>;
  }

  const RECO_COLORS = {
    BUY: "text-signal-buy bg-signal-buy/10",
    HOLD: "text-amber-600 bg-amber-500/10",
    SELL: "text-signal-sell bg-signal-sell/10",
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            <Shield className="w-3 h-3" />
            Admin Console
          </div>
          <h1 className="text-2xl font-bold text-ink-900">Dashboard FinSight</h1>
        </div>
        <button
          onClick={() => { loadStats(); loadUsers(); }}
          className="flex items-center gap-1.5 text-xs text-ink-600 hover:text-ink-900 border border-ink-200 rounded px-3 py-1.5"
        >
          <RefreshCw className="w-3 h-3" />
          Rafraîchir
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard icon={<Activity className="w-4 h-4" />} label="Analyses aujourd'hui"
                 value={stats?.analyses.day ?? 0} />
        <KpiCard icon={<Activity className="w-4 h-4" />} label="Analyses 7j"
                 value={stats?.analyses.week ?? 0} />
        <KpiCard icon={<BarChart3 className="w-4 h-4" />} label="Analyses 30j"
                 value={stats?.analyses.month ?? 0} />
        <KpiCard icon={<Users className="w-4 h-4" />} label="Total analyses"
                 value={stats?.analyses.total ?? 0} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard icon={<Users className="w-4 h-4" />} label="Utilisateurs"
                 value={stats?.users.total ?? 0} />
        <KpiCard icon={<CheckCircle2 className="w-4 h-4 text-signal-buy" />} label="Actifs"
                 value={stats?.users.active ?? 0} />
        <KpiCard icon={<Ban className="w-4 h-4 text-signal-sell" />} label="Bannis"
                 value={stats?.users.banned ?? 0} />
        <KpiCard icon={<DollarSign className="w-4 h-4 text-amber-600" />} label="MRR (€)"
                 value={stats?.revenues.mrr_eur ?? 0}
                 suffix={stats?.revenues.note ? "—" : "€"}
                 hint={stats?.revenues.note} />
      </div>

      {/* Breakdown par kind + reco */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-white border border-ink-200 rounded-md p-5">
          <h2 className="text-sm font-semibold text-ink-900 mb-3 flex items-center gap-2">
            <Globe2 className="w-4 h-4" /> Analyses par type (30j)
          </h2>
          <div className="space-y-2">
            {Object.entries(stats?.analyses.by_kind || {}).sort((a, b) => b[1] - a[1]).map(([kind, n]) => (
              <div key={kind} className="flex items-center justify-between text-xs">
                <span className="text-ink-700 capitalize">{kind.replace("_", " ")}</span>
                <span className="font-mono font-semibold text-ink-900">{n}</span>
              </div>
            ))}
            {Object.keys(stats?.analyses.by_kind || {}).length === 0 && (
              <div className="text-xs text-ink-400 italic">Aucune analyse encore</div>
            )}
          </div>
        </section>

        <section className="bg-white border border-ink-200 rounded-md p-5">
          <h2 className="text-sm font-semibold text-ink-900 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Recommandations (30j)
          </h2>
          <div className="space-y-2">
            {Object.entries(stats?.analyses.by_recommendation || {}).map(([reco, n]) => (
              <div key={reco} className="flex items-center justify-between">
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${RECO_COLORS[reco as keyof typeof RECO_COLORS] || ""}`}>
                  {reco}
                </span>
                <span className="font-mono font-semibold text-ink-900">{n}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Top tickers */}
      <section className="bg-white border border-ink-200 rounded-md p-5">
        <h2 className="text-sm font-semibold text-ink-900 mb-3">Top 10 tickers analysés (30j)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
          {(stats?.analyses.top_tickers_30d || []).map((t, i) => (
            <div key={t.ticker} className="border border-ink-100 rounded p-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-ink-400 font-mono">#{i + 1}</span>
                <span className="text-xs font-mono font-bold text-navy-500">{t.ticker}</span>
              </div>
              {t.company_name && (
                <div className="text-[10px] text-ink-600 truncate">{t.company_name}</div>
              )}
              <div className="text-[10px] text-ink-500 mt-1">{t.count} analyses</div>
            </div>
          ))}
        </div>
      </section>

      {/* Users table */}
      <section className="bg-white border border-ink-200 rounded-md p-5">
        <h2 className="text-sm font-semibold text-ink-900 mb-3 flex items-center gap-2">
          <Users className="w-4 h-4" /> Utilisateurs ({users.length})
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-500 border-b border-ink-200">
                <th className="py-2">Email</th>
                <th className="py-2">Inscrit le</th>
                <th className="py-2">Rôle</th>
                <th className="py-2">Statut</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-ink-100">
                  <td className="py-2 text-ink-800">{u.email || <span className="text-ink-400 font-mono">{u.user_id.slice(0, 8)}…</span>}</td>
                  <td className="py-2 text-ink-500">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString("fr-FR") : "—"}
                  </td>
                  <td className="py-2">
                    {u.is_admin ? (
                      <span className="inline-flex items-center gap-1 text-[10px] bg-navy-50 text-navy-500 px-2 py-0.5 rounded">
                        <Shield className="w-2.5 h-2.5" /> Admin
                      </span>
                    ) : (
                      <span className="text-[10px] text-ink-500">User</span>
                    )}
                  </td>
                  <td className="py-2">
                    {u.banned_at ? (
                      <span className="inline-flex items-center gap-1 text-[10px] bg-signal-sell/10 text-signal-sell px-2 py-0.5 rounded">
                        <Ban className="w-2.5 h-2.5" /> Banni
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[10px] bg-signal-buy/10 text-signal-buy px-2 py-0.5 rounded">
                        Actif
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    {u.is_admin ? (
                      <span className="text-[10px] text-ink-400">—</span>
                    ) : u.banned_at ? (
                      <button onClick={() => unbanUser(u.user_id)}
                              className="text-[10px] text-signal-buy hover:underline">Débannir</button>
                    ) : (
                      <button onClick={() => banUser(u.user_id)}
                              className="text-[10px] text-signal-sell hover:underline">Bannir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Links */}
      <div className="flex gap-3 text-xs">
        <Link href="/admin/monitoring" className="text-navy-500 hover:underline">
          → Monitoring jobs
        </Link>
      </div>

      <div className="text-[10px] text-ink-400 text-right">
        Généré : {stats?.generated_at ? new Date(stats.generated_at).toLocaleString("fr-FR") : "—"}
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, suffix, hint }: {
  icon: React.ReactNode; label: string; value: number; suffix?: string; hint?: string;
}) {
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[1.2px] text-ink-500 mb-2">
        {icon}
        {label}
      </div>
      <div className="text-2xl font-bold text-ink-900 font-mono">
        {value.toLocaleString("fr-FR")} {suffix && <span className="text-sm text-ink-500">{suffix}</span>}
      </div>
      {hint && <div className="text-[10px] text-ink-400 mt-1 italic">{hint}</div>}
    </div>
  );
}
