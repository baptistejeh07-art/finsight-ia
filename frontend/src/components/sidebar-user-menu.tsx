"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/i18n/provider";
import {
  ChevronsUpDown,
  Settings,
  Info,
  LogOut,
  Shield,
  Mail,
  LogIn,
  UserPlus,
} from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";
import { AuthDialog } from "./auth-dialog";

/**
 * Menu utilisateur en bas de la sidebar (style ChatGPT / Claude).
 *
 * - Bouton pied de sidebar : avatar initiale + nom/email + ⇅
 * - Popup qui remonte au clic : Paramètres · Aide · En savoir plus · Déconnexion
 * - Hors session : bouton « Se connecter » uniquement
 */
export function SidebarUserMenu() {
  const { t } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [open, setOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup" | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const supabase = createClient();

  useEffect(() => {
    async function loadUserAndAdmin() {
      const { data } = await supabase.auth.getUser();
      setUser(data.user);
      if (data.user) {
        const { data: prefs } = await supabase
          .from("user_preferences")
          .select("is_admin")
          .eq("user_id", data.user.id)
          .single();
        setIsAdmin(!!prefs?.is_admin);
      } else {
        setIsAdmin(false);
      }
    }
    loadUserAndAdmin();
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null);
      if (!session?.user) setIsAdmin(false);
      else loadUserAndAdmin();
    });
    return () => sub.subscription.unsubscribe();
  }, [supabase]);

  // Click outside → close
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  async function handleLogout() {
    await supabase.auth.signOut();
    setUser(null);
    setOpen(false);
    window.location.href = "/";
  }

  if (!user) {
    return (
      <>
        <div ref={wrapperRef} className="relative border-t border-ink-100 dark:border-ink-700">
          {open && (
            <div
              className="absolute left-2 right-2 bottom-full mb-1 bg-white dark:bg-ink-900 border border-ink-200 dark:border-ink-700 rounded-md shadow-lg overflow-hidden z-50 animate-fade-in"
              role="menu"
            >
              <button
                type="button"
                onClick={() => { setAuthMode("signin"); setOpen(false); }}
                role="menuitem"
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-700 dark:text-ink-100 hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors"
              >
                <LogIn className="w-4 h-4" />
                {t("auth.login")}
              </button>
              <button
                type="button"
                onClick={() => { setAuthMode("signup"); setOpen(false); }}
                role="menuitem"
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-700 dark:text-ink-100 hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors"
              >
                <UserPlus className="w-4 h-4" />
                {t("auth.signup")}
              </button>
              <MenuItem
                href="/contact"
                icon={<Mail className="w-4 h-4" />}
                label={t("nav.contact")}
                onNavigate={() => setOpen(false)}
              />
              <MenuItem
                href="/methodologie"
                icon={<Info className="w-4 h-4" />}
                label={t("nav.learn_more")}
                onNavigate={() => setOpen(false)}
              />
            </div>
          )}

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="w-full flex items-center gap-2.5 px-3 py-3 hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors"
          >
            <span className="shrink-0 w-8 h-8 rounded-full bg-navy-500 text-white font-semibold text-sm flex items-center justify-center">
              ?
            </span>
            <span className="flex-1 text-left overflow-hidden">
              <span className="block text-sm font-medium text-ink-900 dark:text-ink-50 truncate">
                {t("auth.login")}
              </span>
              <span className="block text-[11px] text-ink-500 dark:text-ink-400 truncate">
                {t("nav.contact")}
              </span>
            </span>
            <ChevronsUpDown className="w-3.5 h-3.5 text-ink-400 shrink-0" />
          </button>
        </div>
        {authMode && (
          <AuthDialog
            mode={authMode}
            onClose={() => setAuthMode(null)}
            onModeChange={setAuthMode}
          />
        )}
      </>
    );
  }

  const email = user.email || "";
  const displayName = email.split("@")[0] || "Compte";
  const initial = (displayName[0] || "?").toUpperCase();

  return (
    <div ref={wrapperRef} className="relative border-t border-ink-100">
      {open && (
        <div
          className="absolute left-2 right-2 bottom-full mb-1 bg-white border border-ink-200 rounded-md shadow-lg overflow-hidden z-50 animate-fade-in"
          role="menu"
        >
          {/* Email en tête */}
          <div className="px-3 py-2 border-b border-ink-100 text-xs text-ink-500 truncate">
            {email}
          </div>

          {isAdmin && (
            <MenuItem
              href="/admin"
              icon={<Shield className="w-4 h-4 text-navy-500" />}
              label="Admin Dashboard"
              onNavigate={() => setOpen(false)}
            />
          )}

          <MenuItem
            href="/parametres"
            icon={<Settings className="w-4 h-4" />}
            label={t("common.settings")}
            onNavigate={() => setOpen(false)}
          />
          <MenuItem
            href="/methodologie"
            icon={<Info className="w-4 h-4" />}
            label={t("nav.learn_more")}
            onNavigate={() => setOpen(false)}
          />
          <MenuItem
            href="/contact"
            icon={<Mail className="w-4 h-4" />}
            label={t("nav.contact")}
            onNavigate={() => setOpen(false)}
          />

          <div className="border-t border-ink-100">
            <button
              type="button"
              onClick={handleLogout}
              role="menuitem"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-50 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              {t("nav.sign_out")}
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 px-3 py-3 hover:bg-ink-50 transition-colors"
      >
        <span className="shrink-0 w-8 h-8 rounded-full bg-navy-500 text-white font-semibold text-sm flex items-center justify-center">
          {initial}
        </span>
        <span className="flex-1 text-left overflow-hidden">
          <span className="block text-sm font-medium text-ink-900 truncate">
            {displayName}
          </span>
          <span className="block text-[11px] text-ink-500 truncate">
            {email}
          </span>
        </span>
        <ChevronsUpDown className="w-3.5 h-3.5 text-ink-400 shrink-0" />
      </button>
    </div>
  );
}

function MenuItem({
  href,
  icon,
  label,
  onNavigate,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  onNavigate: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      role="menuitem"
      className="flex items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-50 transition-colors"
    >
      {icon}
      {label}
    </Link>
  );
}
