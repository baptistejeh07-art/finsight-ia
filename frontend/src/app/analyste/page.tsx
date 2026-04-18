import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Database, Cpu, ShieldCheck, FileText, Presentation, FileSpreadsheet, Sparkles } from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { AnalysteChat } from "@/components/marketing/analyste-chat";

export const metadata: Metadata = {
  title: "Votre propre analyste — FinSight expliqué",
  description:
    "Comprendre FinSight : pipeline d'agents, méthodologie, livrables et philosophie. La promesse d'une analyse de niveau institutionnel pour tous.",
};

export default function AnalystePage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        {/* Intro éditoriale */}
        <section className="container-vitrine pt-20 md:pt-28 pb-16 max-w-4xl">
          <div className="label-vitrine mb-5">Qu&apos;est-ce que FinSight ?</div>
          <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-4xl md:text-6xl font-bold">
            Votre propre analyste, où que vous soyez,
            <span className="text-text-muted"> quand vous en avez besoin.</span>
          </h1>
          <p className="mt-8 text-lg text-text-secondary leading-relaxed">
            FinSight rend accessible l&apos;analyse financière institutionnelle
            — celle qu&apos;un junior produit en deux semaines dans une banque
            d&apos;investissement — à toute personne qui veut comprendre une
            société, un secteur ou un indice. Pas de magie : un pipeline
            déterministe, sept agents spécialisés, des données sourcées, et un
            jugement final qui reste le vôtre.
          </p>
        </section>

        {/* Pourquoi */}
        <section className="border-t border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">01 · Pourquoi</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary leading-tight">
                  L&apos;analyse de qualité est restée un privilège.
                </h2>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <p>
                  Pour faire un DCF propre, comparer une société à ses pairs,
                  modéliser des scénarios et formaliser le tout en pitchbook,
                  il faut soit un analyste senior, soit un terminal Bloomberg,
                  soit beaucoup de temps. La plupart des investisseurs
                  particuliers, étudiants, dirigeants de PME et même
                  professionnels en cabinet n&apos;ont aucun de ces trois.
                </p>
                <p>
                  FinSight comble ce vide. Tapez un ticker, un secteur ou un
                  indice — récupérez en quelques minutes ce qu&apos;une équipe
                  de recherche aurait livré en plusieurs jours.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Comment */}
        <section className="bg-surface-muted border-y border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-12">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">02 · Comment</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary leading-tight">
                  Sept agents, un seul jugement.
                </h2>
              </div>
              <div className="md:col-span-8 text-text-secondary leading-relaxed">
                <p>
                  Le moteur FinSight orchestre sept agents spécialisés via
                  LangGraph. Chacun a un rôle strict, une responsabilité
                  vérifiable, et son output est audité par les suivants. Aucun
                  chiffre n&apos;est inventé — le LLM commente, mais ne calcule
                  jamais.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <PillarCard
                icon={<Database className="w-4 h-4" />}
                title="Données"
                desc="yfinance, Finnhub, FMP, Yahoo News, FinBERT — multi-sources avec fallback."
              />
              <PillarCard
                icon={<Cpu className="w-4 h-4" />}
                title="Calculs déterministes"
                desc="DCF, WACC, ratios, scénarios : code Python pur, jamais le LLM."
              />
              <PillarCard
                icon={<Sparkles className="w-4 h-4" />}
                title="Synthèse IA"
                desc="Commentaire éditorial cadré par une constitution stricte."
              />
              <PillarCard
                icon={<ShieldCheck className="w-4 h-4" />}
                title="QA & gouvernance"
                desc="Quatre agents observateurs vérifient chaque sortie."
              />
              <PillarCard
                icon={<ArrowRight className="w-4 h-4" />}
                title="Devil's advocate"
                desc="Une thèse inverse systématique qui ajuste la conviction."
              />
              <PillarCard
                icon={<FileText className="w-4 h-4" />}
                title="Mise en forme"
                desc="ReportLab, python-pptx, openpyxl — des livrables prêts pour comité."
              />
            </div>
          </div>
        </section>

        {/* Ce qu'on livre */}
        <section>
          <div className="container-vitrine py-20 md:py-24 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10 mb-12">
              <div className="md:col-span-4">
                <div className="label-vitrine mb-3">03 · Livrables</div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary leading-tight">
                  Trois formats, une même rigueur.
                </h2>
              </div>
              <div className="md:col-span-8 text-text-secondary leading-relaxed">
                <p>
                  Chaque analyse produit trois fichiers téléchargeables. Vous
                  n&apos;avez plus rien à formaliser : présentez, partagez,
                  archivez.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              <DeliverableCard
                icon={<FileText className="w-4 h-4" />}
                title="Rapport PDF"
                meta="≈ 20 pages"
                desc="Thèse, valorisation, scénarios, risques, devil's advocate. Format ReportLab cohérent."
              />
              <DeliverableCard
                icon={<Presentation className="w-4 h-4" />}
                title="Pitchbook PowerPoint"
                meta="20 slides exactes"
                desc="Format Bloomberg, prêt pour comité d'investissement. Mise en page éditoriale soignée."
              />
              <DeliverableCard
                icon={<FileSpreadsheet className="w-4 h-4" />}
                title="Modèle Excel"
                meta="7 onglets"
                desc="Inputs · DCF · Ratios · Comparables · Scénarios · Dashboards. Formules vivantes."
              />
            </div>
          </div>
        </section>

        {/* Pour qui */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-20 md:py-24 max-w-5xl">
            <div className="grid md:grid-cols-12 gap-10">
              <div className="md:col-span-4">
                <div className="text-xs font-semibold tracking-widest uppercase text-text-inverse/50 mb-3">
                  04 · Pour qui
                </div>
                <h2 className="font-serif text-2xl md:text-3xl font-semibold leading-tight">
                  Conçu pour ceux qui décident.
                </h2>
              </div>
              <div className="md:col-span-8 grid sm:grid-cols-2 gap-x-8 gap-y-5">
                {[
                  ["Investisseurs particuliers", "Décider en connaissance de cause, sans payer un terminal pro."],
                  ["Analystes juniors", "Gagner deux semaines de modélisation par société couverte."],
                  ["Gérants de portefeuille", "Pré-screener, comparer, étoffer une thèse en quelques minutes."],
                  ["CFO et DAF", "Benchmark concurrentiel et veille sectorielle continue."],
                  ["Étudiants en finance", "Pratiquer la valorisation sur des cas réels, pas des slides théoriques."],
                  ["Cabinets de conseil", "Industrialiser la production d'analyses pour vos clients."],
                ].map(([title, desc]) => (
                  <div key={title}>
                    <div className="text-base font-medium">{title}</div>
                    <div className="text-sm text-text-inverse/60 mt-1 leading-relaxed">
                      {desc}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Chatbot */}
        <section className="border-t border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-3xl">
            <div className="text-center mb-10">
              <div className="label-vitrine mb-3">05 · Discutez avec FinSight</div>
              <h2 className="font-serif text-3xl md:text-4xl font-semibold text-text-primary tracking-tight">
                Une question ? Posez-la directement.
              </h2>
              <p className="mt-3 text-text-muted">
                Notre assistant connaît FinSight de bout en bout — pipeline,
                données, livrables, tarifs, roadmap.
              </p>
            </div>
            <AnalysteChat />
          </div>
        </section>

        {/* Bloc créateur */}
        <section className="bg-surface-muted border-t border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-4xl">
            <div className="label-vitrine mb-5">Le créateur</div>
            <div className="grid md:grid-cols-12 gap-10 items-start">
              <div className="md:col-span-4">
                <div className="aspect-square rounded-xl bg-surface-elevated border border-border-default flex items-center justify-center">
                  <span className="font-serif text-6xl font-bold text-text-primary">
                    BJ
                  </span>
                </div>
              </div>
              <div className="md:col-span-8 space-y-4 text-text-secondary leading-relaxed">
                <h3 className="font-serif text-2xl font-semibold text-text-primary">
                  Baptiste Jehanno
                </h3>
                <p>
                  Étudiant en BTS Comptabilité &amp; Gestion en alternance,
                  diplômé du <strong>FMVA</strong> (Financial Modeling &amp;
                  Valuation Analyst — CFI), en préparation du{" "}
                  <strong>CFA niveau I</strong>. Candidat pour une{" "}
                  <strong>L2 Gestion</strong> à Paris.
                </p>
                <p>
                  Mon ambition est claire, même si encore lointaine : devenir
                  analyste financier en banque d&apos;investissement.
                  FinSight est née pendant ma formation FMVA, d&apos;une
                  question revenue sans cesse au fil de mes échanges avec
                  Claude (Anthropic) : pourquoi n&apos;existe-t-il pas encore
                  d&apos;outil accessible à tous pour avoir une vision claire
                  lors d&apos;un investissement, d&apos;une valorisation, ou
                  du contrôle de gestion de sa propre entreprise ? La réponse
                  était simple : pas pleinement sous la forme dont je rêvais.
                  Alors je me suis formé, j&apos;ai pris en main certains
                  outils, ouvert mon premier terminal, et lancé ce qu&apos;est
                  aujourd&apos;hui FinSight — agent par agent, feature par
                  feature, livrable par livrable.
                </p>
                <p>
                  Mon souhait : que chacun ait accès à un outil abordable, avec
                  un rendu comparable à celui d&apos;un analyste junior, pour
                  une fraction du prix d&apos;un terminal pro.
                </p>
                <p className="italic text-text-muted border-l-2 border-accent-primary pl-4">
                  « FinSight est plus qu&apos;un projet d&apos;étudiant —
                  c&apos;est une réponse à l&apos;asymétrie d&apos;information. »
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function PillarCard({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="card-vitrine">
      <div className="w-9 h-9 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center mb-3">
        {icon}
      </div>
      <div className="text-sm font-semibold text-text-primary">{title}</div>
      <div className="text-xs text-text-muted mt-1.5 leading-relaxed">{desc}</div>
    </div>
  );
}

function DeliverableCard({
  icon,
  title,
  meta,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  meta: string;
  desc: string;
}) {
  return (
    <div className="card-vitrine">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-8 h-8 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center">
          {icon}
        </span>
        <div>
          <div className="text-sm font-semibold text-text-primary">{title}</div>
          <div className="text-2xs uppercase tracking-widest text-text-muted">{meta}</div>
        </div>
      </div>
      <p className="text-xs text-text-muted leading-relaxed">{desc}</p>
    </div>
  );
}
