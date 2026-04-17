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

  // Headers sécurité
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },

  // Variables d'env exposées au client (NEXT_PUBLIC_*)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
  },
};

export default nextConfig;
