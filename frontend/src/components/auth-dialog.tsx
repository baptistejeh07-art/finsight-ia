"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";

type Mode = "signin" | "signup";

interface Props {
  mode: Mode;
  onClose: () => void;
  onModeChange: (mode: Mode) => void;
}

export function AuthDialog({ mode, onClose, onModeChange }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cguAccepted, setCguAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const supabase = createClient();

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleGoogle() {
    setLoading(true);
    try {
      // Persiste l'origine pour redirect post-OAuth (le callback lit ce param)
      const next = typeof window !== "undefined" ? window.location.pathname : "/app";
      const redirectTo =
        typeof window !== "undefined"
          ? `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`
          : undefined;
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo,
          queryParams: { access_type: "offline", prompt: "consent" },
        },
      });
      if (error) throw error;
      // Redirect par Supabase vers Google ; on ne reset pas loading ici
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur OAuth";
      toast.error(msg);
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Email et mot de passe requis");
      return;
    }
    if (mode === "signup") {
      if (password.length < 6) {
        toast.error("Mot de passe trop court (min. 6 caractères)");
        return;
      }
      if (!cguAccepted) {
        toast.error("Vous devez accepter les CGU");
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        toast.success("Compte créé. Bienvenue !");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        toast.success("Connexion réussie");
      }
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      // Traduit les messages courants
      let label = msg;
      if (msg.toLowerCase().includes("invalid login")) label = "Email ou mot de passe incorrect";
      else if (msg.toLowerCase().includes("already registered")) label = "Cet email est déjà inscrit";
      else if (msg.toLowerCase().includes("password")) label = "Mot de passe trop faible (min. 6 caractères)";
      toast.error(label);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-2xl w-full max-w-md mx-4 p-6 animate-slide-up relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 p-1 rounded hover:bg-ink-100 transition-colors"
          aria-label="Fermer"
        >
          <X className="w-4 h-4 text-ink-600" />
        </button>

        {/* Logo */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 mb-1">
            <svg className="w-6 h-6" viewBox="0 0 32 32" fill="none">
              <rect x="3" y="20" width="6" height="9" fill="#1B2A4A" />
              <rect x="11" y="14" width="6" height="15" fill="#1B2A4A" />
              <rect x="19" y="6" width="6" height="23" fill="#1B2A4A" />
            </svg>
            <span className="font-bold text-base tracking-wider">FINSIGHT</span>
          </div>
          <h2 className="text-xl font-semibold text-ink-900 mt-3">
            {mode === "signin" ? "Se connecter" : "Créer un compte"}
          </h2>
        </div>

        {/* CGU au-dessus du form (Bloomberg-style) */}
        {mode === "signup" && (
          <p className="text-xs text-ink-600 leading-relaxed text-center mb-5 max-w-sm mx-auto">
            En continuant, j&apos;accepte que FinSight m&apos;envoie des informations sur ses produits.
            Je reconnais avoir lu la{" "}
            <a href="/privacy" className="underline text-ink-900 font-medium">
              Politique de confidentialité
            </a>{" "}
            et j&apos;accepte les{" "}
            <a href="/cgu" className="underline text-ink-900 font-medium">
              Conditions d&apos;utilisation
            </a>.
          </p>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            placeholder="vous@exemple.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            autoFocus
          />
          <input
            type="password"
            placeholder={mode === "signup" ? "Mot de passe (min. 6 caractères)" : "Mot de passe"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
          />
          {mode === "signup" && (
            <label className="flex items-start gap-2 text-xs text-ink-700 mt-2">
              <input
                type="checkbox"
                checked={cguAccepted}
                onChange={(e) => setCguAccepted(e.target.checked)}
                className="mt-0.5"
              />
              <span>J&apos;accepte les Conditions d&apos;utilisation et la Politique de confidentialité</span>
            </label>
          )}
          <button type="submit" className="btn-primary w-full mt-2" disabled={loading}>
            {loading ? "..." : mode === "signin" ? "Continuer" : "Créer mon compte"}
          </button>
        </form>

        {/* Séparateur "ou" */}
        <div className="flex items-center my-5 text-2xs uppercase tracking-widest text-ink-400">
          <div className="flex-1 h-px bg-ink-200" />
          <span className="px-3">ou</span>
          <div className="flex-1 h-px bg-ink-200" />
        </div>

        {/* Bouton Google OAuth */}
        <button
          type="button"
          onClick={handleGoogle}
          disabled={loading}
          className="w-full inline-flex items-center justify-center gap-2.5 px-4 py-2 border border-ink-300 rounded-md text-sm text-ink-900 bg-white hover:bg-ink-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {loading ? "Redirection…" : "Continuer avec Google"}
        </button>

        {/* Switch mode */}
        <div className="text-center text-sm text-ink-600 mt-5">
          {mode === "signin" ? (
            <>
              Pas encore de compte ?{" "}
              <button
                type="button"
                onClick={() => onModeChange("signup")}
                className="text-ink-900 font-medium underline"
              >
                Créer un compte
              </button>
            </>
          ) : (
            <>
              Déjà un compte ?{" "}
              <button
                type="button"
                onClick={() => onModeChange("signin")}
                className="text-ink-900 font-medium underline"
              >
                Se connecter
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
