import type { Metadata } from "next";
import { DM_Sans, DM_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { CookieBanner } from "@/components/cookie-banner";
import { PWAInstaller } from "@/components/pwa-installer";
import { VitrineVisitTracker } from "@/components/vitrine-visit-tracker";
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
    default: "FinSight IA — Votre propre analyste, où que vous soyez",
    template: "%s · FinSight IA",
  },
  description:
    "Analyses financières institutionnelles propulsées par l'IA. Sociétés cotées, secteurs, indices : DCF, ratios, scénarios, comparatifs. Rapports PDF, PPTX et Excel prêts pour comité d'investissement.",
  keywords: [
    "analyse financière",
    "DCF",
    "valuation",
    "IA",
    "fintech",
    "investissement",
    "bourse",
    "Bloomberg",
    "pitchbook",
  ],
  authors: [{ name: "FinSight IA" }],
  metadataBase: new URL("https://finsight-ia.com"),
  openGraph: {
    type: "website",
    locale: "fr_FR",
    url: "https://finsight-ia.com",
    siteName: "FinSight IA",
    title: "FinSight IA — Votre propre analyste, où que vous soyez",
    description:
      "Analyses financières de niveau institutionnel propulsées par l'IA.",
  },
  twitter: {
    card: "summary_large_image",
    title: "FinSight IA — Votre propre analyste, où que vous soyez",
    description:
      "DCF · Ratios · Scénarios · Comparatifs. Analyses institutionnelles en quelques minutes.",
  },
  robots: { index: true, follow: true },
  manifest: "/manifest.json",
  applicationName: "FinSight IA",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "FinSight",
    startupImage: [
      {
        url: "/apple-icon.png",
        media: "(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3)",
      },
    ],
  },
  formatDetection: {
    telephone: false,
  },
  other: {
    "mobile-web-app-capable": "yes",
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "apple-mobile-web-app-title": "FinSight",
    "msapplication-TileColor": "#1B2A4A",
    "msapplication-tap-highlight": "no",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#1B2A4A",
  // Window Controls Overlay : permet à la PWA d'afficher la barre de titre
  // native avec ses propres contrôles. Sensation "vrai logiciel".
  viewportFit: "cover",
};

const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('finsight-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = stored === 'dark' || stored === 'light' ? stored : (prefersDark ? 'dark' : 'light');
    if (theme === 'dark') document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" className={`${dmSans.variable} ${dmMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen antialiased bg-surface text-text-primary">
        <VitrineVisitTracker />
        {children}
        <PWAInstaller />
        <CookieBanner />
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "rgb(var(--accent-primary))",
              color: "rgb(var(--accent-primary-fg))",
              fontSize: "14px",
              borderRadius: "6px",
            },
          }}
        />
      </body>
    </html>
  );
}
