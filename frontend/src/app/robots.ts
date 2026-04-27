import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Audit SEO 27/04/2026 — disallow routes auth-derriere :
        // - /app : dashboard logged-in
        // - /admin/* : back-office FinSight
        // - /resultats/* : pages d'analyse user (private, share via tokens)
        // - /parametres/* : preferences user
        // - /dashboard/* : dashboard user
        // Empeche Googlebot de crawler ces routes (perte signal SEO + flash UX)
        disallow: ["/app", "/admin", "/resultats", "/parametres", "/dashboard"],
      },
    ],
    sitemap: "https://finsight-ia.com/sitemap.xml",
  };
}
