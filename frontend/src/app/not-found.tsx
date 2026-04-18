import Link from "next/link";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata = { title: "Page introuvable" };

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-2xl mx-auto px-6 py-20 w-full text-center">
        <div className="section-label mb-3">Erreur 404</div>
        <h1 className="text-4xl font-bold text-ink-900 mb-3 tracking-tight">
          Page introuvable
        </h1>
        <p className="text-sm text-ink-600 mb-8 max-w-md mx-auto">
          La page que vous cherchez n&apos;existe pas ou a été déplacée.
          Revenez à l&apos;accueil pour lancer une nouvelle analyse.
        </p>
        <Link href="/" className="btn-primary inline-flex">
          Retour à l&apos;accueil
        </Link>
      </main>
      <Footer />
    </div>
  );
}
