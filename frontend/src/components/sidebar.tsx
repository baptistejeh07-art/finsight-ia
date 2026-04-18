"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  GitCompareArrows,
  LayoutDashboard,
  Package,
  Info,
  LogIn,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { AuthDialog } from "./auth-dialog";
import type { User } from "@supabase/supabase-js";

type NavItem = {
  label: string;
  href: string;
  icon: React.ReactNode;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Analyse", href: "/", icon: <BarChart3 className="w-4 h-4" /> },
  { label: "Comparatif", href: "/comparatif", icon: <GitCompareArrows className="w-4 h-4" /> },
  { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
  { label: "Livrables", href: "/#livrables", icon: <Package className="w-4 h-4" /> },
  { label: "À propos", href: "/about", icon: <Info className="w-4 h-4" /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"signin" | "signup" | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    setUser(null);
  }

  return (
    <>
      <aside className="hidden md:flex fixed left-0 top-0 h-screen w-56 flex-col bg-navy-500 text-white border-r border-navy-700 z-40">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center px-4 py-5 border-b border-navy-700">
          <Image
            src="/logo.png"
            alt="FinSight IA"
            width={140}
            height={50}
            priority
            className="object-contain"
          />
        </Link>

        {/* Nav */}
        <nav className="flex-1 px-2 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href.split("#")[0]) && item.href !== "/#livrables";
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-white/10 text-white font-medium"
                    : "text-white/70 hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Auth zone */}
        <div className="px-3 py-4 border-t border-navy-700 space-y-2">
          {user ? (
            <>
              <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-white/70">
                <UserIcon className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{user.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-white/70 hover:bg-white/5 hover:text-white transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Se déconnecter
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setAuthMode("signin")}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-white/80 hover:bg-white/5 hover:text-white transition-colors"
              >
                <LogIn className="w-3.5 h-3.5" />
                Se connecter
              </button>
              <button
                onClick={() => setAuthMode("signup")}
                className="w-full px-3 py-2 rounded-md text-xs font-medium bg-white text-navy-500 hover:bg-white/90 transition-colors"
              >
                S&apos;inscrire
              </button>
            </>
          )}
        </div>
      </aside>

      {authMode && (
        <AuthDialog mode={authMode} onClose={() => setAuthMode(null)} onModeChange={setAuthMode} />
      )}
    </>
  );
}
