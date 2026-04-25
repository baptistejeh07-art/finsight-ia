"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, Shield } from "lucide-react";

const TABS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/sales-agent", label: "Sales Agent" },
  { href: "/admin/monitoring", label: "Monitoring" },
  { href: "/admin/traces", label: "Traces" },
  { href: "/admin/errors", label: "Sentinelle" },
  { href: "/admin/trends", label: "Trends" },
];

export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();

  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/app");
    }
  }

  return (
    <div className="min-h-screen bg-[#FAFAF5] dark:bg-ink-950 text-ink-900 dark:text-ink-50">
      <div className="max-w-7xl mx-auto px-6 md:px-10 py-8 md:py-12">
        <button
          type="button"
          onClick={goBack}
          className="inline-flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-900 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </button>

        <h1
          className="text-3xl md:text-4xl font-semibold text-ink-900 dark:text-ink-50 mb-8 md:mb-12 tracking-tight flex items-center gap-3"
          style={{ fontFamily: "'Copernicus', 'Libre Caslon Text', Georgia, serif" }}
        >
          <Shield className="w-7 h-7 text-navy-500" />
          Admin
        </h1>

        <div className="flex flex-col md:flex-row gap-6 md:gap-12">
          <aside className="w-full md:w-52 shrink-0">
            <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible">
              {TABS.map((t) => {
                const active =
                  pathname === t.href ||
                  (t.href !== "/admin" && pathname?.startsWith(t.href));
                return (
                  <Link
                    key={t.href}
                    href={t.href}
                    className={
                      "px-3 py-2 rounded-md text-sm font-semibold transition-colors whitespace-nowrap " +
                      (active
                        ? "bg-ink-100 dark:bg-ink-800 text-ink-900 dark:text-ink-50"
                        : "text-ink-700 dark:text-ink-300 hover:bg-ink-100/50 dark:hover:bg-ink-800/60 hover:text-ink-900 dark:hover:text-ink-50")
                    }
                  >
                    {t.label}
                  </Link>
                );
              })}
            </nav>
          </aside>

          <div className="flex-1 min-w-0">{children}</div>
        </div>
      </div>
    </div>
  );
}
