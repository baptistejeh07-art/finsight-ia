import type { Metadata } from "next";
import { DM_Sans, DM_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  display: "swap",
});

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FinSight IA — Plateforme d'analyse financière institutionnelle",
    template: "%s · FinSight IA",
  },
  description:
    "Analyses financières institutionnelles propulsées par l'IA. Sociétés cotées, secteurs, indices : DCF, ratios, scénarios, comparatifs. Rapports PDF/PPTX/Excel pro.",
  keywords: [
    "analyse financière",
    "DCF",
    "valuation",
    "IA",
    "fintech",
    "investissement",
    "bourse",
    "Bloomberg",
  ],
  authors: [{ name: "FinSight IA" }],
  metadataBase: new URL("https://finsight-ia.com"),
  openGraph: {
    type: "website",
    locale: "fr_FR",
    url: "https://finsight-ia.com",
    siteName: "FinSight IA",
    title: "FinSight IA — Plateforme d'analyse financière institutionnelle",
    description: "Analyses financières institutionnelles propulsées par l'IA.",
  },
  twitter: {
    card: "summary_large_image",
    title: "FinSight IA — Plateforme d'analyse financière institutionnelle",
    description: "DCF · Ratios · Scénarios · Comparatifs. Analyses institutionnelles en 2 minutes.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" className={`${dmSans.variable} ${dmMono.variable}`}>
      <body className="min-h-screen antialiased">
        <Sidebar />
        <div className="md:pl-56 min-h-screen">{children}</div>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#1B2A4A",
              color: "#fff",
              fontSize: "14px",
              borderRadius: "6px",
            },
          }}
        />
      </body>
    </html>
  );
}
