import { type NextRequest } from "next/server";
import { updateSession } from "./lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Match toutes les routes SAUF :
     * - _next/static (assets)
     * - _next/image (image optim)
     * - favicon.ico, robots.txt, sitemap.xml
     * - extensions images
     */
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
