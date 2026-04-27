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

  // Headers sécurité — CSP minimal ajouté audit 27/04 (F6)
  // Empeche XSS depuis dangerouslySetInnerHTML (theme init script + QA chat).
  // connect-src whitelist : Supabase + backend Railway + Logo.dev images.
  // 'unsafe-inline' temporairement requis pour theme init + Tailwind JIT.
  // À durcir en V2 avec nonce-based CSP (next-safe-action ou middleware CSP).
  async headers() {
    const supabaseHost = (process.env.NEXT_PUBLIC_SUPABASE_URL || "")
      .replace(/^https?:\/\//, "");
    const apiHost = (process.env.NEXT_PUBLIC_API_URL || "")
      .replace(/^https?:\/\//, "");
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://*.supabase.co https://lh3.googleusercontent.com https://img.logo.dev https://logo.clearbit.com",
      "font-src 'self' data:",
      `connect-src 'self' https://${supabaseHost} wss://${supabaseHost} https://${apiHost} https://api.stripe.com https://*.vercel-insights.com`,
      "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
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
