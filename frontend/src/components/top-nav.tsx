"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { AuthDialog } from "./auth-dialog";
import type { User } from "@supabase/supabase-js";
import { useI18n } from "@/i18n/provider";

export function TopNav() {
  const { t } = useI18n();
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
        {!user && (
          <>
            <button
              onClick={() => setAuthMode("signin")}
              className="text-ink-700 hover:text-ink-900 transition-colors"
            >
              {t("auth.login")}
            </button>
            <button
              onClick={() => setAuthMode("signup")}
              className="text-ink-700 hover:text-ink-900 transition-colors"
            >
              {t("auth.signup")}
            </button>
          </>
        )}
        <Link
          href="/contact"
          className="text-ink-700 hover:text-ink-900 transition-colors"
        >
          {t("nav.contact")}
        </Link>
      </div>

      {authMode && (
        <AuthDialog mode={authMode} onClose={() => setAuthMode(null)} onModeChange={setAuthMode} />
      )}
    </>
  );
}
