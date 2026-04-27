import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Mode strict pour catch les bugs React
  reactStrictMode: true,

  // Permet aux images Supabase d'être optimisées par Next/Image
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "ugmqiawmszffqgtvsghz.supabase.co",
        pathname: "/storage/v1/object/public/**",
      },
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com", // avatars Google
      },
    ],
  },

  // Redirections : les prospects tapent souvent /tarifs ou /pricing
  // directement. Sans cette redirection, ils atterrissent sur un 404 alors
  // que la grille tarifaire est l'ancre #tarification de la homepage.
  async redirects() {
    return [
      { source: "/tarifs",   destination: "/#tarification", permanent: false },
      { source: "/tarif",    destination: "/#tarification", permanent: false },
      { source: "/pricing",  destination: "/#tarification", permanent: false },
      { source: "/prix",     destination: "/#tarification", permanent: false },
      { source: "/plans",    destination: "/#tarification", permanent: false },
      { source: "/abonnement", destination: "/#tarification", permanent: false },
    ];
  },

  // Headers sécurité — CSP avec wildcards larges (audit 27/04 F6)
  // Bug 27/04 16h : mon CSP initial parsait NEXT_PUBLIC_SUPABASE_URL au build
  // mais l'host pouvait etre vide → connect-src casse → frontend ne peut
  // plus parler a Supabase → 401 sur tout. Fix : wildcards *.supabase.co
  // + *.up.railway.app au lieu d'hosts dynamiques.
  async headers() {
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://va.vercel-scripts.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "img-src 'self' data: blob: https: http:",
      "font-src 'self' data: https://fonts.gstatic.com",
      "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://*.up.railway.app https://api.stripe.com https://api.openai.com https://api.anthropic.com https://*.vercel-insights.com https://vitals.vercel-insights.com https://api.logo.dev",
      "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
      "upgrade-insecure-requests",
    ].join("; ");
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Content-Security-Policy", value: csp },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },

  // Audit perf 27/04 : remove console en prod (26 console.log/warn/error)
  compiler: {
    removeConsole: process.env.NODE_ENV === "production"
      ? { exclude: ["error"] }  // garde console.error pour Sentry
      : false,
  },

  // Variables d'env exposées au client (NEXT_PUBLIC_*)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
  },
};

export default nextConfig;
