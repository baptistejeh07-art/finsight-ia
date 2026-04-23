export interface AnnonceSection {
  title: string;
  paragraphs: string[];
  bullets?: string[];
}

export interface Annonce {
  slug: string;
  title: string;
  summary: string;
  date?: string; // ISO ou null si feature à venir
  dateLabel: string; // affichage (ex: "16 avril 2026" ou "Q2 2026")
  category: string;
  kind: "release" | "upcoming";
  readTime: string; // ex: "4 min"
  sections: AnnonceSection[];
}

export const ANNONCES: Annonce[] = [
  // ============================================================
  // === DERNIÈRES SORTIES ======================================
  // ============================================================
  {
    slug: "early-backer-trial-gamification",
    title: "Early Backer 20 €/mois à vie, 30 jours offerts et missions bonus",
    summary:
      "Programme Early Backer : 10 places à 20 €/mois verrouillées à vie. Tous les plans payants passent à 30 jours d'essai gratuit. Nouvelle section « Missions » qui crédit des analyses bonus contre partages et invitations.",
    date: "2026-04-23",
    dateLabel: "23 avril 2026",
    category: "Tarification",
    kind: "release",
    readTime: "4 min",
    sections: [
      {
        title: "Programme Early Backer — 10 places uniquement",
        paragraphs: [
          "Les 10 premiers souscripteurs bénéficient d'un tarif de 20 €/mois verrouillé à vie, tant que l'abonnement reste actif. Le plan inclut toutes les fonctionnalités de l'offre Découverte (34,99 €) : analyses société, secteur, indice, comparatifs, livrables PDF/PPTX/XLSX.",
          "L'objectif est simple : construire un premier noyau d'utilisateurs pros qui stressent le produit en conditions réelles, en échange d'un pricing qui ne bougera jamais. Le compteur de places restantes est public et mis à jour en temps réel.",
        ],
        bullets: [
          "20 €/mois à vie (ou 192 €/an, -20 %) tant que l'abonnement reste actif",
          "Toutes les features du plan Découverte (34,99 €) — 20 analyses/mois incluses",
          "Badge Early Backer dans l'espace personnel",
          "Canal direct pour remonter du feedback produit",
          "Compteur public de places restantes (10 max)",
        ],
      },
      {
        title: "30 jours d'essai gratuit sur tous les plans",
        paragraphs: [
          "Tous les plans payants (Early Backer, Découverte, Pro, Enterprise) démarrent désormais par 30 jours gratuits. Aucun prélèvement pendant la période d'essai. Annulation en un clic depuis le portail de facturation Stripe.",
          "Cette friction en moins est volontaire : on préfère qu'un utilisateur essaie sérieusement pendant un mois plutôt qu'il rembourse après paiement. Le trial est poussé automatiquement au Checkout Stripe (trial_period_days=30).",
        ],
      },
      {
        title: "Missions — crédits bonus contre partages",
        paragraphs: [
          "La page Paramètres → Utilisation propose désormais une section Missions. Chaque mission accomplie crédite des analyses supplémentaires sur le quota mensuel.",
        ],
        bullets: [
          "Partage LinkedIn : +3 analyses",
          "3 invitations via lien de parrainage : +5 analyses / mois",
          "Témoignage écrit (3 lignes) : +5 analyses",
          "Partage d'une analyse générée : +2 analyses",
        ],
      },
    ],
  },
  {
    slug: "vitrine-carrousel-capacites",
    title: "Vitrine refondue : nouveau hero et carrousel de capacités",
    summary:
      "Nouveau titre « L'analyse institutionnelle, enfin accessible. » sur le hero. Une section carrousel horizontal à la Palantir présente six capacités clés de la plateforme — cliquables vers les sections ancrées de la méthodologie.",
    date: "2026-04-23",
    dateLabel: "23 avril 2026",
    category: "Vitrine",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "Pourquoi changer le hero",
        paragraphs: [
          "« Votre propre analyste, où que vous soyez » positionnait bien l'outil mais noyait la promesse. Le nouveau titre « L'analyse institutionnelle, enfin accessible. » se positionne frontalement contre Bloomberg sans le nommer : même niveau d'exigence, coût divisé. C'est la phrase qui a le mieux résonné dans les retours produit.",
        ],
      },
      {
        title: "Six capacités en carrousel horizontal",
        paragraphs: [
          "Inspirée de la navigation Palantir Warp Speed, la nouvelle section sous le hero défile horizontalement et présente les six facettes de la plateforme. Chaque card est cliquable vers une ancre de la documentation méthodologique.",
        ],
        bullets: [
          "La pile FinSight — sept agents spécialisés, rapport auditable",
          "Positionnement sectoriel — 11 secteurs GICS, Markowitz, top 3 convictions",
          "Ticker ou SIREN — société cotée via yfinance, PME française via Pappers/INPI/BODACC",
          "Score FinSight — validé par backtest 10 ans, +8,9 % alpha (t=+2,10)",
          "Gouvernance IA — constitution 7 articles, 4 agents observateurs",
          "Multi-livrables — PDF, PPTX et Excel générés en un clic",
        ],
      },
    ],
  },
  {
    slug: "fix-comparer-dashboard-indice",
    title: "Fix critique « Comparer » + interface indice complète",
    summary:
      "Le bouton Comparer (société et secteur) renvoyait vers l'accueil avant complétion : corrigé. L'interface post-analyse indice reçoit désormais toutes ses données (top constituants, stats perf, valorisations, benchmarks) et les colonnes d'années vides sont masquées sur les graphiques.",
    date: "2026-04-23",
    dateLabel: "23 avril 2026",
    category: "Corrections",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "Bug Comparer — cause racine",
        paragraphs: [
          "La page /resultats faisait un router.push vers /analyse quand le job n'était pas encore done au premier fetch. Sur le flux Comparer (deux analyses parallèles de 3 à 6 min), ça garantissait un retour immédiat à l'accueil. Le fix polle le job jusqu'à complétion au lieu de rediriger.",
          "En complément, les appels sessionStorage.setItem sont désormais protégés par try/catch : si le payload dépasse le quota navigateur, le routeur pousse quand même vers la page de résultats qui rechargera via getJob.",
        ],
      },
      {
        title: "Interface indice câblée",
        paragraphs: [
          "Les composants IndicePerfTiles, IndiceValuationTiles, IndiceTopConstituents et IndiceValuationBench recevaient result.data directement, mais les clés (perf_ytd, pe_median, etc.) sont imbriquées sous data.indice_stats. Le fix lit data.indice_stats en priorité avec fallback sur le plat.",
          "Le backend /do_indice renvoie désormais un tableau tickers_data de 25 constituants par market_cap, agrégé à partir des top_tickers sectoriels — la table Top 10 était vide jusqu'ici.",
        ],
      },
      {
        title: "Colonnes d'années vides masquées",
        paragraphs: [
          "Sur NVDA 2022, le graphique CapEx vs Dividendes affichait une colonne vide à gauche. Le filtre côté frontend drop maintenant les années où CapEx et Dividendes sont tous les deux à 0, pour que les barres restantes restent lisibles.",
        ],
      },
    ],
  },
  {
    slug: "commentaires-llm-pme",
    title: "Commentaires narratifs LLM sur les rapports PME",
    summary:
      "Le rapport PDF et le pitchbook PPTX des sociétés non cotées reçoivent désormais huit commentaires générés par LLM (SIG, rentabilité, solidité, efficacité, croissance, scoring, bankabilité, synthèse). Pas de texte générique de substitution : si le LLM n'est pas disponible, les sections restent vides — aucun contenu artificiel.",
    date: "2026-04-23",
    dateLabel: "23 avril 2026",
    category: "PME",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "Ce qui manquait",
        paragraphs: [
          "Jusqu'ici, le rapport PDF PME affichait les tableaux de ratios et les soldes intermédiaires de gestion sans aucun commentaire écrit. Pour un utilisateur PME non initié aux ratios financiers, c'était du chiffre brut sans interprétation.",
        ],
      },
      {
        title: "Une seule passe LLM pour huit sections",
        paragraphs: [
          "Le module core/pappers/commentaires_llm.py envoie les chiffres clés (CA, VA, EBE, résultat net, ratios, benchmark sectoriel, scoring Altman + FinSight PME) et récupère en une seule passe un JSON avec huit commentaires courts (3-5 phrases chacun), prêts à être injectés dans le PDF et le pitchbook.",
        ],
        bullets: [
          "SIG : lecture de la structure de création de valeur",
          "Rentabilité : marges EBE, ROE, ROCE vs médiane sectorielle",
          "Solidité financière : gearing, autonomie, liquidité",
          "Efficacité opérationnelle : DSO, DPO, DIO, BFR",
          "Croissance pluriannuelle : trajectoire CA + résultat",
          "Scoring : Altman Z + Score FinSight PME, lecture de la zone de risque",
          "Bankabilité : capacité d'endettement additionnel",
          "Synthèse : verdict global forces/faiblesses/recommandations",
        ],
      },
      {
        title: "Règle stricte : pas de fallback déterministe",
        paragraphs: [
          "Si le LLM n'est pas disponible ou si son JSON est invalide, les sections manquantes sont tout simplement omises du rapport. Pas de texte générique de substitution qui ferait passer un template pour de l'analyse. C'est une règle produit : mieux vaut du vide clair qu'un paragraphe qui habille le rapport sans rien dire.",
        ],
      },
    ],
  },
  {
    slug: "outputs-indice-refonte",
    title: "Outputs indice : perf history, méthodologie, Markowitz, titres agrandis",
    summary:
      "La page 4 du PDF indice affiche à nouveau une vraie courbe de performance comparée (CAC 40, DAX, FTSE — plus de ligne plate). Les tableaux méthodologie, sociétés représentatives et performances Markowitz sont corrigés. Les titres et légendes des graphiques sont agrandis sur les pages 5 et 10.",
    date: "2026-04-23",
    dateLabel: "23 avril 2026",
    category: "Livrables",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "Performance comparée des indices européens",
        paragraphs: [
          "Le fetch yfinance bulk (indice + S&P 500 + AGG + GLD) échouait dès qu'un ETF auxiliaire était indisponible sur le marché de cotation de l'indice. Le téléchargement se fait maintenant ticker par ticker : on récupère au minimum la courbe de l'indice principal, les trois benchmarks sont alignés dessus avec un forward-fill, et une série n'est affichée que si elle existe réellement.",
        ],
      },
      {
        title: "Tableaux méthodologie + sociétés représentatives corrigés",
        paragraphs: [
          "Le tableau Sources & Méthodologie lisait la mauvaise clé (mismatch majuscule/accent) et restait quasi vide. La clé est alignée, le backend peuple huit lignes documentant le pipeline (Score, signal, EV/EBITDA, P/E, ERP, allocation Markowitz, sentiment…).",
          "Les sociétés représentatives des trois secteurs Surpondérer s'affichaient à vide quand le fetch des constituants européens échouait. Un fallback sur la table CAC 40 / DAX / FTSE codée en dur permet désormais d'afficher les tickers même en cas de panne réseau sur le fetch live.",
        ],
      },
      {
        title: "Markowitz complet + lisibilité graphiques",
        paragraphs: [
          "Le tableau Performances attendues des portefeuilles Min-Variance / Tangency / ERC lisait des champs return/vol/sharpe absents du fallback test. Les trois champs sont désormais garantis — vides si et seulement si l'optimisation Markowitz n'a pas pu tourner.",
          "Sur le PDF indice, les titres et légendes des graphiques pages 5 (cartographie sectorielle) et 10 (allocation optimale) passent de 11-12 pt à 15-17 pt. Les labels secteurs étaient illisibles à la taille précédente.",
        ],
      },
    ],
  },
  {
    slug: "session-22-avril-charts-methodologie",
    title: "25 graphiques interactifs et méthodologie technique complète",
    summary:
      "Le catalogue de graphiques passe de 12 à 25 : volatilité, drawdown, ROE/ROIC, waterfall résultat, valuation multiples, radar, risk profile. La page /methodologie est refondue en whitepaper technique 1 400 lignes avec formules DCF/WACC/Altman/Piotroski, gouvernance IA et profils sectoriels adaptatifs (Bank, REIT, Insurance, Utility, Oil & Gas).",
    date: "2026-04-22",
    dateLabel: "22 avril 2026",
    category: "Plateforme",
    kind: "release",
    readTime: "5 min",
    sections: [
      {
        title: "13 nouveaux graphiques",
        paragraphs: [
          "Le dashboard propose désormais 25 graphiques au choix (contre 12 auparavant). Les composants stubs « bientôt disponible » sont remplacés par de vrais graphiques fonctionnels.",
        ],
        bullets: [
          "Société : Volatilité annualisée rolling, Drawdown vs plus-haut, ROE/ROIC history, Waterfall CA→RN, Revenue+Margin trend, Valuation multiples history, Balance health trend",
          "Secteur/indice : Performance vs S&P/Or/Obligs base 100, Distribution scores, Scatter valeur/qualité, Momentum leaders, Performance par secteur",
          "Comparatif : Radar multiples, Return profile YTD/1A/3A/5A, Risk profile Vol/Sharpe/MDD",
        ],
      },
      {
        title: "Méthodologie technique niveau whitepaper",
        paragraphs: [
          "La page /methodologie est refondue : organigramme LangGraph SVG inline, tableau détail des 10 nœuds, constitution 7 articles de gouvernance IA, 4 agents observateurs (Justice, Enquête, Journaliste, Sociologue), cascade LLM Groq → Mistral → Anthropic → Gemini, neuf sources de données, formules WACC/DCF/Altman Z/Piotroski F/Beneish M, six profils sectoriels adaptatifs (Standard, Bank, Insurance, REIT, Utility, Oil & Gas) avec détection automatique.",
        ],
      },
      {
        title: "Six bugs critiques corrigés",
        paragraphs: [
          "Au passage : conviction IA affichait 1 % au lieu de 78 %, bouton Ajouter un graphique invisible en mode édition, extension Chrome qui confondait SPX et S&P 500, graphique perf plate sur tous les indices européens (CAC 40, DAX, FTSE, Euro Stoxx), ratios % divisés par 100 dans la KpiGrid, build Vercel cassé par des fichiers dashboard non commités.",
        ],
      },
    ],
  },
  {
    slug: "score-finsight-backtest-sp100",
    title: "Score FinSight validé par backtest sp100 sur 10 ans",
    summary:
      "Le profil Balanced délivre +8,9 % d'alpha intra-sectoriel (t = +2,10, significatif à 95 %) sur 57 signaux BUY 2015-2025. Méthodologie walk-forward, sans data leakage.",
    date: "2026-04-21",
    dateLabel: "21 avril 2026",
    category: "Recherche",
    kind: "release",
    readTime: "6 min",
    sections: [
      {
        title: "Ce qu'on voulait savoir",
        paragraphs: [
          "Depuis le lancement, nous annoncions un Score FinSight propriétaire comme objectif de fond. La question de la validation est restée ouverte tant qu'aucun backtest rigoureux ne confirmait que ce score produit effectivement une surperformance. Nous avons conduit cette validation sur l'univers S&P 100 avec un historique de 10 ans (2015-2025).",
          "La méthodologie est walk-forward strict : pour chaque date de signal, le pipeline n'utilise que les données disponibles à cette date (pas de peek-ahead sur les fondamentaux, pas de survivorship bias sur la composition de l'univers). L'évaluation de la performance est mesurée contre la performance sectorielle médiane à 12 mois — c'est-à-dire l'alpha intra-sectoriel, la seule mesure qui a du sens quand on évalue un stock-picker.",
        ],
      },
      {
        title: "Les chiffres défendables",
        paragraphs: [
          "Les résultats présentés ici sont ceux qui résistent à un examen statistique. Nous les publions exactement comme ils sortent du backtest, sans sélection a posteriori.",
        ],
        bullets: [
          "Profil Balanced : +8,9 % d'alpha intra-sectoriel moyen sur 57 signaux BUY (t-stat = +2,10, significatif à 95 %)",
          "Profil Growth agressif sur la Tech : +19,4 % d'alpha historique sur la décennie",
          "Profil Value contrarian sur les secteurs cycliques (Materials, Industrials, Financials) : +24 % à +26 % d'alpha, significatif mais limité à ces secteurs",
          "Profil Conservative et Income : alpha positif mais non significatif hors secteurs cycliques",
        ],
      },
      {
        title: "Les limites qu'on assume",
        paragraphs: [
          "Un backtest n'est qu'un backtest. Nous listons explicitement les biais connus de cette validation.",
        ],
        bullets: [
          "Univers restreint au S&P 100 : large caps US uniquement, pas de mid/small cap, pas de marchés européens/asiatiques",
          "Période 2015-2025 : dominée par un bull market technologique qui peut flatter les signaux Growth",
          "Échantillon Balanced : 57 observations — statistiquement significatif à 95 %, mais loin d'un échantillon institutionnel",
          "Absence d'historique 2000-2015 : cette décennie inclurait deux crises majeures (dotcom, subprime) et changerait la lecture des profils cycliques",
        ],
      },
      {
        title: "Ce qui vient ensuite",
        paragraphs: [
          "Un backtest sur 2000-2025 est planifié dès que notre budget de données premium permet l'accès à un fournisseur complet (EODHD ou équivalent). C'est une question de cash-flow : nous préférons attendre les premiers clients plutôt que brûler de la trésorerie sur un dataset qui aurait très peu d'impact sur la prise de décision à ce stade.",
          "Nous préférons dire les choses telles qu'elles sont : FinSight est aujourd'hui au stade MVP avec une validation statistique initiale solide mais limitée. Nous ne prétendons pas être un provider institutionnel. Nous livrons un outil qui a été mesuré, avec ses forces et ses angles morts documentés.",
        ],
      },
    ],
  },
  {
    slug: "comparatif-secteur",
    title: "Comparatif secteur : deux couples secteur/univers en parallèle",
    summary:
      "Analyser côte à côte \"Technologie dans le S&P 500\" vs \"Santé dans l'Euro Stoxx 50\". Allocation Markowitz par couple, PDF et PPTX comparatifs générés automatiquement.",
    date: "2026-04-21",
    dateLabel: "21 avril 2026",
    category: "Livrables",
    kind: "release",
    readTime: "4 min",
    sections: [
      {
        title: "Le besoin",
        paragraphs: [
          "Le comparatif société côte à côte existait déjà, le comparatif indice aussi. Mais entre les deux, un trou : comparer deux sous-secteurs à l'intérieur de deux univers différents. Par exemple, décider entre le poids Tech dans un portefeuille S&P 500 et le poids Santé dans un portefeuille Euro Stoxx 50. C'est une question d'allocation classique, qui méritait son livrable propre.",
        ],
      },
      {
        title: "Ce que produit le module",
        paragraphs: [
          "La page /comparatif/secteur accepte deux couples secteur/univers, lance en parallèle deux analyses sectorielles complètes, puis croise les résultats.",
        ],
        bullets: [
          "Analyse sectorielle complète pour chaque couple (drivers macro, top performers, valorisations médianes)",
          "Allocation optimale Markowitz calculée indépendamment sur chacune des deux sélections",
          "Tableau comparatif des ratios clés : P/E médian, EV/EBITDA, croissance, qualité, drawdown",
          "PDF comparatif éditorial prêt pour comité d'allocation",
          "Pitchbook PPTX 20 slides structuré autour de la décision d'allocation",
        ],
      },
      {
        title: "Qui l'utilise",
        paragraphs: [
          "Ce livrable vise les utilisateurs qui construisent une allocation tactique : wealth managers qui ré-équilibrent trimestriellement, CIO de multi-family offices, analystes sell-side thématiques. Il permet d'aller au-delà du pur stock-picking vers une logique d'allocation sectorielle rationalisée.",
        ],
      },
    ],
  },
  {
    slug: "veille-ia",
    title: "Veille IA : articles d'analyse automatiques",
    summary:
      "Une nouvelle page /veille publie des articles courts générés par notre pipeline sur l'actualité marchés, les grandes tendances et les signaux sectoriels. Téléchargeables en PDF.",
    date: "2026-04-21",
    dateLabel: "21 avril 2026",
    category: "Contenu",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "L'idée",
        paragraphs: [
          "Nos utilisateurs nous demandaient régulièrement : \"pouvez-vous écrire un billet sur tel secteur cette semaine ?\" La réponse rapide était \"non, ce n'est pas notre métier\". La réponse réfléchie est différente : notre pipeline produit déjà des analyses sectorielles et de marché chaque jour, il suffit de les éditer sous forme d'articles courts.",
        ],
      },
      {
        title: "Ce que contient la page /veille",
        paragraphs: [
          "La rubrique Veille regroupe les articles d'analyse automatique. Chaque article s'appuie sur des données fraîches et suit une structure éditoriale courte : contexte, données chiffrées, interprétation, limites.",
        ],
        bullets: [
          "Articles rédigés par l'IA à partir des données pipeline FinSight",
          "Téléchargement PDF propre pour archivage ou partage interne",
          "Mise à jour au fil de l'eau selon l'actualité",
          "Aucun article ne constitue un conseil personnalisé — l'avertissement habituel s'applique",
        ],
      },
    ],
  },
  {
    slug: "contact-form-resend",
    title: "Formulaire de contact fonctionnel",
    summary:
      "Le formulaire /contact route vers Resend avec domaine authentifié DKIM. Les emails arrivent en boîte principale, pas en spam.",
    date: "2026-04-21",
    dateLabel: "21 avril 2026",
    category: "Plateforme",
    kind: "release",
    readTime: "2 min",
    sections: [
      {
        title: "Pourquoi c'était cassé",
        paragraphs: [
          "Jusqu'ici le formulaire /contact existait visuellement mais le backend email n'était pas câblé proprement. Certains messages partaient, d'autres non, et quand ils partaient, ils tombaient souvent en spam faute de DKIM.",
        ],
      },
      {
        title: "Le fix",
        paragraphs: [
          "Resend prend désormais en charge l'envoi transactionnel. Le domaine d'envoi est authentifié DKIM et le forwarding Namecheap route les réponses vers Gmail sans perte. Résultat : les messages partent, arrivent, et la réponse suit sur la même chaîne.",
        ],
      },
    ],
  },
  {
    slug: "dashboard-2-colonnes",
    title: "Dashboard 2 colonnes pour l'analyse société",
    summary:
      "Mise en page repensée : graphique multi-séries et valorisation à gauche, synthèse étoffée et Q&A à droite. Tout l'essentiel sans scroll.",
    date: "2026-04-16",
    dateLabel: "16 avril 2026",
    category: "Interface",
    kind: "release",
    readTime: "4 min",
    sections: [
      {
        title: "Pourquoi cette refonte",
        paragraphs: [
          "L'écran de résultats société hérité de la V1 empilait les éléments verticalement : KPI, graphique, synthèse, peers, Q&A. Sur un écran 13 ou 14 pouces — celui de 80 % des analystes — il fallait scroller plusieurs fois pour passer du prix à la valorisation, puis encore pour atteindre la synthèse. Cette friction tuait l'efficacité d'usage. Or notre métier, c'est la prise de décision rapide à partir d'une vue d'ensemble.",
          "Nous nous sommes inspirés de l'ergonomie d'un vrai terminal Bloomberg : densité informationnelle élevée, sans bruit, avec une hiérarchie visuelle qui guide l'œil de l'essentiel vers le détail. Le résultat : un dashboard 65/35 en deux colonnes qui fait tenir l'analyse complète au-dessus de la ligne de flottaison.",
        ],
      },
      {
        title: "Ce qui change concrètement",
        paragraphs: [
          "La colonne gauche regroupe désormais les éléments quantitatifs : graphique de cours multi-séries (target + S&P 500 + ETF secteur en pointillés), bloc de valorisation (recommandation, conviction, fourchette de prix cible), KPI grid 6 colonnes (P/E, EV/EBITDA, marges, croissance) et donut de répartition. À droite, la dimension qualitative : synthèse multi-blocs (résumé, valuation comment, financial commentary, peers commentary, conclusion), comparable peers, et la conversation Q&A en permanence accessible.",
        ],
        bullets: [
          "Layout grid-12 strict : pas de débordement, pas de cumul de scrollbars internes",
          "Graphique cours multi-séries via route Next API /api/market-series proxy Yahoo Finance",
          "KPI grid responsive : 6 colonnes desktop, 3 tablette, 2 mobile",
          "Synthèse découpée en 5 blocs distincts avec hiérarchie typographique claire",
          "Q&A en sidebar persistante : pas besoin de scroller pour poser une question",
        ],
      },
      {
        title: "Impact mesuré",
        paragraphs: [
          "Premier retour utilisateurs : l'analyse complète d'une société tient désormais sur un seul écran 1440x900. Le temps moyen pour valider ou rejeter une thèse passe de 4-5 minutes (V1) à moins de 90 secondes. Le scroll devient optionnel — réservé aux utilisateurs qui veulent creuser les commentaires détaillés.",
        ],
      },
      {
        title: "Et après",
        paragraphs: [
          "Cette refonte ouvre la voie à deux extensions : (1) une vue comparatif 2 sociétés en split-screen exploitant la même densité, prévue pour mai 2026, et (2) un mode présentation plein écran pour les comités d'investissement, qui réutilisera ces blocs avec une hiérarchie agrandie.",
        ],
      },
    ],
  },
  {
    slug: "logos-societe-logo-dev",
    title: "Logos société officiels via Logo.dev",
    summary:
      "Chaque ticker affiche désormais le logo officiel de la société. Top 50 mappés manuellement, fallback heuristique pour le reste, fallback ultime navy avec initiales.",
    date: "2026-04-11",
    dateLabel: "11 avril 2026",
    category: "Branding",
    kind: "release",
    readTime: "3 min",
    sections: [
      {
        title: "Le contexte : Clearbit Logo, mort en 2024",
        paragraphs: [
          "Pendant des années, Clearbit Logo (logo.clearbit.com/<domain>) a été le service de référence pour récupérer le logo d'une entreprise à partir de son domaine — gratuit, fiable, instantané. Brandfetch, Logo.dev et d'autres alternatives ont émergé après son retrait progressif en 2024. Pour FinSight, l'enjeu était double : afficher chaque société analysée avec son identité visuelle réelle (pas un simple texte ticker), tout en garantissant une couverture de 100 % de l'univers d'analyse.",
        ],
      },
      {
        title: "L'architecture en cascade",
        paragraphs: [
          "Plutôt que de dépendre d'un seul provider, nous avons construit une cascade de résolution en trois niveaux. Le composant `<CompanyLogo ticker=\"AAPL\" />` essaie successivement chacune des stratégies jusqu'à obtenir un rendu visuel acceptable.",
        ],
        bullets: [
          "Niveau 1 : mapping ticker → domaine officiel hardcodé pour le top 50 (AAPL → apple.com, MC.PA → lvmh.com, etc.). Couverture qualitative parfaite sur les sociétés les plus analysées.",
          "Niveau 2 : heuristique automatique sur le nom de la société retournée par yfinance (strip Inc./Corp./SA/AG, slugify, ajouter .com). Couverture probabiliste de 60-70 % sur les sociétés hors top 50.",
          "Niveau 3 : fallback graphique navy avec les 2 premières lettres du ticker en blanc, en typographie cohérente avec le reste de l'interface. Couverture garantie 100 %.",
        ],
      },
      {
        title: "Logo.dev — pourquoi ce choix",
        paragraphs: [
          "Parmi les alternatives évaluées (Brandfetch, Clearbit successors, Favicon scraping), Logo.dev se distingue par : un free tier généreux, une API simple (juste l'URL avec le domaine), pas de paywall sur les logos courants, et une qualité d'image supérieure (version vectorielle pour la majorité des grandes sociétés). Le token public est hardcodé pour V1 ; dès qu'un compte propriétaire sera ouvert, il passera dans NEXT_PUBLIC_LOGO_DEV_TOKEN.",
        ],
      },
      {
        title: "Effet sur l'expérience produit",
        paragraphs: [
          "Avant, les analyses se présentaient avec un simple ticker en haut : froid, peu engageant. Aujourd'hui, le logo officiel ancre immédiatement la société dans la mémoire visuelle de l'utilisateur. Les pitchbooks téléchargés et les pages de résultats ont gagné en crédibilité institutionnelle — un détail qui change tout en présentation client.",
        ],
      },
    ],
  },
  {
    slug: "pptx-indice-20-slides",
    title: "Pitchbook indice — 20 slides éditoriales",
    summary:
      "ERP, P/B, Dividend Yield, allocation optimale : 20 slides packagées au format société, prêtes pour comité d'investissement.",
    date: "2026-04-05",
    dateLabel: "5 avril 2026",
    category: "Livrables",
    kind: "release",
    readTime: "5 min",
    sections: [
      {
        title: "L'écart historique société/indice",
        paragraphs: [
          "Le pitchbook société FinSight était stable depuis plusieurs mois : 20 slides exactement, structure éditoriale calquée sur les rapports sell-side de référence, exhaustivité validée en comité. À l'inverse, le pitchbook indice livrait une dizaine de slides, suffisantes pour comprendre un univers mais insuffisantes pour décider d'une allocation. Cet écart créait une asymétrie problématique : un analyste qui couvrait à la fois des sociétés et des indices se retrouvait avec deux niveaux de qualité différents.",
        ],
      },
      {
        title: "Les 20 slides retenues",
        paragraphs: [
          "Nous avons reconstruit le pitchbook indice slide par slide en miroir du pitchbook société, en adaptant chaque chapitre au contexte multi-actifs.",
        ],
        bullets: [
          "Slides 1-3 : Couverture (logo indice, période, devise) + Equity Risk Premium calculée sur l'historique 5 ans + thèse macro",
          "Slides 4-7 : Composition (top 20 poids, breakdown sectoriel, géographique, capitalisations)",
          "Slides 8-11 : Valorisations agrégées (P/E médian, EV/EBITDA, P/B, Dividend Yield) avec dispersion intra-indice",
          "Slides 12-14 : Performance (cumul, drawdown, volatilité, comparaison vs benchmark mondial) + slide d'allocation optimale par optimisation moyenne-variance",
          "Slides 15-17 : Top performers / Underperformers / Mouvements significatifs sur la période",
          "Slides 18-20 : Devil's advocate macro + risques systémiques + conclusion stratégique",
        ],
      },
      {
        title: "L'allocation optimale, le cœur du livrable",
        paragraphs: [
          "La slide 14 mérite une mention particulière : elle calcule, par optimisation de portefeuille de Markowitz, l'allocation moyenne-variance efficiente sur les composants de l'indice (avec contrainte long-only et limite par position). Le résultat est présenté sous forme de poids cibles + Sharpe attendu + drawdown théorique. C'est exactement le type de calcul qu'un comité d'investissement réclame en début de séance.",
          "Les analyses indice livrées en avril ont été acceptées sans réécriture par 100 % des testeurs internes — un seuil que la version précédente n'atteignait pas.",
        ],
      },
      {
        title: "Sectoriels au sein d'un indice — la suite",
        paragraphs: [
          "Cette refonte ouvre maintenant la production d'analyses sectorielles au sein d'un indice : par exemple, \"Technologie au sein du S&P 500\" ou \"Banques au sein de l'Euro Stoxx 50\". Le pipeline est partiellement en place ; les pitchbooks correspondants seront livrés au cours du Q2 2026.",
        ],
      },
    ],
  },

  // ============================================================
  // === FEATURES À VENIR =======================================
  // ============================================================
  {
    slug: "paiement-stripe-live",
    title: "Paiement en ligne : Early Backer, Découverte, Pro et Enterprise",
    summary:
      "Checkout Stripe live avec 30 jours d'essai sur tous les plans, portail self-service pour gérer l'abonnement, Early Backer 20 €/mois à vie limité aux 10 premiers souscripteurs.",
    dateLabel: "Imminent — avril/mai 2026",
    category: "Paiement",
    kind: "upcoming",
    readTime: "3 min",
    sections: [
      {
        title: "Ce qui est prêt côté code",
        paragraphs: [
          "L'infrastructure Stripe est livrée : webhook FastAPI qui persiste les subscriptions dans Supabase, page /parametres/facturation avec Checkout Session, portail client self-service, quatre plans (Early Backer, Découverte, Pro, Enterprise) en mensuel et annuel. Le trial_period_days=30 est poussé automatiquement au Checkout, sans intervention manuelle.",
        ],
      },
      {
        title: "Ce qui manque avant ouverture",
        paragraphs: [
          "La finalisation de l'onboarding Stripe côté compte professionnel (KYC, IBAN, validation d'identité) prend quelques jours de délai côté Stripe. Une fois validée, les produits et prix sont créés par un script d'amorçage en une commande, les clés live sont ajoutées aux variables d'environnement Railway, et la page facturation bascule en mode encaissement réel.",
        ],
        bullets: [
          "4 produits créés (Early Backer, Découverte, Pro, Enterprise) × 2 intervalles = 8 prix Stripe",
          "Endpoint webhook sécurisé /stripe/webhook (signature HMAC)",
          "30 jours d'essai gratuit sur tous les plans payants",
          "Prix Early Backer verrouillé à vie via Stripe price_id dédié",
          "Portail self-service : changement de plan, mise à jour carte, annulation, factures",
        ],
      },
      {
        title: "Ce qui reste ouvert",
        paragraphs: [
          "La tarification annuelle sera ajustée au fil des premiers retours (actuellement -20 % vs mensuel). Un mode facturation entreprise (virement SEPA + facture PDF) est prévu pour les plans Enterprise dans un second temps.",
        ],
      },
    ],
  },
  {
    slug: "extension-chrome-tradingview",
    title: "Extension Chrome TradingView publique sur le Web Store",
    summary:
      "Ajouter un bouton « Analyser avec FinSight » directement sur les pages TradingView. Détection automatique du ticker ou de l'indice, redirection vers l'analyse complète en un clic.",
    dateLabel: "Avril 2026",
    category: "Distribution",
    kind: "upcoming",
    readTime: "2 min",
    sections: [
      {
        title: "Ce que fait l'extension",
        paragraphs: [
          "L'extension injecte un bouton discret sur les pages TradingView (symbols, watchlists, screener). Un clic envoie le ticker détecté vers finsight-ia.com/app avec pré-remplissage et lancement automatique de l'analyse. Les indices (CAC 40, S&P 500, DAX…) sont résolus même quand TradingView affiche un alias (SPX, FCHI, GDAXI).",
        ],
      },
      {
        title: "Ce qui manque",
        paragraphs: [
          "La version 1.0.2 est fonctionnelle en installation manuelle (side-load). La soumission au Chrome Web Store coûte 5 $ de frais développeur uniques et demande une review de 2 à 5 jours. Une fois publiée, l'extension sera installable en un clic depuis le Chrome Web Store.",
        ],
      },
    ],
  },
  {
    slug: "score-finsight-extension-commerciale",
    title: "Score FinSight : extension commerciale et backtest 2000-2025",
    summary:
      "Le Score est validé statistiquement sur l'univers S&P 100 (2015-2025). Prochaine étape : backtest sur 2000-2025 via données premium EODHD, puis commercialisation du signal en API.",
    dateLabel: "Fin 2026",
    category: "Recherche",
    kind: "upcoming",
    readTime: "5 min",
    sections: [
      {
        title: "Ce qui est déjà fait",
        paragraphs: [
          "Le Score FinSight existe et a été validé par un backtest walk-forward sur l'univers S&P 100 entre 2015 et 2025. Le profil Balanced délivre +8,9 % d'alpha intra-sectoriel sur 57 signaux BUY (t-stat = +2,10, significatif à 95 %). Les profils Growth agressif (Tech) et Value contrarian (secteurs cycliques) affichent des chiffres plus élevés mais sur des segments plus étroits. Ces résultats sont publiés dans l'annonce du 21 avril 2026.",
        ],
      },
      {
        title: "Les deux extensions prévues",
        paragraphs: [
          "Deux chantiers suivent la validation initiale.",
        ],
        bullets: [
          "Backtest 2000-2025 via un fournisseur de données premium (EODHD ou équivalent). Inclut deux crises majeures (dotcom, subprime) et permet de tester la robustesse des profils cycliques hors du bull market tech 2015-2025.",
          "Commercialisation du Score en API : endpoint dédié pour hedge funds, médias financiers et courtiers qui souhaitent afficher le signal dans leurs interfaces. C'est le début de la transition de FinSight de SaaS d'analyse vers statut de data provider.",
        ],
      },
      {
        title: "Pourquoi attendre",
        paragraphs: [
          "Nous pourrions acheter aujourd'hui un accès EODHD, mais c'est du cash qui a un impact marginal tant que nous n'avons pas les premiers clients qui financent naturellement cette évolution. Le principe est simple : d'abord valider que le produit actuel trouve son marché, puis investir dans l'infrastructure de recherche qui élargit le positionnement.",
        ],
      },
    ],
  },
  {
    slug: "dataset-finsight-trends",
    title: "Dataset FinSight Trends (signal alternatif)",
    summary:
      "Historiser anonymement les tickers et secteurs analysés sur la plateforme pour construire un signal d'attention investisseur retail/PME, vendable aux hedge funds.",
    dateLabel: "Fin 2026",
    category: "Données",
    kind: "upcoming",
    readTime: "4 min",
    sections: [
      {
        title: "L'idée",
        paragraphs: [
          "Chaque analyse lancée sur FinSight est un signal d'intérêt — quelqu'un a pris le temps de regarder sérieusement une société ou un secteur. Agrégés sur des milliers d'utilisateurs et stockés anonymement, ces signaux forment un dataset d'attention investisseur professionnel/PME/retail éduqué. Ce type de donnée se vend à des hedge funds quantitatifs qui l'utilisent comme signal alternatif — au même titre que le trafic web ou la géolocalisation de flotte logistique.",
        ],
      },
      {
        title: "Ce qu'il faut construire",
        paragraphs: [
          "Le dataset existera vraiment quand trois conditions seront réunies.",
        ],
        bullets: [
          "Volume suffisant d'utilisateurs actifs pour que l'agrégat soit statistiquement intéressant",
          "Anonymisation rigoureuse et conforme RGPD (aucun utilisateur identifiable, même indirectement)",
          "Infrastructure d'export régulier (quotidien ou intrajournalier) avec garanties de latence",
        ],
      },
      {
        title: "Temporalité",
        paragraphs: [
          "Construction du dataset en parallèle de la croissance de la base utilisateurs. Commercialisation seulement quand il y a quelque chose d'intéressant à vendre — probablement 2027 au plus tôt.",
        ],
      },
    ],
  },
  {
    slug: "b2b2b-cabinets-comptables",
    title: "B2B2B cabinets comptables (FEC + Pennylane + détection)",
    summary:
      "Canal de distribution B2B2B vers les cabinets d'expertise comptable : import FEC, connecteurs Pennylane et Sage, score de défaillance, score de financement. Accès indirect au tissu PME/ETI français.",
    dateLabel: "2027",
    category: "Distribution",
    kind: "upcoming",
    readTime: "4 min",
    sections: [
      {
        title: "Le pari",
        paragraphs: [
          "Les cabinets d'expertise comptable tiennent la comptabilité de millions de PME françaises. Leur offrir FinSight comme outil d'analyse enrichie — import FEC, reconstruction P&L et bilan, score de défaillance, estimation de capacité de financement — c'est leur donner un produit différenciant vis-à-vis de leurs clients dirigeants, tout en accédant au tissu PME français par un canal que nous n'aurions jamais pu adresser en direct.",
        ],
      },
      {
        title: "Composantes",
        paragraphs: [
          "Le parser FEC est déjà livré (avril 2026). Les connecteurs Pennylane et Sage sont en cours. Restent à construire les couches analytiques spécifiques au contexte non coté.",
        ],
        bullets: [
          "Score de risque de défaillance (Altman Z-score adapté France, enrichi par les signaux qualitatifs)",
          "Score de capacité de financement (profil bancable / investisseur)",
          "Comparatif sectoriel PME non coté via benchmarks Pappers",
          "Dashboards client destinés à la restitution en rendez-vous annuel expert-comptable/dirigeant",
        ],
      },
      {
        title: "Pourquoi c'est un gros levier",
        paragraphs: [
          "Un cabinet comptable moyen a entre 50 et 500 clients PME. Adresser 100 cabinets, c'est adresser 5 000 à 50 000 PME sans effort commercial en direct. La synergie avec Pappers (sociétés non cotées françaises) rend le package enterprise particulièrement différenciant.",
        ],
      },
    ],
  },
];

