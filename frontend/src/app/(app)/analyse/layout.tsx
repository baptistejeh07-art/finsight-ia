import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analyse en cours",
  robots: { index: false, follow: false },
};

export default function AnalyseLayout({ children }: { children: React.ReactNode }) {
  return children;
}
