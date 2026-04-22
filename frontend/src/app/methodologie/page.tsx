import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { MethodologySidebar } from "@/components/marketing/methodology-sidebar";
import { PipelineDiagram } from "@/components/marketing/pipeline-diagram";

export const metadata: Metadata = {
  title: "Méthodologie",
  description:
    "Documentation technique FinSight IA : pipeline LangGraph, sources de données, formules du Score FinSight, protocole de backtest walk-forward, limites assumées, infrastructure.",
};

export default function MethodologiePage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        {/* Header */}
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="label-vitrine mb-5">Documentation technique</div>
            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              Comment FinSight produit ses analyses.
            </h1>
            <p className="text-lg text-text-secondary leading-relaxed">
              Aucun chiffre n&apos;est inventé. Chaque calcul est déterministe. Chaque commentaire IA est cadré par
              une constitution écrite et vérifié par des agents observateurs. Cette page documente l&apos;intégralité du
              pipeline, des sources de données jusqu&apos;à la production des livrables, sans angles morts.
            </p>
          </div>
        </section>

        {/* Layout avec sidebar sticky */}
        <div className="container-vitrine py-16 md:py-20 max-w-7xl">
          <div className="flex gap-12">
            <MethodologySidebar />

            <div className="flex-1 min-w-0 space-y-20">

              {/* ───────────────────────────── 01 · Pipeline ───────────────────────────── */}
              <section id="pipeline" className="scroll-mt-24">
                <div className="label-vitrine mb-3">01 · Architecture du pipeline</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Dix nœuds orchestrés par LangGraph.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Le pipeline est implémenté avec <code className="text-sm font-mono bg-surface-muted px-1.5 py-0.5 rounded">LangGraph 0.6</code>,
                  une machine à états dirigée par un graphe. Chaque nœud est une fonction pure typée qui lit un état
                  partagé <code className="text-sm font-mono bg-surface-muted px-1.5 py-0.5 rounded">FinSightState</code>,
                  produit un diff, et transmet au suivant. Les transitions conditionnelles permettent la tolérance
                  aux pannes (fallback sources, retry LLM, court-circuit sur sortie invalide).
                </p>

                <div className="bg-white border border-border-default rounded-lg p-6 mb-6">
                  <PipelineDiagram />
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Détail des dix nœuds</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Nœud</th>
                        <th className="text-left px-3 py-2 font-semibold">Agent</th>
                        <th className="text-left px-3 py-2 font-semibold">Rôle</th>
                        <th className="text-left px-3 py-2 font-semibold">Sortie clé</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default">
                      {[
                        ["fetch_node",      "AgentData",      "Récupère les données multi-sources (yfinance, Finnhub, FMP, Pappers, INPI, BODACC) et les normalise dans un DataSnapshot.", "snapshot"],
                        ["fallback_node",   "AgentData (dégradé)", "Déclenché si fetch primaire échoue. Réessaie avec les backups et signale la dégradation dans les méta-données.", "snapshot (partial)"],
                        ["quant_node",      "AgentQuant",     "Calcule les ratios déterministes (P/E, EV/EBITDA, ROE, Altman Z, Piotroski F, Beneish M, WACC, DCF Monte Carlo).", "ratios + dcf_result"],
                        ["synthesis_node",  "AgentSynthese",  "Appelle un LLM (Groq Llama 3.3 → Mistral → Anthropic Haiku en cascade) pour produire recommandation, conviction, targets bear/base/bull, thèse, catalyseurs.", "synthesis"],
                        ["synthesis_retry", "AgentSynthese",  "Retry si la sortie JSON est invalide ou si les garde-fous (price-anchor, conviction clamp) détectent une incohérence.", "synthesis (retry)"],
                        ["qa_node",         "AgentQAPython + AgentQAHaiku", "Double contrôle qualité : Python vérifie les règles déterministes (ratios cohérents, targets dans borne, conviction dans [0.25, 0.90]). Haiku relit le texte pour détecter les claims non étayés.", "qa_result + flags"],
                        ["devil_node",      "AgentDevil",     "Devil's Advocate — génère une thèse inverse et calcule un conviction_delta (écart entre synthèse et thèse inverse).", "devil_result"],
                        ["entry_zone_node", "AgentEntryZone", "Calcule le signal d'entrée : écart DCF Base vs cours, momentum, sentiment FinBERT. Retourne une zone entry favorable/neutre/défavorable.", "entry_zone"],
                        ["output_node",     "Writers",        "Appelle ExcelWriter, PPTXWriter, PDFWriter, BriefingWriter en parallèle. Produit les 4 livrables téléchargeables.", "files[]"],
                        ["blocked_node",    "(court-circuit)", "Si synthesis_node échoue trois fois, bascule ici pour produire un livrable partiel plutôt que crasher.", "fallback output"],
                      ].map(([node, agent, role, output]) => (
                        <tr key={node} className="align-top">
                          <td className="px-3 py-2.5 font-mono text-xs text-text-primary font-semibold">{node}</td>
                          <td className="px-3 py-2.5 text-text-primary whitespace-nowrap">{agent}</td>
                          <td className="px-3 py-2.5 text-text-secondary leading-relaxed">{role}</td>
                          <td className="px-3 py-2.5 font-mono text-xs text-text-tertiary">{output}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <p className="text-sm text-text-secondary leading-relaxed mt-6 italic">
                  Chaque nœud est wrappé dans un tracer qui logge latence, succès/erreur, provider LLM utilisé, et
                  score de data quality dans Supabase (table <code className="font-mono bg-surface-muted px-1 rounded">analysis_log</code>).
                  Temps médian pipeline bout en bout sur société cotée&nbsp;: 45 secondes.
                </p>
              </section>

              {/* ───────────────────────────── 02 · Gouvernance IA ───────────────────────────── */}
              <section id="gouvernance" className="scroll-mt-24">
                <div className="label-vitrine mb-3">02 · Gouvernance IA</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Constitution, agents observateurs, cascade LLM.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Un LLM non cadré hallucine, contredit les chiffres, surpromet. La production chez FinSight repose
                  sur trois dispositifs complémentaires&nbsp;: une constitution écrite, une cascade de fallback
                  entre providers, et quatre agents observateurs qui auditent chaque sortie.
                </p>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Constitution — 7 articles</h3>
                <div className="border border-border-default rounded-lg overflow-hidden mb-6">
                  <table className="w-full text-sm border-collapse">
                    <tbody className="divide-y divide-border-default">
                      {[
                        ["Article 1", "Traçabilité absolue", "Tout chiffre cité dans un commentaire IA doit figurer dans DataSnapshot ou être dérivé par quant_node. Pas d'invention."],
                        ["Article 2", "Price-anchor",        "Les targets base/bull/bear doivent être dans [cours × 0,65 ; cours × 1,35]. Hors zone → retry ou rejet."],
                        ["Article 3", "Conviction bornée",   "La conviction est forcée dans [0,25 ; 0,90]. En-deçà de 0,25 = erreur LLM reconstruite depuis recommandation + data_quality."],
                        ["Article 4", "Budget mots strict",  "Chaque champ de sortie a un budget de mots (ex: thesis = 3 phrases × 12-18 mots). Dépassement = troncature contrôlée."],
                        ["Article 5", "Typographie FR",      "Accents complets exigés (é è ê à ç ô), apostrophes droites, pas de points de suspension. restore_accents.py post-traite."],
                        ["Article 6", "Spécificité secteur", "Interdiction de généralités applicables à n'importe quel secteur. Le contenu doit nommer des drivers propres."],
                        ["Article 7", "Honnêteté des limites", "Ne jamais prétendre qu'une analyse est infaillible. Afficher un disclaimer explicite en footer."],
                      ].map(([n, title, body]) => (
                        <tr key={n} className="align-top">
                          <td className="px-3 py-2.5 font-mono text-xs text-text-tertiary whitespace-nowrap">{n}</td>
                          <td className="px-3 py-2.5 font-semibold text-text-primary whitespace-nowrap">{title}</td>
                          <td className="px-3 py-2.5 text-text-secondary leading-relaxed">{body}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Quatre agents observateurs</h3>
                <p className="text-text-secondary text-sm leading-relaxed mb-4">
                  En plus du pipeline principal, quatre agents secondaires auditent la production selon leur angle
                  propre. Leurs sorties ne bloquent pas la livraison (pour ne pas casser l&apos;UX en cas de
                  faux-positif) mais alimentent un verdict compile dans la table{" "}
                  <code className="font-mono bg-surface-muted px-1 py-0.5 rounded text-xs">
                    sentinel_verdicts
                  </code>.
                </p>
                <div className="grid md:grid-cols-2 gap-4 mb-6">
                  {[
                    {
                      name: "AgentJustice",
                      role: "Contrôle la conformité à la constitution. Détecte les violations d'articles et les flag.",
                    },
                    {
                      name: "AgentEnquete",
                      role: "Vérifie les chiffres cités dans les commentaires contre DataSnapshot (non-invention).",
                    },
                    {
                      name: "AgentJournaliste",
                      role: "Évalue la lisibilité : structure, concision, absence de jargon gratuit, accroche.",
                    },
                    {
                      name: "AgentSociologue",
                      role: "Contrôle les biais socio-économiques et la neutralité politique des analyses.",
                    },
                  ].map((a) => (
                    <div key={a.name} className="border border-border-default rounded-lg p-4 bg-white">
                      <div className="font-mono text-sm font-semibold text-text-primary mb-1">{a.name}</div>
                      <div className="text-sm text-text-secondary leading-relaxed">{a.role}</div>
                    </div>
                  ))}
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Cascade LLM providers</h3>
                <p className="text-text-secondary text-sm leading-relaxed mb-4">
                  Aucun appel LLM ne dépend d&apos;un seul provider. Chaque call traverse une cascade
                  déterministe en cas d&apos;échec&nbsp;:
                </p>
                <div className="bg-surface-muted border border-border-default rounded-lg p-5 mb-4">
                  <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto">
{`1. Groq  → llama-3.3-70b-versatile      (principal, rapide, gratuit)
2. Mistral → mistral-small-latest        (fallback 1 — quota Groq saturé ou 401)
3. Anthropic → claude-haiku-4-5          (fallback 2 — synthèses sensibles)
4. Gemini → gemini-2.0-flash             (audit visuel PDF uniquement)

Critères de bascule :
- HTTP 5xx ou timeout > 30s  → provider suivant
- Quota journalier atteint    → provider suivant
- JSON output invalide 2 fois → synthesis_retry puis provider suivant
- Violation d'article de la constitution → rejet et logging`}
                  </pre>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Paramètres LLM</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Agent appelant</th>
                        <th className="text-left px-3 py-2 font-semibold">Température</th>
                        <th className="text-left px-3 py-2 font-semibold">Max tokens</th>
                        <th className="text-left px-3 py-2 font-semibold">Justification</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default">
                      {[
                        ["AgentSynthese",    "0.3", "2 200", "Créativité modérée pour varier la prose, mais structure imposée par JSON schema."],
                        ["AgentQAHaiku",     "0.1", "800",   "Audit strict, aucune créativité souhaitée."],
                        ["AgentDevil",       "0.6", "1 500", "Plus créatif pour explorer la thèse inverse."],
                        ["Writers sectoriels","0.25", "700", "Commentaires factuels à variabilité limitée."],
                        ["Gemini Vision",    "0.1", "1 500", "Audit visuel déterministe des PDF produits."],
                      ].map(([agent, temp, tokens, just]) => (
                        <tr key={agent} className="align-top">
                          <td className="px-3 py-2 font-mono text-xs text-text-primary">{agent}</td>
                          <td className="px-3 py-2 text-center font-mono text-xs text-text-secondary">{temp}</td>
                          <td className="px-3 py-2 text-center font-mono text-xs text-text-secondary">{tokens}</td>
                          <td className="px-3 py-2 text-text-secondary text-xs leading-relaxed">{just}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* ───────────────────────────── 03 · Sources ───────────────────────────── */}
              <section id="sources" className="scroll-mt-24">
                <div className="label-vitrine mb-3">03 · Sources de données</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Multi-sources avec cascade de fallback.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Aucune donnée financière n&apos;est générée ou estimée. Toutes proviennent de sources tierces
                  vérifiables, dans une logique de cascade avec fallback pour résister aux indisponibilités.
                </p>

                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Source</th>
                        <th className="text-left px-3 py-2 font-semibold">Type</th>
                        <th className="text-left px-3 py-2 font-semibold">Couverture</th>
                        <th className="text-left px-3 py-2 font-semibold">Usage FinSight</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default">
                      {[
                        ["yfinance",     "Cotations / fondamentaux", "Mondiale (cotées)",   "Source principale. Historique 5 ans, ratios LTM, dividendes."],
                        ["Finnhub",      "News / sentiment",         "Mondiale",            "10 articles ticker-spécifiques par analyse. FinBERT local calcule le sentiment."],
                        ["FMP",          "Fundamentals",             "Surtout US",          "Fallback si yfinance manque des champs. Free plan limité, 401/403 fréquents sur EU."],
                        ["FRED",         "Macro",                    "US principalement",   "Taux directeur, inflation, indice confiance, spread haut rendement."],
                        ["Pappers",      "Sociétés non cotées",      "France (3,5 M+ entreprises)", "Source principale PME. Bilans, dirigeants, K-Bis, liens capitalistiques."],
                        ["INPI RNE",     "Actes + comptes annuels",  "France",              "Complément Pappers. Dépôts de comptes officiels, statuts, évolutions."],
                        ["BODACC",       "Procédures collectives",   "France",              "Redressements, liquidations, radiations. Signal d'alerte solvabilité."],
                        ["DGCCRF",       "Sanctions LME",            "France",              "Amendes publiques pour retard de paiement > 60 jours (loi LME)."],
                        ["feedparser",   "RSS backup",               "Yahoo Finance",       "Backup news si Finnhub indisponible."],
                      ].map(([src, type, cov, usage]) => (
                        <tr key={src} className="align-top">
                          <td className="px-3 py-2.5 font-semibold text-text-primary">{src}</td>
                          <td className="px-3 py-2.5 text-text-secondary">{type}</td>
                          <td className="px-3 py-2.5 text-text-secondary">{cov}</td>
                          <td className="px-3 py-2.5 text-text-secondary leading-relaxed">{usage}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="bg-surface-muted border border-border-default rounded-lg p-5">
                  <h3 className="font-serif text-base font-semibold text-text-primary mb-2">Traçabilité</h3>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    Chaque valeur affichée dans un livrable est traçable à sa source. L&apos;objet{" "}
                    <code className="font-mono bg-white px-1 py-0.5 rounded text-xs">DataSnapshot.meta</code> contient
                    les timestamps de fetch, la source utilisée pour chaque champ, et un score de qualité des données
                    (confidence_score 0–100). Si la qualité descend sous 60, l&apos;analyse est marquée comme dégradée
                    dans le rapport.
                  </p>
                </div>
              </section>

              {/* ───────────────────────────── 04 · Score FinSight ───────────────────────────── */}
              <section id="score" className="scroll-mt-24">
                <div className="label-vitrine mb-3">04 · Score FinSight propriétaire</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Un score composite 4 dimensions, 5 profils investisseur.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Le Score FinSight v2 note chaque société de 0 à 100 sur quatre dimensions indépendantes, puis
                  agrège selon cinq profils investisseur différenciés. Les bornes sont calibrées sur les quartiles
                  réels observés par secteur (pas de bornes universelles qui désavantageraient systématiquement
                  certains secteurs).
                </p>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Les quatre dimensions</h3>
                <div className="grid md:grid-cols-2 gap-4 mb-6">
                  {[
                    {
                      name: "Qualité",
                      color: "bg-purple-50 border-purple-200 text-purple-900",
                      desc: "Piotroski F-Score (9 points), ROE, ROIC, marge EBITDA. Détecte la capacité à générer un return on capital supérieur au coût.",
                    },
                    {
                      name: "Valeur",
                      color: "bg-blue-50 border-blue-200 text-blue-900",
                      desc: "EV/EBITDA, P/E forward, P/B, FCF yield. Bornes calibrées par secteur (médianes et quartiles du même univers).",
                    },
                    {
                      name: "Momentum",
                      color: "bg-emerald-50 border-emerald-200 text-emerald-900",
                      desc: "Rendement 3/6/12 mois, écart vs MM200, sentiment FinBERT sur news récentes.",
                    },
                    {
                      name: "Risque (inversé)",
                      color: "bg-amber-50 border-amber-200 text-amber-900",
                      desc: "Altman Z, Beneish M, ND/EBITDA, volatilité 1Y, beta. Plus le score est haut, plus le risque est maîtrisé.",
                    },
                  ].map((d) => (
                    <div key={d.name} className={`rounded-lg border p-4 ${d.color}`}>
                      <div className="font-serif text-lg font-semibold mb-2">{d.name}</div>
                      <div className="text-sm leading-relaxed">{d.desc}</div>
                    </div>
                  ))}
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Pondération par profil</h3>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Profil</th>
                        <th className="text-center px-3 py-2 font-semibold">Qualité</th>
                        <th className="text-center px-3 py-2 font-semibold">Valeur</th>
                        <th className="text-center px-3 py-2 font-semibold">Momentum</th>
                        <th className="text-center px-3 py-2 font-semibold">Risque</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default font-mono text-xs">
                      {[
                        ["Conservateur LT",    "35%", "20%", "10%", "35%"],
                        ["Balanced (équilibré)", "25%", "25%", "25%", "25%"],
                        ["Growth agressif",    "15%", "10%", "50%", "25%"],
                        ["Value contrarian",   "20%", "50%", "10%", "20%"],
                        ["Income dividendes",  "25%", "30%", "15%", "30%"],
                      ].map(([name, ...weights]) => (
                        <tr key={name}>
                          <td className="px-3 py-2 font-sans font-semibold text-text-primary">{name}</td>
                          {weights.map((w, i) => (
                            <td key={i} className="px-3 py-2 text-center text-text-secondary">{w}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="bg-surface-muted border border-border-default rounded-lg p-5 mb-6">
                  <h3 className="font-serif text-base font-semibold text-text-primary mb-2">Formule composite</h3>
                  <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto">
{`composite = Σ (score_dim × weight_dim)   pour dim ∈ {Q, V, M, R}

recommendation = BUY  si composite ≥ 65
                HOLD si 40 ≤ composite < 65
                SELL si composite < 40

conviction = 0.55 + min(0.40, |composite − seuil| / 100)   puis clamp [0.30, 0.90]`}
                  </pre>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mt-8 mb-3">
                  Formules des indicateurs sous-jacents
                </h3>
                <p className="text-text-secondary text-sm leading-relaxed mb-4">
                  Chaque sous-score des quatre dimensions est construit à partir d&apos;indicateurs dont la formule
                  est documentée et calculée de façon déterministe (pas d&apos;estimation LLM).
                </p>

                <div className="space-y-4 mb-6">
                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">WACC — Weighted Average Cost of Capital</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`WACC = (E / V) × Re + (D / V) × Rd × (1 − Tc)

Re  = Rf + β_levered × ERP + prime taille + prime pays
β_levered = β_unlevered × (1 + (1 − Tc) × D/E)

Rf  : taux sans risque (OAT 10Y pour FR, Treasury 10Y pour US) via FRED
ERP : Equity Risk Premium (Damodaran annuel, 5,5 % par défaut sur US)
Tc  : taux d'IS (25 % FR, 21 % US)
D/E : leverage cible = médiane sectorielle (source Damodaran)`}
                    </pre>
                  </div>

                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">DCF — Discounted Cash Flow Monte Carlo</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`V0 = Σ(t=1..5) FCFt / (1+WACC)^t  +  TV / (1+WACC)^5

TV   = FCF5 × (1+g) / (WACC − g)        [Gordon terminal]
g    ∈ [1,5 % ; 2,5 %]                   [TGR borné, LT inflation]
FCFt = EBITDA_t × (1 − taux_réinvestissement)

Monte Carlo : 1 000 tirages
- Croissance revenue : Normale(μ_histo, σ_histo)
- Marge EBITDA       : Normale(μ_LTM, σ / 3)
- WACC               : Uniforme(WACC_base − 0,5 pt, WACC_base + 0,5 pt)

Output : distribution empirique V0 → percentiles bear(p10) / base(p50) / bull(p90)`}
                    </pre>
                  </div>

                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">Altman Z-Score</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`Z = 1,2 × (WC / TA) + 1,4 × (RE / TA) + 3,3 × (EBIT / TA)
  + 0,6 × (MC / TL) + 1,0 × (Ventes / TA)

WC : Working Capital (actif circulant − passif circulant)
RE : Retained Earnings (réserves + report à nouveau)
TA : Total Assets
TL : Total Liabilities
MC : Market Capitalisation (valeur boursière capitaux propres)

Zones :
- Z > 2,99   : zone saine (safe zone)
- 1,81 < Z < 2,99 : zone grise (ambiguë)
- Z < 1,81   : zone de détresse (distress zone, risque faillite)`}
                    </pre>
                  </div>

                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">Piotroski F-Score (9 critères binaires)</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`F = Σ(i=1..9) 1{critère i vrai}   →  F ∈ {0, 1, ..., 9}

Profitabilité (4 points) :
  1. Net Income > 0
  2. ROA > 0
  3. Operating Cash Flow > 0
  4. OCF > Net Income (qualité des bénéfices)

Levier / liquidité (3 points) :
  5. ND/EBITDA_t < ND/EBITDA_{t−1}    (désendettement)
  6. Current Ratio_t > Current Ratio_{t−1}   (liquidité en hausse)
  7. Pas d'émission nette d'actions

Efficience opérationnelle (2 points) :
  8. Marge brute en hausse vs t−1
  9. Asset Turnover en hausse vs t−1

Interprétation : F ≥ 7 = qualité fondamentale solide ;
                 F ≤ 3 = alerte sur la santé opérationnelle.`}
                    </pre>
                  </div>

                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">Beneish M-Score (8 facteurs)</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`M = −4,84 + 0,920·DSRI + 0,528·GMI + 0,404·AQI + 0,892·SGI
    + 0,115·DEPI − 0,172·SGAI + 4,679·TATA − 0,327·LVGI

DSRI : Days Sales Receivables Index
GMI  : Gross Margin Index
AQI  : Asset Quality Index
SGI  : Sales Growth Index
DEPI : Depreciation Index
SGAI : SG&A Index
TATA : Total Accruals to Total Assets
LVGI : Leverage Index

Seuil : M > −1,78 = probabilité élevée de manipulation comptable.`}
                    </pre>
                  </div>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mt-8 mb-3">
                  Pondérations internes par dimension
                </h3>
                <p className="text-text-secondary text-sm leading-relaxed mb-4">
                  Chaque dimension agrège plusieurs sous-indicateurs. Les pondérations sont fixées empiriquement
                  selon la littérature académique et testées par backtest&nbsp;:
                </p>

                <div className="grid md:grid-cols-2 gap-4 mb-6">
                  {[
                    {
                      name: "Quality (0–100)",
                      weights: [
                        ["Piotroski F-Score",    "35 %"],
                        ["ROIC",                 "25 %"],
                        ["ROE",                  "20 %"],
                        ["Marge EBITDA",         "20 %"],
                      ],
                    },
                    {
                      name: "Value (0–100)",
                      weights: [
                        ["EV/EBITDA vs médiane sect.", "35 %"],
                        ["P/E Forward",                "25 %"],
                        ["P/B",                        "20 %"],
                        ["FCF Yield",                  "20 %"],
                      ],
                    },
                    {
                      name: "Momentum (0–100)",
                      weights: [
                        ["Rendement 12 mois",       "30 %"],
                        ["Rendement 6 mois",        "25 %"],
                        ["Rendement 3 mois",        "20 %"],
                        ["Écart vs MM200",          "15 %"],
                        ["Sentiment FinBERT",       "10 %"],
                      ],
                    },
                    {
                      name: "Risque inversé (0–100)",
                      weights: [
                        ["Altman Z",            "30 %"],
                        ["ND/EBITDA",           "25 %"],
                        ["Beneish M",           "20 %"],
                        ["Volatilité 1Y",       "15 %"],
                        ["Beta",                "10 %"],
                      ],
                    },
                  ].map((d) => (
                    <div key={d.name} className="border border-border-default rounded-lg p-4 bg-white">
                      <div className="font-serif font-semibold text-text-primary mb-3">{d.name}</div>
                      <table className="w-full text-xs">
                        <tbody className="divide-y divide-border-default/50">
                          {d.weights.map(([item, w]) => (
                            <tr key={item}>
                              <td className="py-1.5 text-text-secondary">{item}</td>
                              <td className="py-1.5 text-right font-mono font-semibold text-text-primary">{w}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>

                <p className="text-sm text-text-secondary leading-relaxed italic">
                  Chaque sous-indicateur est normalisé 0–100 par rank-percentile intra-sectoriel (une société au
                  75e percentile de son secteur sur un critère obtient 75 points sur ce critère). Cette normalisation
                  neutralise les écarts structurels entre secteurs (ex&nbsp;: une marge de 10&nbsp;% est excellente
                  dans la distribution mais faible en tech).
                </p>

                <p className="text-sm text-text-secondary leading-relaxed italic mt-4">
                  Code source&nbsp;:{" "}
                  <code className="font-mono bg-surface-muted px-1 py-0.5 rounded">core/finsight_score_v2.py</code>{" "}
                  (compute_scores_v2 + recommend_all_profiles).
                </p>
              </section>

              {/* ───────────────────────────── 05 · Backtest ───────────────────────────── */}
              <section id="backtest" className="scroll-mt-24">
                <div className="label-vitrine mb-3">05 · Validation empirique</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Backtest walk-forward, benchmark intra-sectoriel.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-4">
                  Toute prétention commerciale sur la performance du Score FinSight s&apos;appuie sur un protocole
                  reproductible et documenté. Les chiffres ci-dessous sont issus du dataset parquet disponible dans{" "}
                  <code className="font-mono text-xs bg-surface-muted px-1 py-0.5 rounded">outputs/backtest/backtest_latest.json</code>
                  .
                </p>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Protocole</h3>
                <ul className="space-y-2 text-text-secondary leading-relaxed mb-6 list-disc list-inside">
                  <li>
                    <strong>Univers</strong>&nbsp;: 50 sociétés du top S&amp;P 100 par capitalisation, rebalancé
                    mensuellement sur 131 mois (juin 2015 → mars 2026).
                  </li>
                  <li>
                    <strong>Observation mensuelle</strong>&nbsp;: pour chaque ticker × mois, calcul du Score FinSight
                    v2 sur les quatre dimensions + application des cinq profils.
                  </li>
                  <li>
                    <strong>Forward return 12 mois</strong>&nbsp;: mesure du rendement total 12 mois après la date
                    d&apos;observation (dividendes réinvestis).
                  </li>
                  <li>
                    <strong>Benchmark</strong>&nbsp;: ETF sectoriel SPDR correspondant (XLK, XLV, XLF, XLY, XLC, XLI,
                    XLP, XLE, XLB, XLRE, XLU). Permet un alpha <em>intra-sectoriel</em>, plus juste qu&apos;un
                    benchmark SPY global.
                  </li>
                  <li>
                    <strong>Walk-forward</strong>&nbsp;: les bornes par quartile sectoriel utilisées pour le scoring
                    à la date <em>T</em> sont calibrées uniquement sur les observations <em>antérieures à T</em>{" "}
                    (pas de look-ahead bias).
                  </li>
                  <li>
                    <strong>Test statistique</strong>&nbsp;: t-stat de Student sur les excès de rendement des{" "}
                    observations filtrées BUY. Significativité à 95&nbsp;% requiert |t| &gt; 1,96.
                  </li>
                </ul>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">Résultats principaux</h3>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Profil</th>
                        <th className="text-center px-3 py-2 font-semibold">n BUY</th>
                        <th className="text-center px-3 py-2 font-semibold">Excès moyen</th>
                        <th className="text-center px-3 py-2 font-semibold">t-stat</th>
                        <th className="text-center px-3 py-2 font-semibold">Information Ratio</th>
                        <th className="text-center px-3 py-2 font-semibold">% positifs</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default font-mono text-xs">
                      {[
                        ["Balanced",         "57",  "+8,9 %",  "+2,10 ★★",  "+0,28", "74 %"],
                        ["Growth agressif",  "57",  "+6,1 %",  "+1,89 ★",   "+0,25", "77 %"],
                        ["Conservateur",     "220", "−2,6 %",  "−1,49",     "−0,10", "66 %"],
                        ["Value contrarian", "320", "−5,6 %",  "−4,15 ★★★", "−0,23", "63 %"],
                        ["Income dividendes","227", "−4,3 %",  "−2,33 ★★",  "−0,15", "64 %"],
                      ].map(([profile, n, excess, t, ir, pos]) => (
                        <tr key={profile}>
                          <td className="px-3 py-2 font-sans font-semibold text-text-primary">{profile}</td>
                          <td className="px-3 py-2 text-center text-text-secondary">{n}</td>
                          <td className="px-3 py-2 text-center text-text-primary font-semibold">{excess}</td>
                          <td className="px-3 py-2 text-center text-text-secondary">{t}</td>
                          <td className="px-3 py-2 text-center text-text-secondary">{ir}</td>
                          <td className="px-3 py-2 text-center text-text-secondary">{pos}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-xs text-text-secondary italic mt-2">
                    ★ = significatif à 90 %, ★★ = 95 %, ★★★ = 99 %.
                  </p>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mb-3">
                  Métriques de validation — formules
                </h3>
                <div className="space-y-4 mb-6">
                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">Information Ratio</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`IR = E[r_p − r_b] / σ(r_p − r_b)

r_p : rendement du portefeuille FinSight (obs BUY)
r_b : rendement du benchmark (ETF sectoriel correspondant)
E   : moyenne empirique de l'excès
σ   : écart-type de l'excès

IR > 0,5   : signal robuste
IR ∈ [0,2 ; 0,5] : signal exploitable avec rigueur
IR < 0,2   : bruit`}
                    </pre>
                  </div>

                  <div className="border border-border-default rounded-lg p-5 bg-white">
                    <div className="font-serif font-semibold text-text-primary mb-2">t-statistique de Student</div>
                    <pre className="text-xs font-mono text-text-primary leading-relaxed overflow-x-auto bg-surface-muted p-3 rounded">
{`t = x̄ / (s / √n)

x̄ : moyenne empirique de l'excès de rendement
s  : écart-type empirique de l'excès
n  : nombre d'observations BUY

Seuils (n ≥ 30, approx. Normale) :
- |t| > 1,65  → p < 0,10  (significatif à 90 %)
- |t| > 1,96  → p < 0,05  (significatif à 95 %)
- |t| > 2,58  → p < 0,01  (significatif à 99 %)

Exemple Balanced : t = 8,9 / (32 / √57) = +2,10  →  p ≈ 0,036`}
                    </pre>
                  </div>
                </div>

                <div className="bg-surface-muted border border-border-default rounded-lg p-5">
                  <h3 className="font-serif text-base font-semibold text-text-primary mb-2">Résultat par secteur</h3>
                  <p className="text-sm text-text-secondary leading-relaxed mb-3">
                    Les profils Value, Conservateur et Income sous-performent en absolu sur 2015-2025 (bull tech),
                    mais retrouvent leur signal sur les secteurs cycliques (Materials, Industrials, Financials)&nbsp;:
                  </p>
                  <ul className="space-y-1 text-sm text-text-secondary font-mono">
                    <li>Value contrarian / cycliques&nbsp;: <strong className="text-text-primary">+24,3 % d&apos;alpha</strong>, cohérent avec la littérature Fama-French</li>
                    <li>Conservateur LT / cycliques&nbsp;: <strong className="text-text-primary">+26,3 % d&apos;alpha</strong></li>
                    <li>Income dividendes / cycliques&nbsp;: <strong className="text-text-primary">+25,4 % d&apos;alpha</strong></li>
                  </ul>
                </div>
              </section>

              {/* ───────────────────────────── 06 · Limites ───────────────────────────── */}
              <section id="limites" className="scroll-mt-24">
                <div className="label-vitrine mb-3">06 · Limites et biais assumés</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Ce que ces chiffres ne disent pas.
                </h2>

                <div className="space-y-5">
                  {[
                    {
                      title: "Taille d'échantillon limitée",
                      body: "Pour les profils Balanced et Growth, n BUY = 57 observations. C'est à la limite basse d'une inférence statistique robuste. Le t-stat de +2,10 passe tout juste le seuil 95 %. Un jury rigoureux exigerait n ≥ 100.",
                    },
                    {
                      title: "Régime unique dominant",
                      body: "La fenêtre 2015-2025 est dominée par un bull tech majeur. Les profils Value, Conservateur et Income y sont structurellement désavantagés, ce qui est cohérent avec la littérature Fama-French mais ne prouve pas que le score fonctionne en régime value (2000-2006) ou en crise (2008-2009).",
                    },
                    {
                      title: "Bornes sectorielles calibrées post-hoc",
                      body: "Les quartiles sectoriels utilisés par le scoring sont observés sur les données actuelles. Même si le protocole walk-forward élimine l'essentiel du look-ahead, la structure des quartiles peut avoir légèrement dérivé sur 10 ans.",
                    },
                    {
                      title: "Facteurs v1.1 non historisables",
                      body: "Cinq facteurs (Beneish M complet, EPS revisions consensus, short interest historique, insider transactions, institutional flow) sont exclus du backtest car non disponibles via yfinance sur 10 ans. Le score backtesté est donc v1.0 simplifié, pas la version production.",
                    },
                    {
                      title: "Univers biaisé survivorship",
                      body: "Le top 100 S&P actuel exclut les sociétés défaillantes ou sorties de l'indice. Le vrai test devrait intégrer les disparues (Lehman, GE avant sa sortie, etc.). C'est corrigé dans la version premium avec souscription EODHD.",
                    },
                    {
                      title: "Frais de transaction ignorés",
                      body: "Les excès de rendement présentés sont bruts. En rebalancement mensuel, les frais de courtage (0,05 %-0,15 %) et l'impôt sur plus-value réduiraient l'alpha net de 1 à 2 points de pourcentage.",
                    },
                  ].map((item) => (
                    <div key={item.title} className="border-l-2 border-text-tertiary pl-4">
                      <h3 className="font-serif text-base font-semibold text-text-primary mb-1">{item.title}</h3>
                      <p className="text-sm text-text-secondary leading-relaxed">{item.body}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* ───────────────────────────── 07 · Profils sectoriels ───────────────────────────── */}
              <section id="profils" className="scroll-mt-24">
                <div className="label-vitrine mb-3">07 · Profils sectoriels adaptatifs</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Un scoring qui refuse l&apos;uniformité.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Appliquer les mêmes ratios (EV/EBITDA, P/E, Marge EBITDA) à une banque et à une foncière cotée
                  est une erreur grossière. Une banque n&apos;a pas d&apos;EBITDA significatif ; une REIT distribue
                  par construction 90&nbsp;% de son revenu locatif. FinSight détecte automatiquement le profil
                  sectoriel via <code className="font-mono text-xs bg-surface-muted px-1 py-0.5 rounded">detect_profile(sector, industry)</code>{" "}
                  et adapte ratios, modèle de valorisation et prompts LLM.
                </p>

                <div className="space-y-4">
                  {[
                    {
                      code: "STANDARD",
                      name: "Corporate générique",
                      model: "DCF Monte Carlo",
                      ratios: "EV/EBITDA, P/E, EV/Revenue, marges brute/EBITDA/nette, ROE, ROIC, Altman Z",
                      hint: "Ratios classiques. Mention FCF et qualité du bilan.",
                      coverage: "Tech, conso, healthcare, industrials, materials, comm. services",
                    },
                    {
                      code: "BANK",
                      name: "Banque commerciale",
                      model: "P/TBV + ROE vs coût du capital",
                      ratios: "P/TBV, ROE, ROTE, CET1, NPL, Cost/Income, NIM, Provisions",
                      hint: "Pas d'EBITDA. Revenue = NII + commissions + trading. Focus levier réglementaire (CET1 > 12 %), qualité actifs (NPL < 3 %), rentabilité capital (ROE > coût du capital 8-10 %).",
                      coverage: "Financial Services + industry contient « Bank »",
                    },
                    {
                      code: "INSURANCE",
                      name: "Assurance",
                      model: "Embedded Value / P/EV",
                      ratios: "P/EV, Combined Ratio, Loss Ratio, ROE, Solvency II, Investment Yield",
                      hint: "Revenue = Primes Brutes Acquises. EBITDA = Résultat opérationnel avant taxes. Combined Ratio < 100 % = souscription profitable. Gross margin ≈ (1 − Loss Ratio).",
                      coverage: "Financial Services + industry Insurance",
                    },
                    {
                      code: "REIT",
                      name: "Foncière cotée",
                      model: "NAV (Net Asset Value) + P/NAV",
                      ratios: "P/NAV, FFO/share, AFFO/share, Dividend Yield, Debt/Equity, Occupancy Rate, Cap Rate",
                      hint: "Revenue = Rental Income. EBITDA ≈ NOI (Net Operating Income). Marge NOI typique 70-90 %. Net margin souvent <10 % (dépréciations). Valorisation par NAV plutôt que DCF.",
                      coverage: "Real Estate + industry REIT",
                    },
                    {
                      code: "UTILITY",
                      name: "Utility régulée",
                      model: "RAB (Regulated Asset Base) × rendement réglementé",
                      ratios: "P/B, Regulated ROE, Dividend Yield, Debt/EBITDA, Payout Ratio",
                      hint: "Modèle économique = base d'actifs régulés rémunérée. Croissance liée aux CapEx autorisés par le régulateur. Dividende = variable clé pour l'investisseur.",
                      coverage: "Utilities (électricité, gaz, eau régulés)",
                    },
                    {
                      code: "OIL_GAS",
                      name: "E&P pétrole/gaz",
                      model: "NAV par réserves + sensibilité prix baril",
                      ratios: "EV/EBITDA, EV/Reserves, EV/Production, Free Cash Flow Breakeven Price, Debt/EBITDA",
                      hint: "Cyclicalité extrême tied au prix du baril. Valorisation inclut NAV des réserves P1 + P2. Break-even price FCF = indicateur clé (survie si prix brut < break-even).",
                      coverage: "Energy + industry E&P ou Integrated (hors downstream pur)",
                    },
                  ].map((p) => (
                    <div key={p.code} className="border border-border-default rounded-lg overflow-hidden bg-white">
                      <div className="px-5 py-3 border-b border-border-default bg-surface-muted flex items-center gap-3 flex-wrap">
                        <span className="font-mono text-sm font-bold text-text-primary">{p.code}</span>
                        <span className="font-serif text-base font-semibold text-text-primary">{p.name}</span>
                        <span className="text-xs text-text-tertiary ml-auto">{p.coverage}</span>
                      </div>
                      <div className="p-5 space-y-2.5 text-sm">
                        <div>
                          <span className="font-semibold text-text-primary">Modèle de valorisation&nbsp;:</span>{" "}
                          <span className="text-text-secondary">{p.model}</span>
                        </div>
                        <div>
                          <span className="font-semibold text-text-primary">Ratios sectoriels&nbsp;:</span>{" "}
                          <span className="text-text-secondary font-mono text-xs">{p.ratios}</span>
                        </div>
                        <div>
                          <span className="font-semibold text-text-primary">Hint LLM injecté&nbsp;:</span>{" "}
                          <span className="text-text-secondary italic">{p.hint}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <p className="text-sm text-text-secondary leading-relaxed mt-6 italic">
                  Code source&nbsp;:{" "}
                  <code className="font-mono bg-surface-muted px-1 py-0.5 rounded">core/sector_profiles.py</code>{" "}
                  (fonction detect_profile + dict _CONFIGS).
                </p>
              </section>

              {/* ───────────────────────────── 08 · Stack ───────────────────────────── */}
              <section id="stack" className="scroll-mt-24">
                <div className="label-vitrine mb-3">08 · Stack technique</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Infrastructure, langages, dépendances.
                </h2>

                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="font-serif text-base font-semibold text-text-primary mb-3">Back-end</h3>
                    <ul className="text-sm text-text-secondary space-y-1.5 leading-relaxed">
                      <li><strong>Python 3.14</strong> (langage principal)</li>
                      <li><strong>LangGraph 0.6</strong> — orchestration du pipeline</li>
                      <li><strong>yfinance</strong> — cotations et fondamentaux</li>
                      <li><strong>pandas / numpy / scipy</strong> — calculs quantitatifs</li>
                      <li><strong>ReportLab</strong> — génération PDF (9 pages par rapport)</li>
                      <li><strong>python-pptx</strong> — pitchbook PowerPoint (20 slides)</li>
                      <li><strong>openpyxl</strong> — modèle Excel financier (templates injectés)</li>
                      <li><strong>FinBERT</strong> (HuggingFace, local) — sentiment news</li>
                      <li><strong>FastAPI</strong> — backend HTTP (Railway)</li>
                    </ul>
                  </div>

                  <div>
                    <h3 className="font-serif text-base font-semibold text-text-primary mb-3">Front-end</h3>
                    <ul className="text-sm text-text-secondary space-y-1.5 leading-relaxed">
                      <li><strong>Next.js 14</strong> (App Router, Server Components)</li>
                      <li><strong>TypeScript 5</strong> — typage strict</li>
                      <li><strong>Recharts</strong> — 25 composants graphiques interactifs</li>
                      <li><strong>Tailwind CSS</strong> — design system</li>
                      <li><strong>react-grid-layout</strong> — grille drag &amp; drop modulable</li>
                    </ul>
                  </div>

                  <div>
                    <h3 className="font-serif text-base font-semibold text-text-primary mb-3">Providers LLM</h3>
                    <ul className="text-sm text-text-secondary space-y-1.5 leading-relaxed">
                      <li><strong>Groq</strong> — Llama 3.3 70B (principal, gratuit, rapide)</li>
                      <li><strong>Mistral</strong> — mistral-small-latest (fallback et audit)</li>
                      <li><strong>Anthropic</strong> — Claude Haiku 4.5 (fallback synthèse)</li>
                      <li><strong>Google</strong> — Gemini 2.0 Flash Vision (audit visuel PDF)</li>
                    </ul>
                  </div>

                  <div>
                    <h3 className="font-serif text-base font-semibold text-text-primary mb-3">Infrastructure</h3>
                    <ul className="text-sm text-text-secondary space-y-1.5 leading-relaxed">
                      <li><strong>Vercel</strong> — front-end (auto-deploy master)</li>
                      <li><strong>Railway</strong> — backend Python + FastAPI</li>
                      <li><strong>Supabase</strong> — base PostgreSQL + auth + storage</li>
                      <li><strong>Resend</strong> — emails transactionnels (DKIM signé)</li>
                      <li><strong>Namecheap</strong> — domaine finsight-ia.com</li>
                    </ul>
                  </div>
                </div>

                <h3 className="font-serif text-lg font-semibold text-text-primary mt-8 mb-3">
                  Volumétrie du code source
                </h3>
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-surface-muted border-b border-border-default">
                        <th className="text-left px-3 py-2 font-semibold">Composant</th>
                        <th className="text-left px-3 py-2 font-semibold">Rôle</th>
                        <th className="text-right px-3 py-2 font-semibold">Lignes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-default font-mono text-xs">
                      {[
                        ["outputs/",          "Writers PDF / PPTX / Excel / Briefing",  "46 846"],
                        ["core/",             "Pipeline, graph, scores, profils sectoriels", "17 372"],
                        ["agents/",           "7 agents du pipeline + observateurs",     "6 522"],
                        ["backend/",          "FastAPI + endpoints REST",                 "5 438"],
                        ["cli_analyze.py",    "Orchestration CLI (société / secteur / indice / PME / cmp)", "3 038"],
                        ["tools/",            "Audits, migrations, backtest, générateurs", "29 714"],
                        ["— Total Python",    "Back-end + outillage",                     "108 930"],
                        ["frontend/src/",     "Next.js 14 + TypeScript + composants dashboard", "27 093"],
                        ["— Total général",   "Python + TypeScript",                      "136 023"],
                      ].map(([name, role, lines], i) => {
                        const isTotal = String(name).startsWith("—");
                        return (
                          <tr key={i} className={isTotal ? "bg-surface-muted font-sans font-semibold" : ""}>
                            <td className="px-3 py-2 text-text-primary">{name}</td>
                            <td className="px-3 py-2 text-text-secondary font-sans text-xs">{role}</td>
                            <td className="px-3 py-2 text-right text-text-primary">{lines}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-text-secondary italic leading-relaxed">
                  Code source et historique des commits maintenus sur un dépôt Git privé (baptistejeh07-art/finsight-ia).
                  Environ 1 200 commits, rythme de release continu, déploiement automatique sur push vers master.
                </p>
              </section>

              {/* ───────────────────────────── 09 · Choix de conception ───────────────────────────── */}
              <section id="choix" className="scroll-mt-24">
                <div className="label-vitrine mb-3">09 · Choix de conception</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Pourquoi ces technologies, pas d&apos;autres.
                </h2>
                <p className="text-text-secondary leading-relaxed mb-6">
                  Chaque brique est un arbitrage assumé entre performance, coût, dépendances et maintenabilité.
                  Voici les principales décisions techniques et leur justification.
                </p>

                <div className="space-y-4">
                  {[
                    {
                      choice: "LangGraph plutôt que Celery, Airflow ou un orchestrateur maison",
                      why: "LangGraph exprime le pipeline comme un graphe typé avec état partagé, transitions conditionnelles natives et retry déclaratifs. Celery = file de tâches, pas un graphe. Airflow = lourd (DB + scheduler + workers) pour un pipeline court (45 s). LangGraph est compilé en statemachine légère, zéro service externe à maintenir.",
                    },
                    {
                      choice: "Groq en LLM principal (pas OpenAI / Anthropic)",
                      why: "Groq Llama 3.3 70B est gratuit dans la limite de 14 400 requêtes/jour et 3 à 5× plus rapide qu'OpenAI sur un prompt équivalent (inférence sur puces LPU propriétaires). Le coût total d'une analyse passe de ~0,15 € (OpenAI gpt-4o-mini) à 0 € (Groq). Anthropic Claude Haiku reste en fallback pour les cas où la qualité de synthèse financière doit primer.",
                    },
                    {
                      choice: "Monte Carlo DCF (1 000 tirages) plutôt qu'un DCF déterministe",
                      why: "Un DCF déterministe donne un prix cible unique qui surestime la précision. La distribution Monte Carlo sur croissance, marge et WACC produit naturellement les percentiles bear / base / bull (p10 / p50 / p90), bien plus honnête sur l'incertitude. Coût calcul : 200 ms vs 10 ms — négligeable face à la valeur informationnelle.",
                    },
                    {
                      choice: "Supabase plutôt que Firebase ou PostgreSQL managé classique",
                      why: "Supabase fournit PostgreSQL (vs NoSQL Firebase — trop limitant pour du reporting financier), Auth intégrée, Row Level Security déclarative en SQL (gestion multi-tenant simple), Storage pour les livrables PDF/PPTX, REST auto-généré. Coût gratuit jusqu'à 500 Mo, puis 25 € / mois. Hébergement UE (Frankfurt) = compatible RGPD sans DPA.",
                    },
                    {
                      choice: "Next.js 14 App Router plutôt que Pages Router ou Remix",
                      why: "App Router permet le Server Components, le streaming et le routing fichier-système avec layouts nested. La taille du bundle client est divisée par ~3 vs Pages Router pour les pages lourdes (dashboard). Remix = alternative viable mais Next.js a un écosystème Vercel intégré (deploy, analytics, edge functions).",
                    },
                    {
                      choice: "Recharts plutôt que D3.js, Chart.js ou Visx",
                      why: "Recharts est assez haut niveau pour produire 25 visualisations de qualité (ligne, bar, area, scatter, radar, composed, treemap) sans écrire de SVG manuel. D3.js = flexibilité maximum mais 10× plus de code. Chart.js = canvas = pas de tooltip React idiomatique. Visx = D3 repackagé, overkill. Recharts fait 95 % du job pour 10 % du code.",
                    },
                    {
                      choice: "FinBERT local plutôt qu'une API de sentiment (HuggingFace Inference, OpenAI)",
                      why: "FinBERT est un modèle BERT fine-tuné sur un corpus financier (Financial PhraseBank). Le télécharger une fois (440 Mo) et l'exécuter localement coûte 0 € par prédiction vs 0,0002 € par call HF Inference. Sur 10 articles × 100 analyses/jour = 1 000 inférences quotidiennes — gain annuel ≈ 75 €. Temps d'inférence local : 80 ms par article sur CPU.",
                    },
                    {
                      choice: "ReportLab + python-pptx + openpyxl plutôt qu'un service externe (PDFKit, Carbone)",
                      why: "Les livrables sont le cœur de la proposition de valeur. Un service tiers (Carbone, PDFKit) génère une dépendance critique dont les limites d'utilisation et la latence (300-800 ms par document) sont subies. ReportLab + python-pptx donnent un contrôle total sur la mise en page et tournent en local (120 ms par PDF de 9 pages, 200 ms par PPTX de 20 slides).",
                    },
                  ].map((c, i) => (
                    <div key={i} className="border border-border-default rounded-lg p-5 bg-white">
                      <h3 className="font-serif text-base font-semibold text-text-primary mb-2">{c.choice}</h3>
                      <p className="text-sm text-text-secondary leading-relaxed">{c.why}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* ───────────────────────────── 10 · Sécurité ───────────────────────────── */}
              <section id="securite" className="scroll-mt-24">
                <div className="label-vitrine mb-3">10 · Sécurité et RGPD</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Garanties opérationnelles.
                </h2>

                <ul className="space-y-3 text-sm text-text-secondary leading-relaxed">
                  <li>
                    <strong className="text-text-primary">Authentification</strong>&nbsp;: Supabase Auth avec
                    vérification email. Mots de passe hashés (bcrypt), pas d&apos;accès direct à la base par l&apos;équipe.
                  </li>
                  <li>
                    <strong className="text-text-primary">Isolation des données utilisateur</strong>&nbsp;: Row Level
                    Security (RLS) Supabase actif sur toutes les tables. Chaque utilisateur ne peut lire que ses
                    propres analyses.
                  </li>
                  <li>
                    <strong className="text-text-primary">Chiffrement en transit</strong>&nbsp;: TLS 1.3 imposé sur
                    tous les endpoints (front, back, Supabase). HSTS activé sur finsight-ia.com.
                  </li>
                  <li>
                    <strong className="text-text-primary">Chiffrement au repos</strong>&nbsp;: AES-256 sur Supabase
                    et Vercel (gestion managée).
                  </li>
                  <li>
                    <strong className="text-text-primary">Emails authentifiés</strong>&nbsp;: SPF + DKIM + DMARC via
                    Resend. Domaine expéditeur vérifié.
                  </li>
                  <li>
                    <strong className="text-text-primary">Pas de revente de données</strong>&nbsp;: les analyses des
                    utilisateurs ne sont ni partagées ni revendues. Un projet futur (« FinSight Trends ») agrégerait
                    des tendances anonymisées sur des données de type dataset uniquement avec consentement explicite
                    et granulaire.
                  </li>
                  <li>
                    <strong className="text-text-primary">Suppression de compte</strong>&nbsp;: effacement complet
                    sous 72h sur demande, incluant historique d&apos;analyses et logs applicatifs.
                  </li>
                  <li>
                    <strong className="text-text-primary">Hébergement UE</strong>&nbsp;: Vercel (Frankfurt), Supabase
                    (Francfort), Resend (Irlande). Aucun transfert hors UE pour les données utilisateur.
                  </li>
                </ul>
              </section>

              {/* ───────────────────────────── 11 · Roadmap ───────────────────────────── */}
              <section id="roadmap" className="scroll-mt-24">
                <div className="label-vitrine mb-3">11 · Roadmap scientifique</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary mb-6">
                  Ce qui est prévu pour renforcer la rigueur.
                </h2>

                <div className="space-y-5">
                  {[
                    {
                      phase: "Court terme (1-3 mois)",
                      items: [
                        "Score baromètre mauvais payeurs sur module PME (calcul DSO/DPO + agrégation DGCCRF + BODACC).",
                        "Intégration FEC (Fichier des Écritures Comptables) pour cabinets comptables.",
                        "Extension backtest à l'univers S&P 500 complet (500 tickers vs 50 actuels).",
                      ],
                    },
                    {
                      phase: "Moyen terme (3-6 mois)",
                      items: [
                        "Souscription EODHD All-In-One (25 ans de fundamentals mondiaux) pour backtest 2000-2025.",
                        "Couverture des régimes value (1999-2002, 2003-2007) et de la crise 2008-2009.",
                        "Calibration des bornes sectorielles sur l'univers complet, cross-validation temporelle.",
                      ],
                    },
                    {
                      phase: "Long terme (6-12 mois)",
                      items: [
                        "Publication d'un whitepaper institutionnel (20-30 pages) avec protocole, résultats, limites, review par tiers académique.",
                        "Partenariat recherche avec une école ou une université (sciences de gestion).",
                        "API Score FinSight publique avec metered billing — ouverture à des chercheurs pour validation indépendante.",
                      ],
                    },
                  ].map((p) => (
                    <div key={p.phase} className="border border-border-default rounded-lg p-5 bg-white">
                      <h3 className="font-serif text-base font-semibold text-text-primary mb-3">{p.phase}</h3>
                      <ul className="space-y-1.5 text-sm text-text-secondary list-disc list-inside leading-relaxed">
                        {p.items.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>

              {/* Fin — CTA */}
              <section className="border-t border-border-default pt-10">
                <div className="max-w-3xl">
                  <h3 className="font-serif text-xl font-semibold text-text-primary mb-3">
                    Une question technique, une contestation ?
                  </h3>
                  <p className="text-text-secondary leading-relaxed mb-4">
                    La documentation technique est maintenue en continu. Toute remarque sur la méthodologie,
                    demande de justification, ou signalement d&apos;une limite non listée est bienvenue.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <a
                      href="mailto:baptiste.jeh07@gmail.com"
                      className="inline-block px-5 py-2.5 rounded-md bg-text-primary text-white text-sm font-semibold hover:opacity-90 transition-opacity"
                    >
                      Écrire au fondateur
                    </a>
                    <Link
                      href="/app"
                      className="inline-block px-5 py-2.5 rounded-md border border-border-default text-text-primary text-sm font-semibold hover:bg-surface-muted transition-colors"
                    >
                      Essayer la plateforme
                    </Link>
                  </div>
                </div>
              </section>

            </div>
          </div>
        </div>
      </main>

      <MarketingFooter />
    </>
  );
}
