"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { AuthDialog } from "./auth-dialog";
import type { User } from "@supabase/supabase-js";

export function TopNav() {
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

  return (
    <>
      <div className="hidden md:flex fixed top-0 right-0 z-30 px-6 py-4 items-center gap-5 text-xs">
        {/* Connecté : menu utilisateur géré dans la sidebar (SidebarUserMenu).
            Ici on ne laisse que les boutons auth quand non-connecté. */}
        {!user && (
          <>
            <button
              onClick={() => setAuthMode("signin")}
              className="text-ink-700 hover:text-ink-900 transition-colors"
            >
              Se connecter
            </button>
            <button
              onClick={() => setAuthMode("signup")}
              className="text-ink-700 hover:text-ink-900 transition-colors"
            >
              S&apos;inscrire
            </button>
          </>
        )}
        <Link
          href="/contact"
          className="text-ink-700 hover:text-ink-900 transition-colors"
        >
          Contact us
        </Link>
      </div>

      {authMode && (
        <AuthDialog mode={authMode} onClose={() => setAuthMode(null)} onModeChange={setAuthMode} />
      )}
    </>
  );
}
