import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Résultat d'analyse",
  robots: { index: false, follow: false },
};

export default function ResultatsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
