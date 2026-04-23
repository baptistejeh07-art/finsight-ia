export type CasKind = "categorie" | "role";

export interface CasUsage {
  slug: string;
  kind: CasKind;
  title: string;
  short: string; // pour la grille
  intro: string; // sous-titre éditorial
  problem: string;
  solution: string;
  workflow: string[];
  livrables: string[];
}

const CAS: CasUsage[] = [
  // === CATÉGORIES ===
  {
    slug: "investissement",
    kind: "categorie",
    title: "Investissement",
    short: "Sélectionner ses positions sur fondamentaux solides.",
    intro:
      "FinSight aide les investisseurs particuliers et professionnels à pré-screener, comparer et bâtir une thèse complète sur n'importe quelle société cotée.",
    problem:
      "Construire une thèse d'investissement sérieuse demande de croiser des dizaines de sources, modéliser un DCF, comparer aux pairs, anticiper les scénarios. La plupart des investisseurs n'ont ni le temps ni les outils.",
    solution:
      "FinSight produit cette thèse complète en quelques minutes : valorisation par DCF, multiples comparables, scénarios bull/base/bear, devil's advocate, et les trois livrables professionnels prêts à archiver.",
    workflow: [
      "Saisir le ticker depuis l'app",
      "Lancer l'analyse complète (≈ 2 minutes)",
      "Lire la synthèse et le devil's advocate",
      "Télécharger le pitchbook PowerPoint pour partager ou archiver",
    ],
    livrables: ["Pitchbook 20 slides", "Modèle Excel DCF complet", "Rapport PDF"],
  },
  {
    slug: "conseil",
    kind: "categorie",
    title: "Conseil & M&A",
    short: "Industrialiser la production d'analyses pour vos clients.",
    intro:
      "Cabinets de conseil, advisors M&A, banques d'affaires : FinSight automatise la couche analytique répétitive pour libérer du temps de réflexion stratégique.",
    problem:
      "Les juniors passent l'essentiel de leur temps sur la modélisation et la mise en forme. Les seniors veulent des comparables, des screens, des scénarios — pas des slides à monter.",
    solution:
      "FinSight produit en deux minutes ce qu'un junior livrerait en deux jours. Le format est éditorial dès la sortie ; il ne reste qu'à challenger et à présenter.",
    workflow: [
      "Définir l'univers cible (secteur, indice ou liste)",
      "Lancer une vague d'analyses comparatives",
      "Récupérer les pitchbooks et Excel pour le pitch client",
      "Itérer sur les hypothèses avec le modèle Excel vivant",
    ],
    livrables: ["Pitchbooks série", "Modèles Excel cohérents", "Comparatifs cross-société"],
  },
  {
    slug: "finance-entreprise",
    kind: "categorie",
    title: "Finance d'entreprise",
    short: "Benchmark concurrentiel et veille sectorielle.",
    intro:
      "CFO, DAF, contrôleurs de gestion : suivez votre positionnement face aux pairs cotés et anticipez les évolutions de votre secteur.",
    problem:
      "Le benchmark concurrentiel se fait souvent au doigt mouillé, à partir de rapports annuels parcourus à la main. Difficile de produire une vue d'ensemble structurée et actualisée.",
    solution:
      "FinSight génère pour vos concurrents les mêmes ratios, multiples et comparatifs que pour vous-même. Vous voyez précisément où vous vous situez.",
    workflow: [
      "Sélectionner vos pairs (3 à 6 sociétés)",
      "Lancer le comparatif",
      "Identifier les écarts de performance",
      "Préparer le board pack avec les graphiques sourcés",
    ],
    livrables: ["Comparatif PowerPoint", "Excel benchmark", "Rapport sectoriel"],
  },
  {
    slug: "recherche",
    kind: "categorie",
    title: "Recherche actions",
    short: "Couvrir plus de noms, plus rapidement.",
    intro:
      "Buy-side et sell-side : étendez votre univers de couverture sans démultiplier vos coûts marginaux.",
    problem:
      "Initier la couverture d'une nouvelle valeur prend des semaines. Maintenir la couverture coûte cher en équipe.",
    solution:
      "FinSight automatise la couche déterministe (chiffres, ratios, comparables) ; vos analystes se concentrent sur l'edge analytique propre à leur boutique.",
    workflow: [
      "Initialiser la couverture en quelques minutes",
      "Mettre à jour automatiquement chaque trimestre",
      "Générer la note Initiating Coverage à partir du pitchbook",
      "Croiser avec votre vue propriétaire",
    ],
    livrables: ["Notes IC", "Updates trimestriels", "Bases de données comparables"],
  },
  {
    slug: "education",
    kind: "categorie",
    title: "Éducation & formation",
    short: "Former sur des cas réels, pas des slides théoriques.",
    intro:
      "Écoles de commerce, masters finance, certifications professionnelles : donnez à vos étudiants un outil professionnel pour pratiquer.",
    problem:
      "Les étudiants apprennent la théorie de la valorisation, mais n'ont jamais accès aux outils qui leur seront demandés en entreprise.",
    solution:
      "FinSight reproduit le workflow d'un analyste junior. Les étudiants travaillent sur des cas réels, comparent leurs hypothèses au moteur, et sortent diplômés opérationnels.",
    workflow: [
      "Distribuer des licences académiques",
      "Construire un cours autour d'analyses concrètes",
      "Organiser des compétitions de stock-picking",
      "Valider les acquis sur des cas notés",
    ],
    livrables: ["Licences académiques", "Cas pédagogiques", "Concours d'investissement"],
  },

  // === RÔLES ===
  {
    slug: "analyste",
    kind: "role",
    title: "Analyste financier",
    short: "Industrialiser la partie modélisation pour vous concentrer sur la thèse.",
    intro:
      "Que vous soyez junior en banque ou analyste indépendant, FinSight automatise la couche déterministe et vous laisse vous concentrer sur le jugement.",
    problem:
      "70 % du temps passé en formatage Excel et PowerPoint. 20 % à recopier des chiffres. 10 % à réfléchir.",
    solution:
      "FinSight inverse la proportion. Les chiffres et la mise en forme arrivent en deux minutes ; vous récupérez vos heures pour bâtir votre conviction.",
    workflow: [
      "Lancer l'analyse depuis l'app",
      "Adapter les hypothèses dans le modèle Excel",
      "Étoffer la synthèse PDF avec votre angle propriétaire",
      "Présenter le pitchbook adapté à votre charte",
    ],
    livrables: ["Pitchbook", "Modèle Excel", "Rapport PDF"],
  },
  {
    slug: "gerant",
    kind: "role",
    title: "Gérant de portefeuille",
    short: "Pré-screener et étoffer les thèses en quelques minutes.",
    intro:
      "Asset management traditionnel ou wealth tech : utilisez FinSight comme première ligne de filtrage et de validation.",
    problem:
      "Vous voyez passer des centaines d'idées par mois. Impossible d'investir le temps d'une analyse profonde sur chacune.",
    solution:
      "FinSight produit une analyse complète en deux minutes. Vous validez ou rejetez en connaissance de cause, sans mobiliser un analyste pour rien.",
    workflow: [
      "Pré-screener avec le comparatif sectoriel",
      "Lancer une analyse complète sur les survivants",
      "Vérifier le devil's advocate avant entrée en position",
      "Archiver le pitchbook au dossier d'investissement",
    ],
    livrables: ["Comparatifs", "Analyses complètes", "Devil's advocate"],
  },
  {
    slug: "cfo",
    kind: "role",
    title: "CFO / DAF",
    short: "Suivre vos pairs cotés en continu.",
    intro:
      "Direction financière, contrôle de gestion, M&A interne : ayez en permanence la vue concurrentielle structurée que vos concurrents n'ont pas.",
    problem:
      "Les benchmarks concurrentiels sont coûteux, datés et incomplets. Le board demande des comparaisons précises que personne n'a le temps de produire.",
    solution:
      "FinSight génère vos benchmarks avec les mêmes critères que vos propres reportings, mis à jour à la demande.",
    workflow: [
      "Définir l'univers de pairs",
      "Lancer le comparatif chaque trimestre",
      "Identifier les écarts d'efficience opérationnelle",
      "Préparer les slides board avec les insights clés",
    ],
    livrables: ["Comparatif trimestriel", "Excel benchmark", "Slides board"],
  },
  {
    slug: "particulier",
    kind: "role",
    title: "Investisseur particulier",
    short: "Investir comme un pro, sans payer un terminal Bloomberg.",
    intro:
      "Vous gérez votre patrimoine ou un portefeuille personnel ? Accédez à des analyses structurées et outillées pour quelques euros par mois.",
    problem:
      "Les forums boursiers donnent des opinions, pas des analyses. Les rapports des courtiers sont biaisés. Construire une vraie thèse demande des outils inaccessibles.",
    solution:
      "FinSight vous donne le même type d'analyse qu'un analyste sell-side, avec en plus un devil's advocate qui challenge la thèse — exactement ce qu'il vous manque.",
    workflow: [
      "Lancer une analyse sur votre prochain achat",
      "Lire la synthèse et le devil's advocate",
      "Vérifier la valorisation DCF dans l'Excel",
      "Décider en connaissance de cause",
    ],
    livrables: ["Analyse complète", "Excel DCF", "Devil's advocate"],
  },
  {
    slug: "etudiant",
    kind: "role",
    title: "Étudiant en finance",
    short: "Pratiquer la valorisation sur des cas réels.",
    intro:
      "Master finance, école de commerce, prépa CFA : FinSight est l'outil que vous n'avez pas en cours mais qu'on vous demandera en stage.",
    problem:
      "Vous apprenez la théorie de la valorisation, mais sans jamais voir un vrai pitchbook ni manipuler un vrai modèle DCF.",
    solution:
      "FinSight vous donne accès au workflow complet d'un analyste junior. Pratiquez sur des sociétés réelles, comparez vos hypothèses au moteur, montez en compétence avant même votre premier stage.",
    workflow: [
      "Lancer une analyse sur la société de votre cas d'études",
      "Comparer vos hypothèses Excel à celles du modèle",
      "Préparer un pitchbook au format pro pour vos rendus",
      "Étoffer votre portfolio de stock-picks documentés",
    ],
    livrables: ["Pitchbook", "Modèle Excel", "Cas pratiques"],
  },
];

export const CAS_LIST = CAS;
export const CAS_CATEGORIES = CAS.filter((c) => c.kind === "categorie");
export const CAS_ROLES = CAS.filter((c) => c.kind === "role");

export function getCasBySlug(slug: string): CasUsage | undefined {
  return CAS.find((c) => c.slug === slug);
}
