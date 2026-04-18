import type { Metadata } from "next";
import Link from "next/link";
import {
  Database,
  Cpu,
  ShieldCheck,
  Sparkles,
  GitBranch,
  FileCheck,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Méthodologie",
  description:
    "Comment FinSight produit ses analyses financières : pipeline 7 agents, sources de données, calcul DCF/WACC, gouvernance constitutionnelle, garanties d'auditabilité.",
};

export default function MethodologiePage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        {/* Header */}
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Méthodologie</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              Comment FinSight produit ses analyses.
            </h1>
            <p className="text-lg text-text-secondary leading-relaxed">
              Aucun chiffre n&apos;est inventé. Chaque calcul est déterministe.
              Chaque commentaire IA est cadré par une constitution écrite et
              vérifié par quatre agents observateurs. Cette page documente
              l&apos;intégralité du pipeline, sans angles morts.
            </p>
          </div>
        </section>

        {/* Pipeline */}
        <section className="border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-12">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">01 · Pipeline</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Sept agents, orchestrés par LangGraph.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Chaque analyse FinSight est exécutée par un graphe d&apos;agents
                  spécialisés défini avec LangGraph. Le graphe est
                  déterministe : les mêmes inputs produisent strictement la même
                  séquence d&apos;appels. Chaque nœud écrit son résultat dans un
                  state Pydantic typé, lu par les nœuds suivants.
                </p>
                <p>
                  La séparation des responsabilités est stricte : l&apos;agent
                  Données ne calcule rien. L&apos;agent Calculs n&apos;invente
                  rien. L&apos;agent Synthèse ne touche pas aux chiffres. Cette
                  séparation est notre première garantie d&apos;auditabilité.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <AgentCard
                icon={<Database className="w-4 h-4" />}
                num="01"
                title="AgentData"
                desc="Récupère les fondamentaux et le marché. Multi-sources avec fallback. Normalisation Pydantic."
              />
              <AgentCard
                icon={<Cpu className="w-4 h-4" />}
                num="02"
                title="AgentQuant"
                desc="Calcule WACC, DCF, ratios, scénarios. Code Python pur, jamais le LLM. Tests unitaires sur les formules."
              />
              <AgentCard
                icon={<Sparkles className="w-4 h-4" />}
                num="03"
                title="AgentSynthese"
                desc="Commentaire éditorial via LLM (Groq llama-3.3-70b, fallback Anthropic Haiku 4.5). Cadré par la constitution."
              />
              <AgentCard
                icon={<FileCheck className="w-4 h-4" />}
                num="04"
                title="AgentQA"
                desc="Vérifications croisées : cohérence chiffres ↔ commentaires, signaux contradictoires, hallucinations."
              />
              <AgentCard
                icon={<AlertTriangle className="w-4 h-4" />}
                num="05"
                title="AgentDevil"
                desc="Thèse inverse systématique. Ajuste la conviction finale. Sceptique permanent."
              />
              <AgentCard
                icon={<ShieldCheck className="w-4 h-4" />}
                num="06"
                title="Gouvernance"
                desc="Quatre agents observateurs vérifient le respect de la constitution V2. Verdict ALERTES si violation."
              />
            </div>
          </div>
        </section>

        {/* Données */}
        <section className="bg-surface-muted border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">02 · Sources de données</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Multi-providers, fallback systématique.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Aucune analyse ne dépend d&apos;une seule source. Une coupure
                  yfinance, un quota Finnhub atteint, un free plan FMP qui rend
                  un 401 : le pipeline bascule automatiquement sur la source
                  suivante sans interrompre l&apos;analyse. Toutes les données
                  sont rafraîchies à la demande, jamais mises en cache plus
                  d&apos;une heure côté serveur.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-border-default rounded-lg overflow-hidden bg-surface-elevated">
                <thead>
                  <tr className="bg-surface-muted border-b border-border-default">
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Domaine
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Source principale
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Fallback
                    </th>
                    <th className="text-left text-2xs uppercase tracking-widest text-text-muted font-semibold py-3 px-4">
                      Profondeur
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {[
                    ["Cours et market data", "yfinance", "Finnhub", "5 ans"],
                    ["Fondamentaux (P&L, BS, CF)", "yfinance", "FMP", "5 ans"],
                    ["Ratios et multiples", "Calculs internes", "—", "Année LTM + 4 ans"],
                    ["News société", "Finnhub", "Yahoo RSS", "10 articles récents"],
                    ["Sentiment news", "FinBERT (local)", "—", "Temps réel"],
                    ["Indices & secteurs", "yfinance", "Sectorial mapping interne", "Tous indices majeurs"],
                  ].map(([domain, primary, fallback, depth]) => (
                    <tr key={domain} className="hover:bg-surface-muted/50">
                      <td className="py-3 px-4 text-text-primary font-medium">{domain}</td>
                      <td className="py-3 px-4 text-text-secondary">{primary}</td>
                      <td className="py-3 px-4 text-text-muted">{fallback}</td>
                      <td className="py-3 px-4 text-text-muted">{depth}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-6 text-sm text-text-muted leading-relaxed">
              Les données livrées par les sources tierces sont normalisées par
              FinSight (devises, conversions GBp/GBP, retraitement des
              exceptionnels). Aucune analyse n&apos;est lancée si les
              fondamentaux essentiels manquent : nous préférons refuser une
              analyse plutôt que livrer une analyse incomplète.
            </p>
          </div>
        </section>

        {/* DCF */}
        <section className="border-b border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">03 · Valorisation DCF</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  La méthode, sans boîte noire.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Le DCF FinSight suit la méthode standard Damodaran/McKinsey,
                  appliquée systématiquement avec les mêmes hypothèses pour
                  garantir la comparabilité entre analyses.
                </p>
                <ol className="space-y-3 mt-4">
                  {[
                    [
                      "WACC",
                      "Coût des fonds propres via CAPM (Rf = taux 10 ans US, ERP propre à FinSight, beta yfinance), coût de la dette à partir de la note implicite ou taux moyen historique. Pondération valeur de marché.",
                    ],
                    [
                      "Free Cash Flows projetés",
                      "Période explicite de 5 ans, croissance dérivée de la moyenne 3 ans glissante, plafonnée à 15 % et plancher 0 %. Marges convergentes vers la moyenne sectorielle.",
                    ],
                    [
                      "Valeur terminale",
                      "Modèle de Gordon avec g = 2 % (croissance long terme alignée inflation cible BCE/Fed). Sensibilité au taux g ± 1 % systématique.",
                    ],
                    [
                      "Equity bridge",
                      "Enterprise Value − dette nette + minoritaires + investissements financiers. Conversion en cours par action sur capital fully diluted.",
                    ],
                    [
                      "Sensibilités",
                      "Tableau WACC × g de 5×5, avec mise en évidence du cours actuel et du cours cible. Toujours dans le pitchbook.",
                    ],
                  ].map(([title, desc], i) => (
                    <li key={i} className="flex gap-4">
                      <span className="w-7 h-7 rounded-full bg-accent-primary/10 text-accent-primary text-xs font-semibold flex items-center justify-center shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <div>
                        <div className="text-text-primary font-medium">{title}</div>
                        <div className="text-sm text-text-muted leading-relaxed mt-1">
                          {desc}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        </section>

        {/* Constitution */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="text-xs font-semibold tracking-widest uppercase text-white mb-3">
                  04 · Gouvernance constitutionnelle
                </div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold leading-tight">
                  Sept articles. Aucun écart toléré.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-5 text-text-inverse/80 leading-relaxed">
                <p>
                  Les LLM hallucinent. Pour empêcher cela en analyse financière
                  — où une erreur peut coûter cher — nous avons rédigé une
                  constitution stricte que chaque agent doit respecter. Quatre
                  agents observateurs vérifient en post-traitement le respect
                  des sept articles et émettent un verdict (PASS / ALERTES /
                  BLOCKED).
                </p>
                <ul className="space-y-3 mt-2">
                  {[
                    "Article 1 : aucun chiffre généré par le LLM. Tous les nombres viennent du state quant.",
                    "Article 2 : toute affirmation doit être sourçable (donnée, calcul ou littérature de référence).",
                    "Article 3 : la conviction est explicitement bornée [0, 1] et justifiée.",
                    "Article 4 : le devil's advocate ne peut pas être ignoré ; il ajuste la conviction finale.",
                    "Article 5 : aucun conseil personnalisé d'investissement, jamais.",
                    "Article 6 : les biais ESG, géopolitiques ou idéologiques sont explicitement déclarés.",
                    "Article 7 : tout écart à la constitution déclenche une alerte tracée dans le state.",
                  ].map((art, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <GitBranch className="w-3.5 h-3.5 text-text-inverse/60 shrink-0 mt-1" />
                      <span className="text-sm">{art}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Garanties */}
        <section>
          <div className="container-vitrine py-16 md:py-20 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">05 · Garanties d&apos;auditabilité</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                  Tout est tracé.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Pour chaque analyse, FinSight conserve : le state Pydantic
                  intégral du pipeline (entrées, calculs, sorties intermédiaires),
                  les prompts envoyés aux LLM, les hashes des modèles utilisés,
                  les versions des sources de données et le verdict des agents
                  de gouvernance. Une analyse peut être rejouée à
                  l&apos;identique six mois plus tard à partir du seul state
                  archivé.
                </p>
                <p>
                  Sur les plans Enterprise, ce log complet est exposé en API
                  pour permettre à votre équipe conformité de mener ses propres
                  audits internes. La méthodologie est versionnée comme du code
                  : chaque modification de la constitution ou d&apos;une formule
                  est documentée dans le changelog public.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="bg-surface-muted border-t border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-3xl text-center">
            <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary tracking-tight mb-3">
              Une question méthodologique ?
            </h2>
            <p className="text-text-muted mb-7">
              Notre assistant connaît FinSight de bout en bout, ou contactez-nous
              directement.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link href="/analyste" className="btn-cta">
                Discuter avec FinSight
                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Link>
              <Link href="/contact" className="btn-outline">
                Nous contacter
              </Link>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function AgentCard({
  icon,
  num,
  title,
  desc,
}: {
  icon: React.ReactNode;
  num: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="card-vitrine">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-9 h-9 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center">
          {icon}
        </span>
        <div className="text-2xs uppercase tracking-widest text-text-muted">
          Agent {num}
        </div>
      </div>
      <div className="text-sm font-semibold text-text-primary">{title}</div>
      <div className="text-xs text-text-muted mt-1.5 leading-relaxed">{desc}</div>
    </div>
  );
}
