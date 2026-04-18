import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Comparatif société",
  description:
    "Comparer deux sociétés cotées en parallèle. DCF, ratios, multiples, verdict relatif. Livrables PDF + PPTX + Excel.",
};

export default function ComparatifLayout({ children }: { children: React.ReactNode }) {
  return children;
}
