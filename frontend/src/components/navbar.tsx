"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LogOut, User as UserIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { AuthDialog } from "./auth-dialog";
import type { User } from "@supabase/supabase-js";

export function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"signin" | "signup" | null>(null);
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, [supabase]);

  async function handleLogout() {
    await supabase.auth.signOut();
    setUser(null);
  }

  return (
    <>
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-ink-200">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <Logo className="w-7 h-7" />
            <span className="font-bold text-base tracking-wider text-ink-900">
              FINSIGHT
            </span>
            <span className="text-2xs font-mono text-ink-500 ml-1 hidden md:inline">
              IA
            </span>
          </Link>

          {/* Nav center (desktop) */}
          <nav className="hidden md:flex items-center gap-6">
            <Link
              href="/"
              className="text-sm text-ink-700 hover:text-ink-900 transition-colors"
            >
              Analyse
            </Link>
            {user && (
              <Link
                href="/dashboard"
                className="text-sm text-ink-700 hover:text-ink-900 transition-colors"
              >
                Dashboard
              </Link>
            )}
            <Link
              href="/about"
              className="text-sm text-ink-700 hover:text-ink-900 transition-colors"
            >
              À propos
            </Link>
          </nav>

          {/* Auth actions */}
          <div className="flex items-center gap-2">
            {user ? (
              <UserMenu user={user} onLogout={handleLogout} />
            ) : (
              <>
                <button
                  onClick={() => setAuthMode("signin")}
                  className="btn-secondary !py-1.5 !px-3"
                >
                  Se connecter
                </button>
                <button
                  onClick={() => setAuthMode("signup")}
                  className="btn-primary !py-1.5 !px-3"
                >
                  S&apos;inscrire
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {authMode && (
        <AuthDialog mode={authMode} onClose={() => setAuthMode(null)} onModeChange={setAuthMode} />
      )}
    </>
  );
}

function UserMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-ink-100 transition-colors"
      >
        <UserIcon className="w-4 h-4 text-ink-600" />
        <span className="text-sm text-ink-900 hidden sm:inline">
          {user.email?.split("@")[0]}
        </span>
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1 w-56 bg-white border border-ink-200 rounded-md shadow-lg overflow-hidden animate-fade-in"
          onMouseLeave={() => setOpen(false)}
        >
          <div className="px-3 py-2 border-b border-ink-100">
            <div className="text-2xs text-ink-500 uppercase tracking-wider">
              Connecté
            </div>
            <div className="text-sm font-medium text-ink-900 truncate">
              {user.email}
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-50 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}

function Logo({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Pictogramme barres montantes */}
      <rect x="3" y="20" width="6" height="9" fill="#1B2A4A" />
      <rect x="11" y="14" width="6" height="15" fill="#1B2A4A" />
      <rect x="19" y="6" width="6" height="23" fill="#1B2A4A" />
    </svg>
  );
}