export const RELEASES = ANNONCES.filter((a) => a.kind === "release");
export const UPCOMING = ANNONCES.filter((a) => a.kind === "upcoming");

/**
 * Sélection mise en avant sur la page d'accueil vitrine (sections
 * « Dernières sorties » et « Prochainement »). Les cartes détaillées
 * de toutes les annonces restent accessibles via /annonces/[slug].
 *
 * Règle : 3 max sur chaque section, les plus impactantes pour un
 * visiteur prospect.
 */
const RELEASES_FEATURED_SLUGS = [
  "early-backer-trial-gamification",       // business hook — Early Backer 20€/mois à vie
  "score-finsight-backtest-sp100",         // crédibilité — +8,9 % alpha backtesté
  "session-22-avril-charts-methodologie",  // richesse produit — 25 charts + méthodo
];

const UPCOMING_FEATURED_SLUGS = [
  "extension-chrome-tradingview",          // distribution concrète court terme
  "score-finsight-extension-commerciale",  // monétisation différenciante (API Score)
  "b2b2b-cabinets-comptables",             // gros levier business (distribution indirecte)
];

export const RELEASES_FEATURED: Annonce[] = RELEASES_FEATURED_SLUGS
  .map((slug) => ANNONCES.find((a) => a.slug === slug))
  .filter((a): a is Annonce => a !== undefined);

export const UPCOMING_FEATURED: Annonce[] = UPCOMING_FEATURED_SLUGS
  .map((slug) => ANNONCES.find((a) => a.slug === slug))
  .filter((a): a is Annonce => a !== undefined);

export function getAnnonceBySlug(slug: string): Annonce | undefined {
  return ANNONCES.find((a) => a.slug === slug);
}
