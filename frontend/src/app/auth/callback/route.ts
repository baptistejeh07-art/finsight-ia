import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Callback OAuth Supabase.
 * - Récupère ?code=xxx renvoyé par le provider (Google)
 * - Échange le code contre une session côté serveur
 * - Set les cookies de session
 * - Redirige vers ?next ou /app par défaut
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") || "/app";
  const errorDescription = url.searchParams.get("error_description");

  // Provider a renvoyé une erreur
  if (errorDescription) {
    return NextResponse.redirect(
      new URL(`/?auth_error=${encodeURIComponent(errorDescription)}`, url.origin)
    );
  }

  if (!code) {
    return NextResponse.redirect(new URL("/?auth_error=missing_code", url.origin));
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(
      new URL(`/?auth_error=${encodeURIComponent(error.message)}`, url.origin)
    );
  }

  // OK : redirect vers la page d'origine ou /app
  // On force /app si next pointe vers la racine (vitrine) — mieux pour l'UX post-login
  const finalNext = next === "/" ? "/app" : next;
  return NextResponse.redirect(new URL(finalNext, url.origin));
}
