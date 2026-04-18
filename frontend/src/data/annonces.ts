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
    slug: "portrait-entreprise-pappers",
    title: "Portrait d'entreprise pour les sociétés non cotées",
    summary:
      "Branchement à Pappers V2 pour analyser les 3,5 millions d'entreprises françaises non cotées : PME, ETI, deals M&A, due diligence light.",
    dateLabel: "Q2 2026",
    category: "Données",
    kind: "upcoming",
    readTime: "5 min",
    sections: [
      {
        title: "L'angle mort de la finance d'entreprise",
        paragraphs: [
          "Les outils d'analyse financière grand public ne couvrent que les sociétés cotées — c'est-à-dire moins de 1 % du tissu économique français. Les 99 % restants — PME familiales, ETI patrimoniales, scale-ups pré-IPO, sociétés cibles d'opérations M&A mid-cap — restent invisibles dans Bloomberg, FactSet, ou tout terminal de référence. Pour les analyser, il faut compulser des liasses fiscales, des extraits Kbis, des comptes annuels publiés au greffe : un travail manuel chronophage qui décourage l'investigation systématique.",
          "Pappers V2 résout ce problème côté données : son API expose, pour chaque entreprise française enregistrée, les bilans/comptes de résultat des 5 dernières années, les dirigeants, l'actionnariat, les procédures collectives, les marques déposées. Tout ce qu'un analyste M&A junior collecterait à la main en 2 heures, accessible en un appel API.",
        ],
      },
      {
        title: "Ce que FinSight ajoutera par-dessus",
        paragraphs: [
          "Pappers fournit les données brutes ; FinSight ajoute la couche analytique propriétaire. Le portrait d'entreprise reprendra la même rigueur que l'analyse société cotée, adaptée au contexte non coté.",
        ],
        bullets: [
          "Ratios financiers calculés sur 5 ans (rentabilité, structure financière, BFR, CAFG)",
          "Score de qualité comptable (cohérence des comptes, signes de manipulation)",
          "Score de risque de défaillance (modèle Altman Z-score adapté au contexte français)",
          "Estimation de valeur par DCF + multiples sectoriels (à partir des comparables cotés Euronext Growth)",
          "Analyse de la gouvernance (concentration de l'actionnariat, ancienneté dirigeants, procédures judiciaires)",
          "Briefing M&A : préparation cession, profil acquéreur idéal, valorisation négociable",
        ],
      },
      {
        title: "Cas d'usage prioritaires",
        paragraphs: [
          "Trois catégories d'utilisateurs sont attendues sur cette feature : (1) les advisors M&A mid-cap qui produisent quotidiennement des fiches cibles ; (2) les directions financières qui font de la veille concurrentielle sur leurs pairs non cotés ; (3) les fonds de Private Equity en phase de sourcing, qui screening 50-100 cibles avant d'en retenir 5 pour une approche.",
          "Une intégration FEC (fichier des écritures comptables) est aussi prévue pour les cabinets d'expertise comptable qui veulent enrichir leurs propres analyses clients avec un score FinSight propriétaire.",
        ],
      },
      {
        title: "Tarification anticipée",
        paragraphs: [
          "Le portrait d'entreprise sera inclus dans le plan Pro (44,99 €/mois, 8 portraits inclus). Au-delà, des crédits supplémentaires seront proposés à l'unité (~3 €/portrait). Sur le plan Enterprise, l'accès sera illimité pour cohérence avec les volumes M&A institutionnels.",
        ],
      },
    ],
  },
  {
    slug: "comptes-utilisateurs",
    title: "Comptes utilisateurs et historique persistant",
    summary:
      "Sauvegardez vos analyses, suivez vos sociétés favorites en watchlist, retrouvez vos pitchbooks d'une session à l'autre.",
    dateLabel: "Courant 2026",
    category: "Plateforme",
    kind: "upcoming",
    readTime: "4 min",
    sections: [
      {
        title: "L'état actuel : tout en éphémère",
        paragraphs: [
          "Aujourd'hui, chaque analyse FinSight est stockée dans le sessionStorage du navigateur de l'utilisateur. C'est rapide, sans friction, sans inscription requise — mais c'est aussi totalement éphémère. Fermez l'onglet, et vous perdez l'accès à l'analyse (sauf à avoir téléchargé les fichiers PDF/PPTX/XLSX). Cela convient pour de l'usage exploratoire ponctuel, mais pas pour un workflow professionnel récurrent.",
        ],
      },
      {
        title: "Ce que les comptes apporteront",
        paragraphs: [
          "L'authentification Supabase, déjà en place côté infrastructure, sera activée en mode complet. Chaque utilisateur disposera d'un espace personnel persistant qui transformera FinSight d'outil ponctuel en plateforme de travail.",
        ],
        bullets: [
          "Historique d'analyses : toutes vos analyses passées accessibles depuis le dashboard /dashboard, avec recherche par ticker, secteur, date",
          "Watchlists multiples : organisez vos sociétés suivies par thématique (\"Tech US\", \"Luxe\", \"Énergies vertes\", \"Pré-IPO\")",
          "Re-run intelligent : relancez une analyse passée pour comparer l'évolution des fondamentaux et de votre conviction",
          "Partage de pitchbooks : générez un lien public ou semi-privé pour partager une analyse avec un client/collègue (Pro uniquement)",
          "Synchronisation cross-device : démarrez une analyse sur ordinateur, terminez-la sur tablette",
          "Notifications : alerte automatique quand un cours franchit votre target ou qu'une news matérielle tombe sur une société de watchlist",
        ],
      },
      {
        title: "Implications techniques",
        paragraphs: [
          "Le passage en mode authentifié est non-trivial : il implique de migrer le sessionStorage vers une couche persistante PostgreSQL/Supabase, de gérer les permissions (Row Level Security), d'introduire un cache backend pour les analyses partagées, et de préparer une UI de gestion de compte (paramètres, facturation, équipe). C'est l'un des chantiers structurants de 2026.",
        ],
      },
      {
        title: "Roadmap intermédiaire",
        paragraphs: [
          "Avant l'ouverture publique des comptes, une bêta privée sera proposée aux utilisateurs ayant souscrit aux plans Essentiel et Pro. Inscription via /contact en attendant le lancement officiel.",
        ],
      },
    ],
  },
  {
    slug: "score-finsight",
    title: "Score FinSight propriétaire",
    summary:
      "Une note d'investissement composite — qualité, valorisation, momentum, gouvernance — calculée par notre pipeline et destinée à devenir un signal de référence.",
    dateLabel: "Fin 2026",
    category: "Recherche",
    kind: "upcoming",
    readTime: "6 min",
    sections: [
      {
        title: "L'idée fondatrice",
        paragraphs: [
          "Chaque analyse FinSight extrait, sous le capot, des centaines de signaux quantitatifs et qualitatifs : ratios de rentabilité, multiples de valorisation, dynamique des flux de trésorerie, sentiment des news, qualité du devil's advocate, conviction du modèle, écart à la moyenne sectorielle, etc. Ces signaux sont aujourd'hui consommés indirectement à travers la synthèse, mais ils ne donnent pas lieu à une note unique, comparable d'une société à l'autre.",
          "Le Score FinSight sera cette note. Composite, propriétaire, ancrée dans la rigueur de notre pipeline. Sa vocation : devenir une référence dans le paysage des notations alternatives, à la croisée du buy-side institutionnel et de l'analyse retail.",
        ],
      },
      {
        title: "Les quatre piliers du score",
        paragraphs: [
          "Le Score FinSight agrégera quatre dimensions distinctes, chacune notée de 0 à 100, puis combinées par pondération calibrée empiriquement.",
        ],
        bullets: [
          "Qualité (30 %) : ROIC, marge opérationnelle ajustée, qualité des earnings (Sloan), variabilité des cash-flows, gouvernance",
          "Valorisation (30 %) : décote/surcote DCF, multiples vs pairs, vs historique propre, marge de sécurité Graham",
          "Momentum (20 %) : performance 6/12 mois ajustée du beta, révisions d'estimés analystes, sentiment news pondéré",
          "Risque (20 %) : levier, liquidité, exposition cyclique, devil's advocate score, signaux comptables d'alerte",
        ],
      },
      {
        title: "Calibration et validation",
        paragraphs: [
          "La calibration des poids et seuils se fera sur l'historique d'analyses produit par FinSight, en backtest sur 3 ans minimum d'univers cotés. L'objectif : maximiser l'écart de performance entre le top quintile (Score > 80) et le bottom quintile (Score < 20), tout en maintenant une stabilité raisonnable du score (faible turnover trimestriel).",
          "Le score sera publié transparently : chaque société analysée affichera ses 4 sous-scores et les facteurs principaux de chaque dimension. Pas de boîte noire — la méthodologie complète sera publiée dans un white paper accessible à tous les utilisateurs.",
        ],
      },
      {
        title: "Vision long terme : une référence externe",
        paragraphs: [
          "À horizon 18-24 mois, le Score FinSight a vocation à devenir un signal alternatif consommable par des hedge funds via API, un benchmark pour les médias financiers, et un indicateur affiché dans les tableaux de bord des courtiers en ligne partenaires. C'est la pierre angulaire de la stratégie de transition de FinSight vers un statut de data provider, au-delà du simple SaaS d'analyse.",
        ],
      },
    ],
  },
];

export const RELEASES = ANNONCES.filter((a) => a.kind === "release");
export const UPCOMING = ANNONCES.filter((a) => a.kind === "upcoming");

export function getAnnonceBySlug(slug: string): Annonce | undefined {
  return ANNONCES.find((a) => a.slug === slug);
}
