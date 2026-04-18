"use client";

import { useState } from "react";
import { Plus, Minus } from "lucide-react";

interface QA {
  q: string;
  a: string;
}

const FAQ: QA[] = [
  {
    q: "Comment fonctionne la tarification de FinSight ?",
    a: "Quatre formules : un plan Découverte gratuit (3 analyses/mois), un plan Essentiel à 34,99 €/mois (20 analyses), un plan Pro à 44,99 €/mois (analyses + portraits d'entreprise) et des plans Équipe & Enterprise sur devis. Une API pay-per-use est également disponible à partir de 0,05 € par appel.",
  },
  {
    q: "Est-il possible d'utiliser FinSight gratuitement ?",
    a: "Oui. Le plan Découverte donne accès à 3 analyses société par mois, avec les trois livrables (PDF, PowerPoint, Excel) et la conversation Q&A. C'est suffisant pour évaluer la qualité avant de choisir un plan payant.",
  },
  {
    q: "Sur quelles sociétés FinSight peut-il produire des analyses ?",
    a: "Toute société cotée sur les principales places mondiales (NYSE, Nasdaq, Euronext, LSE, XETRA, etc.) — environ 50 000 tickers. Nous couvrons aussi les indices majeurs (CAC 40, S&P 500, Euro Stoxx 50…) et les analyses sectorielles. Les sociétés non cotées (via Pappers) arrivent au Q2 2026 sur le plan Pro.",
  },
  {
    q: "À quelle fréquence les données sont-elles mises à jour ?",
    a: "Les cours de bourse et fondamentaux financiers sont rafraîchis à chaque analyse à partir de yfinance, Finnhub et FMP. Les news sentiment sont récupérées en temps réel sur les flux Finnhub et RSS. Aucune donnée n'est mise en cache plus d'une heure côté serveur.",
  },
  {
    q: "Mes analyses sont-elles confidentielles ?",
    a: "Oui. Les analyses individuelles ne sont pas partagées et restent attachées à votre compte. Sur les plans Équipe et Enterprise, vous contrôlez les permissions au niveau utilisateur. Aucune donnée client n'est utilisée pour entraîner nos modèles.",
  },
  {
    q: "Quels moyens de paiement sont acceptés ?",
    a: "Cartes bancaires (Visa, Mastercard, Amex), prélèvement SEPA pour l'Europe et virement bancaire sur les plans Enterprise. La facturation est mensuelle ou annuelle (avec une remise sur l'annuel).",
  },
  {
    q: "Quelle est la fiabilité des analyses ?",
    a: "Le pipeline FinSight combine sept agents spécialisés : un agent données déterministe (DCF, ratios calculés, jamais inventés), un agent synthèse (LLM cadré par une constitution), un agent QA (vérifie les chiffres), un agent contradicteur (thèse inverse) et trois agents de gouvernance. Chaque chiffre est sourcé. Aucune analyse ne remplace votre jugement final.",
  },
  {
    q: "Puis-je intégrer FinSight à mes outils internes ?",
    a: "Oui. Notre API REST permet d'appeler les analyses depuis n'importe quel système, et les plans Enterprise incluent des connecteurs natifs (Pennylane, Sage, FEC pour la France). Documentation complète sur demande.",
  },
];

export function Faq() {
  return (
    <section className="bg-surface-muted border-t border-border-default">
      <div className="container-vitrine py-20 md:py-24 max-w-3xl">
        <h2 className="font-serif text-center text-3xl md:text-4xl font-bold text-text-primary tracking-tight mb-12">
          Questions fréquentes
        </h2>
        <div className="divide-y divide-border-default border-y border-border-default">
          {FAQ.map((qa, i) => (
            <FaqItem key={i} qa={qa} defaultOpen={i === 0} />
          ))}
        </div>
      </div>
    </section>
  );
}

function FaqItem({ qa, defaultOpen = false }: { qa: QA; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-5 text-left gap-6 hover:text-accent-primary transition-colors"
      >
        <span className="text-base font-medium text-text-primary">{qa.q}</span>
        {open ? (
          <Minus className="w-4 h-4 text-text-muted shrink-0" />
        ) : (
          <Plus className="w-4 h-4 text-text-muted shrink-0" />
        )}
      </button>
      {open && (
        <div className="pb-5 -mt-1 text-sm text-text-secondary leading-relaxed animate-fade-in">
          {qa.a}
        </div>
      )}
    </div>
  );
}
