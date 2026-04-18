"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { LogOut, User as UserIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { AuthDialog } from "./auth-dialog";
import type { User } from "@supabase/supabase-js";

export function Sidebar() {
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
      <aside className="hidden md:flex fixed left-0 top-0 h-screen w-56 flex-col bg-white text-ink-900 border-r border-ink-200 z-40">
        {/* Logo (volontairement blanc sur blanc — espace réservé identitaire) */}
        <Link href="/" className="flex items-center justify-center px-4 py-5">
          <Image
            src="/logo.png"
            alt="FinSight IA"
            width={140}
            height={50}
            priority
            className="object-contain opacity-0"
          />
        </Link>

        {/* Nav — uniquement Livrables */}
        <nav className="flex-1 px-3 py-4">
          <Link
            href="/#livrables"
            className="block px-3 py-2 text-sm font-medium text-ink-900 hover:text-navy-500 transition-colors"
          >
            Livrables
          </Link>
        </nav>

        {/* Auth zone */}
        <div className="px-3 py-4 border-t border-ink-200 space-y-2">
          {user ? (
            <>
              <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-ink-600">
                <UserIcon className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{user.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-900 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Se déconnecter
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setAuthMode("signin")}
                className="w-full px-3 py-2 rounded-md text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-900 transition-colors text-left"
              >
                Se connecter
              </button>
              <button
                onClick={() => setAuthMode("signup")}
                className="w-full px-3 py-2 rounded-md text-xs font-medium bg-navy-500 text-white hover:bg-navy-600 transition-colors"
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
