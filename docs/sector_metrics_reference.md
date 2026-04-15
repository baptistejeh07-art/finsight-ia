# Métriques sectorielles — Référence refonte XLSX

Document de référence pour la refonte des templates XLSX société et secteur par profil métier. Chaque profil liste :

- **Ce qu'il faut RETIRER** du template standard (EV/EBITDA, marges brutes, etc.) parce que non applicable ou trompeur.
- **Ce qu'il faut AJOUTER** avec les benchmarks (fourchettes typiques).
- **Le modèle de valorisation** à utiliser à la place du DCF générique.
- **Sources de données** : yfinance (`.info`), statements Supabase (IS/BS/CF), filings externes quand nécessaire.

Le profil est détecté automatiquement via `core/sector_profiles.detect_profile(sector, industry)`. La liste des constantes est dans `core/sector_profiles.py` : `STANDARD`, `BANK`, `INSURANCE`, `REIT`, `UTILITY`, `OIL_GAS`.

Contenu actuellement implémenté dans le code : les ratios par profil sont définis dans `_CONFIGS` dans `core/sector_profiles.py` et utilisés par `sector_pdf_writer` + `indice_pdf_writer`. Les writers XLSX ne les utilisent **pas encore** — c'est l'objet du chantier de refonte Baptiste.

---

## Vue d'ensemble — Ratios à implémenter par profil

Résumé compact de tous les ratios à mettre dans les templates XLSX. Les colonnes **P1/P2/P3** correspondent à trois niveaux de priorité :

- **P1** = ratio critique, indispensable (doit apparaître en haut de l'onglet INPUT + dans le tableau de synthèse)
- **P2** = ratio important, à intégrer dans le second bloc
- **P3** = ratio complémentaire, peut être placé en annexe ou en note

| Profil | P1 (critique) | P2 (important) | P3 (complément) | Modèle de valo |
|---|---|---|---|---|
| **STANDARD** | EV/EBITDA · P/E · ROE · FCF Yield · Debt/EBITDA | EV/Rev · ROIC · Marge EBITDA · Net Margin · Interest Coverage | Altman Z · PEG · Piotroski F · Gross Margin | DCF 3-phases |
| **BANK** | P/TBV · P/E · ROE · NIM · CET1 Ratio · Cost/Income | ROA · NPL Ratio · Coverage · Div Yield · Loan/Deposit | P/PPOP · LCR · NSFR · Non-II / Total Rev · Dividend Coverage | DDM (Gordon) + Justified P/B |
| **INSURANCE** | P/B · P/E · Combined Ratio · ROE · Solvency II | Loss Ratio · Expense Ratio · Investment Yield · Div Yield | P/EV (Life) · NBV Margin · Cat Reserves · Reserve Releases | P/B ancré ROE ou Embedded Value (Life) |
| **REIT** | P/FFO · P/AFFO · P/NAV · FFO/share · Div Yield · LTV | Occupancy · Same-Store NOI Growth · Debt/EBITDA · ICR · Dividend Coverage | WALT · Cap Rate · Debt Maturity · Capex / Revenue | NAV + P/FFO multiple |
| **UTILITY** | P/E · EV/EBITDA · P/RAB · Allowed ROE · Div Yield · Debt/RAB | Earned ROE · RAB Growth · FFO/Debt · Capex/D&A · Payout Ratio | Load Factor · Customer Count · T&D Losses · Rate Case Timing | RAB × multiple sectoriel (SOTP) |
| **OIL_GAS** | EV/DACF · EV/EBITDAX · Price/Reserves 1P · Net Debt/EBITDAX · Breakeven WTI | EV/Production · FCF Yield @ strip · F&D Cost · Cash Cost/BOE · RRR | Hedging % · R/P Ratio · 3P Upside · Decline Rate · Royalty Rate | NAV 1P + 2P discount (+SOTP pour integrated) |
| **TECH / SaaS** | EV/Revenue · EV/Gross Profit · Rule of 40 · NRR · Gross Margin | ARR Growth · CAC Payback · Magic Number · FCF Margin · Gross Retention | R&D / Revenue · SBC / Revenue · ARR / Employee · DBNRR · Logo Retention | EV/Rev + EV/FCF exit multiple |
| **RETAIL / STAPLES** | EV/EBITDA · P/E · SSSG (comp sales) · Gross Margin · Inventory Turns | Store Count · Revenue / sq ft · GMROI · Online Mix % · Div Yield | CapEx / Store · Lease-adj Debt · Unit Growth · Private Label Mix | EV/EBITDA + multiple growth-adjusted |
| **PHARMA / BIOTECH** | rNPV Pipeline · Peak Sales · Patent Cliff · R&D / Revenue · EV/NTM Sales | Gross Margin · Operating Margin · Phase III assets · FCF / Net Income · Dividend Coverage | Phase II assets · Milestone payments · License deals · Orphan % | rNPV risk-adj + DCF residual |
| **AIRLINES** | EV/EBITDAR · CASM ex-fuel · RASM · Load Factor · ASM Growth | Fuel cost / gallon · Stage Length · Labor CASM · Fleet Age · Unit Revenue | Ancillary Revenue % · Loyalty Miles Liability · Capex / Revenue · Fleet Mix | EV/EBITDAR + replacement value |
| **METALS & MINING** | NAV (DCF par mine) · AISC / unit · Reserves 1P+2P · Production · EV/EBITDA | Grade (g/t or %) · LOM · Capex / oz · Net Debt/EBITDA · FCF yield @ spot | Royalty rate · Country risk · Stripping ratio · Cash cost quartile | NAV discount (0.8-1.2x) + spot EV/EBITDA |
| **TELECOM** | EV/EBITDA · FCF Yield · Div Yield · ARPU · Subscriber Growth | Churn · Capex / Revenue · Net Debt/EBITDA · EBITDA Margin · Post-paid mix | ARPU Growth · Revenue / HH · FTTH coverage · Spectrum Holdings · Tower Lease Cost | EV/EBITDA + DCF + dividend support |

---

## 1. BANK — Banques commerciales + banques d'investissement

**Tickers concernés** : BAC, JPM, C, WFC, GS, MS, USB, PNC, BK, TFC, SCHW, BNP.PA, BARC.L, DBK.DE, HSBA.L, ISP.MI, SAN.MC, UBSG.SW, etc.

### À retirer

| Métrique standard | Raison |
|---|---|
| EV/EBITDA | Inapplicable : une banque n'a pas d'EBITDA significatif (elle *est* son passif). Les intérêts payés sont un coût de production, pas un OPEX. |
| EV/Revenue | Revenus = NII + commissions, non comparables aux revenus d'une industrie. EV inclut la dette opérationnelle. |
| Marge brute / Marge EBITDA | Aberrantes (80-95%) parce que le « COGS » est principalement l'intérêt payé aux déposants. Trompeuses. |
| Net Debt / EBITDA | La dette est le produit d'une banque. Ratio vide de sens. |
| Free Cash Flow Yield | FCF = Net Income ± Δ(loans - deposits). Très volatile et pas comparable aux corporates. |
| DCF | Impossible à construire proprement : WACC aberrant (coût des fonds propres uniquement pertinent), NOPAT non défini. |
| Altman Z-Score | Calibré pour manufacturing. Inadapté aux bilans bancaires (levier 10-15x normal). |

### À ajouter — Valorisation

| Métrique | Formule / Source | Benchmark |
|---|---|---|
| **P/TBV (Price to Tangible Book Value)** | `yfinance .info.priceToBook` (approximation). TBV = Equity − Goodwill − Intangibles. | 0.8-1.5x normal ; prime justifiée si ROE > coût FP. |
| **P/E** | `yfinance .info.trailingPE` | 8-14x (cycle-dépendant) |
| **P/PPOP** (Pre-Provision Operating Profit) | Market Cap / (Revenue − OpEx avant provisions). | 5-10x. À calculer depuis IS : `Revenue − Operating Expenses + Provisions`. |

**Modèle de valorisation** : **Dividend Discount Model (Gordon)** ou **Excess Return Model** (Damodaran). Pas de DCF.
- Gordon : `Price = DPS₁ / (k − g)` avec k = coût des fonds propres (CAPM).
- Alternative : `Justified P/B = (ROE − g) / (k − g)`.

### À ajouter — Fondamentaux bancaires (KPIs)

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **NIM (Net Interest Margin)** | Net Interest Income / Average Earning Assets | 1.5-3.5% (EU), 2.5-4% (US) | IS Supabase (NII ligne) / BS (Loans + Investments moyennés) |
| **Cost / Income** | OpEx / (NII + Non-Interest Income) | 45-65% | IS Supabase |
| **CET1 Ratio** | Common Equity Tier 1 / Risk-Weighted Assets | ≥ 11% (Bâle III), ≥ 12.5% (SIFI) | **Pillar 3** trimestriel (non yfinance — à parser des filings) |
| **NPL Ratio** | Non-Performing Loans / Total Loans | < 3% (développés), < 1.5% (qualité) | Idem Pillar 3 |
| **Coverage Ratio** | Loan Loss Reserves / NPLs | > 100% | Idem |
| **LCR** (Liquidity Coverage Ratio) | HQLA / Net Cash Outflows 30j | > 100% | Idem |
| **NSFR** (Net Stable Funding Ratio) | Available Stable Funding / Required Stable Funding | > 100% | Idem |
| **ROE** | Net Income / Common Equity | 10-15% (cible) | IS/BS Supabase |
| **ROA** | Net Income / Total Assets | 0.9-1.3% | IS/BS Supabase |
| **Loan/Deposit Ratio** | Loans / Deposits | 80-95% | BS Supabase |
| **Dividend Yield** | Trailing dividends / price | 3-7% | yfinance |

### Sous-catégories à distinguer

- **Banques commerciales retail** (USB, PNC, BNP.PA) : focus sur NIM + loan growth + deposits stables.
- **Banques d'investissement / Capital markets** (GS, MS) : focus sur FICC revenues + M&A fees + ROE + leverage ratio Bâle III.
- **Banques universelles** (JPM, BNP, HSBA) : combiner les deux + segment reporting (Retail / CIB / Asset Mgmt / Wealth).

### Structure XLSX société recommandée (onglet INPUT)

```
Revenus          ├ Net Interest Income
                 ├ Non-Interest Income (Commissions + Trading + Other)
                 └ Total Revenue
Coûts            ├ Operating Expenses (ex-provisions)
                 ├ Loan Loss Provisions
                 └ Pre-Provision Operating Profit (PPOP)
Résultat         ├ Pre-tax Profit
                 ├ Tax
                 └ Net Income → EPS → DPS
Bilan            ├ Total Loans Net
                 ├ Deposits (Demand / Term / Wholesale)
                 ├ Total Assets
                 ├ Tier 1 Capital
                 └ Tangible Common Equity → TBV
Ratios           ├ NIM, Cost/Income, ROE, ROA
                 ├ CET1, NPL, Coverage, LCR, NSFR
                 └ P/TBV, P/E, P/PPOP, Div Yield
```

---

## 2. INSURANCE — Assureurs (P&C, Life, Health, Re)

**Tickers concernés** : BRK.B, TRV, PGR, ALL, CB, HIG, AIG, MET, PRU, AFL, UNH, ELV, MMC, AON ; CS.PA, ALV.DE, MUV2.DE, ZURN.SW, G.MI.

### À retirer

| Métrique standard | Raison |
|---|---|
| EV/EBITDA | Revenus techniques = primes − sinistres. EBITDA aberrant. |
| Gross Margin | Le « COGS » est la sinistralité, variable par nature. |
| DCF classique | Les cash flows sont dominés par le float (portefeuille d'investissement). Modèle dédié nécessaire. |
| Altman Z | Mêmes raisons que banques. |

### À ajouter — Valorisation

| Métrique | Formule | Benchmark |
|---|---|---|
| **P/B (Price to Book)** | yfinance.priceToBook | 0.8-1.3x (P&C), 0.6-1.1x (Life) |
| **P/EV (Price to Embedded Value)** | Price / (Net Asset Value + VIF — Value of In-Force Business) | 0.6-1.0x (Life essentiellement) |
| **P/E** | 8-13x | yfinance.trailingPE |
| **Dividend Yield** | 3-5% | yfinance |

**Modèle de valorisation** :
- **P&C/Non-Life** : Multiple P/B ancré sur ROE durable vs coût des FP. `Fair P/B = (ROE − g) / (k − g)`.
- **Life** : **Embedded Value** (EV = NAV + VIF) + New Business Margin. EV est publié par les assureurs européens dans les rapports annuels.
- **Reinsurance** : même logique P&C + cycle de pricing mondial.

### À ajouter — Fondamentaux assurance (KPIs)

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **Combined Ratio** | (Losses + LAE + Expenses) / Net Premiums Earned | < 100% = sous-jacent rentable ; 94-98% = excellent | Rapports annuels (Supabase ne cache pas) |
| **Loss Ratio** | Losses incurred / NPE | 60-70% | Idem |
| **Expense Ratio** | Underwriting Expenses / NPE | 25-30% | Idem |
| **Underwriting Margin** | 1 − Combined Ratio | 2-6% | Calculé |
| **Investment Yield** | Investment Income / Avg. Invested Assets | 3-5% (selon mix) | IS + BS |
| **Solvency II Ratio** | Own Funds / SCR | > 150% (cible), > 100% minimum | SFCR (filings EU) |
| **ROE** | Net Income / Equity | 10-15% | IS/BS |
| **Net Premiums Earned** | Calculé IS Supabase | Croissance 3-8% annuelle | IS |
| **Embedded Value / share** (Life) | EV / shares outstanding | — | Rapports annuels |
| **New Business Value** (Life) | — | — | Rapports annuels |

### Sous-catégories

- **P&C** (TRV, PGR, ALL, CB, CS.PA) : Combined Ratio + loss reserves + cat losses.
- **Life / Annuity** (MET, PRU, AFL, ALV.DE) : Embedded Value + MCEV + new business margin.
- **Health** (UNH, ELV, HUM) : Medical Loss Ratio < 85% + membership growth.
- **Reinsurance** (MUV2.DE, HNR1.DE, RNR) : Cycle de pricing + retro cession + cat exposure.
- **Brokers** (MMC, AON, AJG) : **Fee-based — reste en STANDARD**. EV/EBITDA applicable.

### Structure XLSX société recommandée

```
Revenus          ├ Net Premiums Written
                 ├ Net Premiums Earned
                 ├ Investment Income
                 └ Other Income (fees, commissions)
Coûts            ├ Losses + LAE
                 ├ Underwriting Expenses
                 └ Combined Ratio
Résultat         ├ Underwriting Income
                 ├ Investment Income
                 └ Net Income
Bilan            ├ Invested Assets (portefeuille)
                 ├ Loss Reserves
                 ├ Equity
                 └ Embedded Value (Life uniquement)
Ratios           ├ Combined / Loss / Expense
                 ├ ROE, Solvency II
                 └ P/B, P/EV, Div Yield
```

---

## 3. REIT — Foncières cotées

**Tickers concernés** : O, SPG, PLD, AMT, EQR, AVB, DLR, EQIX, WELL ; VNA.DE, KLEP.PA, UNI.PA.

### À retirer

| Métrique standard | Raison |
|---|---|
| Net Income | Biaisé par la D&A des immeubles (forte D&A comptable, mais immeubles ne se déprécient pas vraiment en valeur). |
| EPS | Idem. |
| P/E | Non pertinent — tous les REITs paraissent chers (P/E 30-50x). |
| EV/EBITDA | Possible mais pas standard de marché. |
| DCF classique | La vraie méthode est NAV (Net Asset Value). |

### À ajouter — Valorisation

| Métrique | Formule | Benchmark |
|---|---|---|
| **FFO** (Funds From Operations) | Net Income + D&A + (Losses on Sales) − (Gains on Sales) | Calculé |
| **AFFO** (Adjusted FFO) | FFO − Recurring CapEx − Straight-line Rent − Stock Comp | Calculé (plus proche du cash flow réel) |
| **P/FFO** | Price / FFO per share | 14-22x (selon qualité actifs) |
| **P/AFFO** | Price / AFFO per share | 16-25x |
| **P/NAV** | Price / NAV per share | 0.85-1.15x (décote/prime vs actifs) |
| **Dividend Yield** | Trailing dividends / price | 3-6% |
| **Dividend Coverage** | FFO / Dividends paid | > 1.2x sain |

**Modèle de valorisation** :
- **NAV** : somme des cap rates sectoriels appliqués aux NOI par segment → total asset value − dette → NAV → par action.
- **P/FFO multiple** : ancrer sur moyenne 10 ans sectorielle par sous-secteur.
- **Dividend Discount** : pour REITs matures (Realty Income O), avec g = 3-5%.

### À ajouter — Fondamentaux immobiliers

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **Occupancy Rate** | Leased area / Leasable area | > 92% (bon), > 96% (excellent) | Rapports trimestriels |
| **Same-Store NOI Growth** | NOI LTM (mêmes actifs) YoY | 2-5% | Idem |
| **LTV** (Loan-to-Value) | Net Debt / Asset Value | < 50% | Calculé BS + valuation report |
| **Debt / EBITDA** | Net Debt / EBITDA | 5-7x acceptable | BS/IS |
| **ICR** (Interest Coverage) | EBITDA / Interest | > 3x | IS |
| **Cap Rate** (yield sur actifs) | NOI / Asset Value | 4-7% (selon sous-segment) | Rapports ou calcul |
| **WALT** (Weighted Avg Lease Term) | — | > 5 ans (stabilité) | Rapports |

### Sous-catégories à distinguer

- **Résidentiel** (AVB, EQR, VNA.DE) : WALT court (1 an typique), occupancy 94-96%, NOI growth selon marché locatif.
- **Bureaux** (BXP, SLG, ICAD.PA) : WALT long, occupancy volatile post-COVID.
- **Retail / Mall** (SPG, KIM, MERY.PA) : Risque e-commerce, cycles.
- **Industrial / Logistique** (PLD, DLR, AMT) : occupancy > 95%, croissance forte (e-commerce).
- **Santé** (WELL, VTR, OHI) : triple-net leases, stabilité cash flows.
- **Data Centers** (EQIX, DLR) : capex lourd, growth 10%+, priced sur FFO growth.
- **Cell Towers** (AMT, CCI, SBAC) : contrats longs (15-20 ans), escalators, FFO yield 3-4%.

### Structure XLSX société recommandée

```
Revenus          ├ Rental Income (par segment)
                 ├ Same-Store NOI Growth
                 └ Total Revenue
Coûts            ├ Property Operating Expenses
                 ├ D&A (à neutraliser dans FFO)
                 ├ G&A
                 └ NOI (Net Operating Income)
Résultat         ├ EBITDA
                 ├ Interest Expense
                 ├ FFO = NI + D&A +/− gains/losses
                 ├ AFFO = FFO − recurring CapEx − SL rent
                 └ DPS
Bilan            ├ Gross Asset Value (externe ou cap rate x NOI)
                 ├ Net Debt
                 ├ NAV = GAV − Net Debt − preferred
                 └ NAV / share
Ratios           ├ Occupancy, WALT, NOI growth
                 ├ LTV, Debt/EBITDA, ICR
                 └ P/FFO, P/AFFO, P/NAV, Div Yield
```

---

## 4. UTILITY — Services aux collectivités (régulés)

**Tickers concernés** : NEE, DUK, SO, D, AEP, EXC, SRE, XEL, PEG ; ENGI.PA, EDF.PA, IBE.MC, EOAN.DE, NG.L.

### À retirer

| Métrique standard | Raison |
|---|---|
| ROE classique | Régulé par l'autorité (ROE autorisé ~ 9-10%). Comparer au « allowed ROE ». |
| Marge brute | Le COGS (fuel/purchased power) varie brutalement avec l'énergie. Pas comparable. |
| DCF standard | Remplacé par RAB-based valuation (rate base). |

### À ajouter — Valorisation

| Métrique | Formule | Benchmark |
|---|---|---|
| **P/E** | yfinance.trailingPE | 15-20x |
| **EV/EBITDA** | Fonctionne pour utilities — 8-12x normal |
| **Dividend Yield** | 3-6% (stars retirement / yield plays) |
| **P/RAB** (Regulated Asset Base) | Price / RAB per share | 0.9-1.2x (selon allowed ROE > WACC) |
| **EV/RAB** | EV / RAB | 1.0-1.4x |

**Modèle de valorisation** :
- **Sum-of-the-parts** par juridiction réglementaire : chaque RAB multiplié par le multiple sectoriel régional.
- **RAB growth** = CapEx − Depreciation + Rate cases (augmentations tarifaires).
- **Earned ROE vs Allowed ROE** = indicateur de performance vs régulateur.

### À ajouter — Fondamentaux utilities

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **RAB** (Regulated Asset Base) | Rate base en $ / €. Donnée par la régulation. | — | Rapports annuels + filings régulateurs |
| **RAB Growth** | YoY | 4-8% (croissance saine) | Idem |
| **Allowed ROE** | Défini par la PUC / CRE / Ofgem | 9-10.5% (US), 3.5-5% (UK/EU post-Ofgem RIIO) | Filings régulateurs |
| **Earned ROE** | Net Income / Average Equity | vs Allowed — gap de régulation | IS/BS |
| **Payout Ratio** | DPS / EPS | 60-75% | yfinance |
| **Debt / RAB** | Net Debt / RAB | 50-65% | BS + RAB |
| **FFO / Debt** | Operating CF / Total Debt | 12-18% (S&P investment grade) | CF/BS |
| **Capex / D&A** | Capex / D&A | > 1.5x (croissance), 1.0x (maintenance) | CF/IS |
| **Dividend Coverage** | FCF / Dividends | 1.1-1.3x | CF |
| **Customer Count / Sales Volume** | MWh ou clients | YoY tendance | Rapports |

### Sous-catégories

- **Electric** (DUK, SO, NEE, EDF.PA) : RAB growth + transition énergétique capex.
- **Gas** (SRE, D, ENGI.PA) : Exposition au prix du gaz + pipeline regulation.
- **Water** (AWK, UU.L, VIE.PA) : Taux de renouvellement réseau + contrats de concession.
- **Renewables** (NEE) : Capex très lourd + PPA long-terme.
- **Integrated / Generation** (IBE.MC, EOAN.DE) : Mix regulated vs merchant power — distinguer les deux.

### Structure XLSX société recommandée

```
Revenus          ├ Regulated Revenue
                 ├ Non-Regulated (merchant)
                 └ Total
Coûts            ├ Fuel / Purchased Power
                 ├ OpEx
                 ├ D&A
                 └ EBITDA
Résultat         ├ EBIT, Interest, Net Income
                 └ DPS
Bilan            ├ RAB par juridiction
                 ├ Net Debt, Equity
                 └ FFO, Capex
Ratios           ├ Allowed ROE, Earned ROE, RAB growth
                 ├ Debt/RAB, FFO/Debt, Coverage
                 └ P/E, EV/EBITDA, P/RAB, Div Yield
```

---

## 5. OIL_GAS — Énergie (Upstream E&P + Integrated)

**Tickers concernés** : XOM, CVX, COP, EOG, PXD, OXY, DVN, HES ; SHEL.L, BP.L, TTE.PA, ENI.MI, EQNR.OL, GALP.LS.

**⚠️** Exclut : **refining/marketing** (VLO, MPC), **pipelines** (KMI, ENB.TO), **equipment/services** (SLB, HAL, BKR) → restent en STANDARD.

### À retirer

| Métrique standard | Raison |
|---|---|
| Gross Margin | Volatile avec brut/gaz. Peu comparable. |
| Pur DCF | Possible mais trop sensible aux hypothèses prix. Préférer NAV de réserves. |

### À ajouter — Valorisation

| Métrique | Formule | Benchmark |
|---|---|---|
| **EV/DACF** (Debt-Adjusted Cash Flow) | EV / (Operating CF + after-tax interest) | 4-8x (cycle-dépendant) |
| **EV/EBITDAX** (EBITDA + Exploration Expenses) | EV / EBITDAX | 3-6x |
| **Price / Reserves** (proven 1P) | EV / Reserves (BOE) | $10-20/BOE (US onshore), $5-10/BOE (international) |
| **NAV 1P + 2P + 3P** | Valeur actualisée des réserves probées/probables/possibles | Ancrage principal |
| **EV/Production** (daily) | EV / daily production (BOE/d) | $30k-60k / BOE/d |
| **P/E** | 8-14x (cycle dépendant) |
| **Dividend Yield** | 3-6% (majors) |

**Modèle de valorisation** : **NAV Method** dominant.
- NAV = PV des cash flows de production des réserves 1P à un deck de prix donné (forward strip ou long-term band).
- Integrated majors : SOTP (Upstream NAV + Downstream EV/EBITDA + Chemicals + Trading).
- Aggressive : NAV 2P (proven + probable) avec discount 25-35%.

### À ajouter — Fondamentaux E&P

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **Production** | Daily BOE/d (split oil/gas/NGL) | — | Rapports trimestriels |
| **Réserves 1P** (proved) | fin d'année BOE | R/P > 10 ans = sain | Rapports annuels |
| **Reserve Replacement Ratio** | (Additions − Production) / Production | > 100% sain | Idem |
| **F&D Cost** (Finding & Development) | Capex / Reserve Additions | < $15/BOE | Idem |
| **Cash Cost / BOE** | OpEx + Production costs / BOE produced | < $15/BOE (tier 1) | Idem |
| **Breakeven WTI** (ou Brent) | Prix pétrole pour NPV = 0 | < $40-50/bbl (best in class) | Model externe |
| **Capex / DD&A** | > 1.0x = croissance | Idem | |
| **Net Debt / EBITDAX** | < 1.5x sain, > 2.5x stress | BS/IS |
| **Hedging %** | % production hedgée sur 12 mois | Protection downside | Rapports |

### Sous-catégories

- **Pure E&P Upstream** (EOG, PXD, DVN, HES) : Production growth + reserves + breakeven + FCF yield au current strip.
- **Integrated Majors** (XOM, CVX, SHEL.L, BP.L, TTE.PA, ENI.MI) : SOTP Upstream/Downstream/Chemicals. Dividend sacrosanct.
- **Natural Gas** (RRC, AR, EQT) : Henry Hub sensitivity. LNG exposure.
- **Offshore** (BP, TTE, EQNR) : Mega projects, long tail.

### Structure XLSX société recommandée

```
Opérationnel     ├ Production (BOE/d, splits oil/gas)
                 ├ Réserves 1P / 2P
                 ├ R/P, RRR, F&D
                 └ Cash Cost / BOE
Revenus          ├ Price realized (oil, gas, NGL)
                 ├ Net Revenue
                 └ Hedging gains/losses
Coûts            ├ Production costs
                 ├ Exploration (expensed + capitalized)
                 ├ D&A (volumetric - par BOE)
                 └ EBITDAX
Résultat         ├ EBIT, NI
                 └ FCF + DPS
Bilan            ├ Net Debt
                 ├ Long-lived assets (PPE)
                 └ NAV 1P + 2P
Ratios           ├ EV/DACF, EV/EBITDAX, EV/Production, Price/Reserves
                 ├ Debt/EBITDAX, Capex/DDA, FCF Yield @ current strip
                 └ Breakeven WTI
```

---

## 6. STANDARD — Corporates industriels et services

Profil par défaut. Template actuel déjà adapté. Rappel des sections types :

- EV/EBITDA (8-18x), P/E (15-25x), EV/Revenue (1-5x)
- Marges : Brute (30-60%), EBITDA (15-30%), Nette (5-15%)
- ROE (10-20%), ROIC (vs WACC)
- Debt/EBITDA (< 3x), Interest Coverage (> 5x)
- FCF Yield (> 5%)
- DCF standard à 3 phases (explicit, fade, terminal)

**Sous-profils à distinguer** (non implémentés dans `core/sector_profiles.py` — à ajouter dans `_CONFIGS` en même temps que la refonte XLSX).

---

### 6a. TECH / SaaS

**Tickers** : MSFT, ORCL, CRM, NOW, ADBE, INTU, WDAY, TEAM, SNOW, DDOG, NET, ZS, CRWD, OKTA, ZM, DOCU, HUBS, MDB, ESTC, DBX, ASAN, MNDY.

#### À retirer
- P/E pour sociétés non-profitables (utiliser EV/Revenue et Rule of 40)
- Marge brute < 50% attendue pour SaaS → red flag si c'est le cas (signal de non-SaaS)
- Net Debt/EBITDA (souvent cash-net, ratio non pertinent)

#### Ratios à implémenter

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **EV/Revenue** | EV / Revenue LTM | 5-15x (SaaS mature), 15-30x (hyper-growth) | yfinance |
| **EV/Gross Profit** | EV / (Revenue − COGS) | 8-25x | IS Supabase |
| **Rule of 40** | Rev Growth % + FCF Margin % | > 40 sain, > 60 excellent | Calculé |
| **ARR** (Annual Recurring Revenue) | Subscription Revenue × 4 (trimestriel) | — | Earnings reports |
| **ARR Growth YoY** | — | > 30% (growth), > 15% (mature) | Idem |
| **NRR** (Net Revenue Retention) | (Starting ARR + Expansion − Churn) / Starting ARR | > 110% sain, > 120% excellent | Earnings reports |
| **GRR** (Gross Revenue Retention) | (Starting ARR − Churn) / Starting ARR | > 92% | Idem |
| **Gross Margin** | Gross Profit / Revenue | 70-85% (SaaS), 60-75% (legacy) | IS |
| **FCF Margin** | FCF / Revenue | 20-35% (mature), 0-15% (growth) | CF/IS |
| **Magic Number** | Q-on-Q ARR growth × 4 / S&M spend | > 1.0 efficace, > 1.5 excellent | Calculé |
| **CAC Payback** | CAC / (ARPU × Gross Margin) | < 18 mois B2C, < 24 mois B2B | Calculé |
| **R&D / Revenue** | R&D / Revenue | 15-30% | IS |
| **SBC / Revenue** | Stock-Based Comp / Revenue | 5-15% (sain) ; > 20% = dilutif | CF |
| **LTV / CAC** | Lifetime Value / Customer Acquisition Cost | > 3x | Calculé |

#### Modèle de valorisation
- **EV / NTM Revenue multiple** ancré sur la distribution historique du secteur SaaS (5-15x selon Rule of 40).
- **Fade DCF** (exit multiple method) : modéliser growth fade jusqu'à maturité (~15-20% FCF margin en régime), terminal EV/Revenue ~5x.
- **Reverse DCF** pour tester la croissance implicite pricée.

#### Structure XLSX
```
Top-line       ├ ARR (Subscription Rev x4)
               ├ Non-recurring (Services, Licenses)
               ├ Total Revenue
               └ Revenue Growth %
Métriques SaaS ├ NRR, GRR, Gross Retention
               ├ Logo Churn, Gross Margin
               ├ Magic Number, CAC Payback
               └ Rule of 40
Coûts          ├ COGS (Hosting + Support)
               ├ R&D (% Revenue)
               ├ S&M (% Revenue)
               ├ G&A
               └ SBC (ex- and including)
FCF            ├ Operating CF
               ├ Capex + Capitalized R&D
               └ FCF Margin
Valo           ├ EV/Revenue, EV/Gross Profit
               └ Reverse DCF breakeven growth
```

---

### 6b. RETAIL / CONSUMER DISCRETIONARY + STAPLES

**Tickers** : WMT, COST, HD, LOW, TGT, TJX, ROST, DG, DLTR, BJ, KR, SYY ; KER.PA, HMB.ST, NEXT.L, MKS.L, INDITEX (ITX.MC), ZAL.DE.

#### À retirer
- DCF standard (pas pertinent pour cyclicals retail)
- Free float assumption stable (les marges fluctuent fortement)

#### Ratios à implémenter

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **EV/EBITDA** | yfinance | 8-14x (retail) ; 12-18x (luxury) | yfinance |
| **P/E** | — | 15-22x | yfinance |
| **SSSG / Comp Sales** (LFL) | YoY % same-store growth | > 3% excellent, 0-2% maturité, < 0 alerte | Earnings reports |
| **Traffic × Ticket** | Foot traffic × Avg basket | Décomposition SSSG | Earnings |
| **Gross Margin** | IS | 25-35% (grocery), 40-50% (apparel), 60-70% (luxury) | IS |
| **EBITDA Margin** | IS | 6-10% (grocery), 12-18% (specialty), 20-30% (luxury) | IS |
| **Inventory Turns** | COGS / Avg Inventory | 4-8x (retail), 1-2x (luxury) | IS/BS |
| **Days of Inventory** | 365 / Turns | 45-90 jours | Calculé |
| **GMROI** | Gross Margin $ / Avg Inventory Cost | > $2 de GP par $ d'inventaire | Calculé |
| **Store Count** | Fin d'année | Croissance net adds | Earnings |
| **Revenue / sq ft** | Revenue / Total Leased sq ft | $250-500 (apparel), $500-1000 (grocery dense) | Earnings |
| **Online Mix %** | E-commerce Rev / Total | > 20% tendance saine | Earnings |
| **Lease-Adjusted Debt / EBITDAR** | (Debt + 8×Rent) / EBITDAR | < 4x | BS/IS |
| **Same-Store Gross Margin** | YoY évolution | Stable = pricing power | Earnings |
| **CapEx / Store** | Maintenance + New | < 3% revenue (maintenance) | CF |
| **Div Yield** | — | 2-4% | yfinance |

#### Modèle de valorisation
- **EV/EBITDA multiple** corrélé à SSSG + unit growth.
- **DCF** avec multiple terminal EV/EBITDA (pas Gordon — les cycles sont trop courts).

---

### 6c. PHARMA / BIOTECH

**Tickers Big Pharma** : JNJ, PFE, MRK, ABBV, LLY, BMY, AMGN, GILD ; NVO (Novo), ROG.SW (Roche), NOVN.SW (Novartis), AZN.L, GSK.L, SAN.PA.
**Tickers Biotech** : REGN, VRTX, BIIB, ALNY, MRNA, BNTX, ARGX, EXAS, INCY, ILMN.

#### À retirer pour biotech pré-revenue
- P/E, EV/EBITDA (bénéfices négatifs)
- Marge brute (pas de revenus)

#### Ratios à implémenter (Big Pharma)

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **EV/Revenue NTM** | — | 3-6x | yfinance |
| **P/E** | — | 12-20x | yfinance |
| **Gross Margin** | — | 70-85% | IS |
| **Operating Margin** | — | 20-35% | IS |
| **R&D / Revenue** | — | 15-25% | IS |
| **Pipeline Value (rNPV)** | Σ (Peak Sales × Success Probability × Multiple) | Discloser le top 5-10 | Analyse manuelle + consensus |
| **Patent Cliff Exposure** | % revenus at risk < 5 ans | < 15% sain | Rapports annuels |
| **FCF / Net Income** | — | > 100% (qualité earnings) | CF/IS |
| **Dividend Coverage** | FCF / Dividends | > 1.5x | CF |
| **Payout Ratio** | Div / NI | < 60% | yfinance |
| **Top product concentration** | Top 3 / Total Revenue | < 50% (diversifié) | Rapports |
| **Geographic Mix** | US / EU / ROW | — | Rapports |

#### Ratios à implémenter (Biotech pur)

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **Cash Runway** | Cash / Quarterly Burn | > 2 ans sain | CF/BS |
| **Phase III assets** | Nombre | — | Pipeline rapports |
| **Phase II assets** | Nombre | — | Idem |
| **Milestones unearned** | PV Milestones contractuels | — | Partenariats |
| **Orphan Drug %** | # orphan / total pipeline | — | Pipeline |
| **Peak Sales top asset** | Consensus analystes | — | — |
| **rNPV total pipeline** | Σ (PS × POS × multiple) − Net Debt | Positif | Model |

#### Modèle de valorisation
- **Big Pharma** : DCF base business + rNPV pipeline + multiple de sortie.
- **Biotech** : rNPV pur (pipeline seul si pré-revenue). POS (Probability of Success) par phase : Phase I ~10%, II ~20%, III ~60%, Approved ~90%.

---

### 6d. AIRLINES

**Tickers** : DAL, UAL, AAL, LUV, ALK, JBLU, ALGT, SKYW ; AF.PA, LHA.DE, IAG.MC, RYA.L.

#### À retirer
- EV/EBITDA standard (ignorer les leases d'avions fausse la comparaison)
- Marge brute (pas pertinente — tout est dans OpEx)
- Altman Z (leverage structural élevé)

#### Ratios à implémenter

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **EV/EBITDAR** (R = aircraft Rent) | (EV + 7× annual Rent) / (EBITDA + Rent) | 5-8x | IS + Rent disclosures |
| **CASM ex-fuel** | (OpEx − Fuel) / ASM | 8-12 cents (legacy), 6-9 cents (LCC) | IS |
| **RASM** | Revenue / ASM | 10-16 cents | IS |
| **Load Factor** | Revenue Passenger Miles / ASM | > 80% sain, > 85% excellent | Rapports |
| **ASM Growth** | Available Seat Miles YoY | 3-8% | Rapports |
| **PRASM** | Passenger Revenue / ASM | RASM − cargo | Rapports |
| **Yield** | Passenger Revenue / RPM | $0.10-0.20 | Calculé |
| **Fuel cost / gallon** | — | Hedging % important | Rapports |
| **Stage Length** | Avg distance per flight | Ajustement CASM | Rapports |
| **Labor CASM** | Labor / ASM | 2-4 cents | IS |
| **Fleet Age** | Avg aircraft age | < 15 ans (jeune) | Rapports |
| **Ancillary Revenue %** | Baggage + Fees / Rev | > 10% LCC | Rapports |
| **Operating Margin** | — | 8-15% (normal), négatif en crise | IS |
| **Net Debt / EBITDAR** | — | < 4x | Calculé |
| **Free Cash Flow Yield** | FCF / Market Cap | 5-10% (pre-crise) | CF |

#### Modèle de valorisation
- **EV/EBITDAR multiple** + replacement value du fleet (NBV avions).
- **SOTP** : Passenger + Cargo + Loyalty program (sous-valorisé pour DAL, UAL).
- DCF sensible au prix du fuel → scenario bands low/mid/high.

---

### 6e. METALS & MINING

**Tickers** : BHP.L, RIO.L, FCX, NEM (gold), GOLD (Barrick), WPM (streaming), FNV, FCX, VALE, GLEN.L, ANTO.L, AAL.L.

#### À retirer
- DCF 10-year horizon (préférer mine-by-mine NAV)
- Marge brute stable (cyclique)

#### Ratios à implémenter

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **NAV (par mine)** | PV(production × price − OpEx − Sustain Capex − Taxes) | — | Technical reports |
| **NAV / share** | NAV / diluted shares | — | Calculé |
| **P/NAV** | Price / NAV per share | 0.8-1.2x | Calculé |
| **EV/EBITDA** (spot) | — | 4-7x (cycle-dépendant) | yfinance |
| **AISC** (All-in Sustaining Cost) | OpEx + Royalty + Sustain Capex / oz | Top quartile < $800/oz gold, < $2/lb Cu | Rapports |
| **Reserves 1P** | Fin d'année | R/P > 10 ans | Rapports |
| **Reserves 2P** | 1P + Probable | Upside option | Idem |
| **Resources (M&I + Inferred)** | Blue sky | — | Idem |
| **Grade** | g/t (gold), % (base metals) | Top quartile | Idem |
| **LOM** (Life of Mine) | Annual production × years | > 10 ans | Idem |
| **Production Growth** | YoY | Visibility Critique | Rapports |
| **CapEx / D&A** | — | > 1.0x (replacement) | CF/IS |
| **Net Debt / EBITDA** | — | < 1.5x | BS/IS |
| **Free Cash Flow @ spot** | Current prices × production − cash costs − Capex | Positif = génération | Calculé |
| **Dividend Yield** | — | 3-7% (majors) | yfinance |
| **Royalty Rate** (streamers) | — | Modèle différent | Contracts |
| **Stripping Ratio** (open-pit) | Waste / Ore | < 3:1 excellent | Rapports |

#### Modèle de valorisation
- **NAV par mine** au long-term price deck → somme → diluted NAV/share → `P/NAV` multiple 0.9-1.2x.
- **EV/EBITDA spot** comme cross-check (multiple 4-6x base metals, 6-8x gold).
- Pour **streamers** (FNV, WPM) : NAV des contrats royalty + growth pipeline.

---

### 6f. TELECOM

**Tickers** : VZ, T, TMUS, CMCSA, CHTR, LUMN ; VOD.L, DTE.DE, TEF.MC, ORA.PA, TLSN.ST, TIT.MI.

#### À retirer
- P/E seul (pas pertinent — structure capitale distorts EPS)
- DCF sans modéliser Capex 5G / FTTH explicitement

#### Ratios à implémenter

| Métrique | Formule | Benchmark | Source |
|---|---|---|---|
| **EV/EBITDA** | — | 5-9x | yfinance |
| **Dividend Yield** | — | 4-7% | yfinance |
| **FCF Yield** | FCF / Market Cap | 6-10% | CF |
| **ARPU** (Average Revenue Per User) | Service Revenue / Avg subscribers | $40-60 US post-paid, €15-25 EU | Rapports |
| **ARPU Growth** | YoY | +1-3% sain | Idem |
| **Subscriber Base** | Total post-paid + pre-paid | — | Rapports |
| **Net Adds** | Trimestriel post-paid | Positif = part de marché | Rapports |
| **Churn** | Disconnections / Avg base | < 1% monthly post-paid | Rapports |
| **Capex / Revenue** | — | 15-22% (5G/FTTH cycle) | CF/IS |
| **EBITDA Margin** | — | 30-40% | IS |
| **Net Debt / EBITDA** | — | 2.5-3.5x (investment grade) | BS/IS |
| **Payout Ratio** | Div / FCF | 60-90% | Calculé |
| **Service Revenue %** | Service / Total Revenue | > 85% (ex-équipement) | Rapports |
| **FTTH Coverage %** | Households passed / Total | Tendance | Rapports |
| **Spectrum Holdings** | MHz-PoP | Valeur d'actif cachée | Auctions / filings |
| **Interest Coverage** | EBITDA / Interest | > 4x | IS |

#### Modèle de valorisation
- **EV/EBITDA** multiple 5-8x selon croissance + capex intensity.
- **DCF** avec capex 5G/FTTH modélisé explicitement (pic capex → free cash flow rebound).
- **Dividend support** : tester si le current dividend est couvert par FCF ajusté capex maintenance.

---

---

## Annexe — Chantier XLSX : checklist d'implémentation

### Étape 1 : Identifier le profil à la génération
- `core/sector_profiles.detect_profile(sector, industry)` retourne le profil
- À appeler dans `outputs/excel_writer.py` (analyse société) et `outputs/screening_writer.py` (XLSX secteur)

### Étape 2 : Templates XLSX par profil
Créer un template par profil (au lieu d'un seul `TEMPLATE.xlsx`) :
- `TEMPLATE_STANDARD.xlsx` (existant)
- `TEMPLATE_BANK.xlsx`
- `TEMPLATE_INSURANCE.xlsx`
- `TEMPLATE_REIT.xlsx`
- `TEMPLATE_UTILITY.xlsx`
- `TEMPLATE_OIL_GAS.xlsx`

### Étape 3 : Routage à la génération
Dans `ExcelWriter.generate` :
```python
profile = detect_profile(sector, industry)
template_path = TEMPLATES[profile]  # dict profile → template path
wb = openpyxl.load_workbook(template_path)
self._fill_cells_for_profile(wb, state, profile)
```

### Étape 4 : Cell mapping par profil
Chaque profil a sa propre grille de cellules (FORMULA_CELLS restent protégées) :
- `_BANK_CELLS` : où mettre NIM, CET1, NPL, ROE, P/TBV, Cost/Income
- `_REIT_CELLS` : où mettre FFO, AFFO, Occupancy, NAV, LTV
- etc.

### Étape 5 : Data chain enrichissement
Compléter `compute_ticker` / `fetch_node` pour récupérer les métriques spécifiques :
- **CET1/NPL** : scraper filings via Supabase (non yfinance — filings bancaires US Y-9C, EU Pillar 3)
- **Combined Ratio** : rapports annuels assureurs
- **FFO** : calcul depuis Net Income + D&A (déjà faisable avec IS/BS/CF Supabase)
- **NAV** : externe (reporters ou calcul avec cap rate assumption)
- **RAB** : filings régulateurs
- **Réserves / production** : rapports annuels upstream

Pour les métriques non disponibles dans yfinance ou Supabase, placeholder + pull manuel ou source externe (à définir).

---

**Priorité d'implémentation suggérée** :
1. **BANK** (plus fréquent, plus large gap vs standard)
2. **REIT** (2ème plus grande valeur ajoutée utilisateur)
3. **INSURANCE**
4. **UTILITY**
5. **OIL_GAS**
6. **TECH / SaaS** (important pour couvrir MSFT, ORCL, SNOW, DDOG sans distorsion)
7. **RETAIL / STAPLES** (WMT, COST, INDITEX)
8. **PHARMA** (JNJ, LLY, ROG.SW)
9. **AIRLINES** (DAL, UAL, RYA.L)
10. **METALS** (BHP.L, RIO.L, FCX)
11. **TELECOM** (VZ, DTE.DE, ORA.PA)

Baptiste gère l'indice XLSX lui-même. Ce document couvre **société** + **secteur**.

---

## Placement dans les onglets XLSX — mapping actionnable

Pour chaque profil, voici où placer les ratios dans un template XLSX typique (INPUT, RATIOS, DCF, COMPARABLES, SCENARIOS, DASHBOARD) :

### Onglet `INPUT` — données source
- **Tous profils** : IS + BS + CF historiques (5 ans), market data (price, shares, beta)
- **BANK** ajoute : NII split, provisions, CET1, NPL, RWA, Tier 1 capital
- **INSURANCE** ajoute : NPW, NPE, Losses, Expenses, Invested Assets, Solvency II
- **REIT** ajoute : NOI par segment, Cap Rate assumptions, Recurring Capex, Occupancy
- **UTILITY** ajoute : RAB par juridiction, Allowed ROE, Rate Base Growth, Capex plan
- **OIL_GAS** ajoute : Production (BOE/d), Réserves 1P/2P/3P, Cash cost/BOE, Hedging
- **TECH/SaaS** ajoute : ARR, NRR, GRR, S&M, R&D capitalized, Gross Retention
- **RETAIL** ajoute : SSSG, Store count, Revenue/sq ft, Online mix, Inventory days
- **PHARMA** ajoute : Pipeline par phase, Peak sales, Patent cliff, Top 5 products split
- **AIRLINES** ajoute : ASM, RPM, Load Factor, Fuel cost, Fleet age, Aircraft rent
- **METALS** ajoute : Production par métal, Grade, Reserves, AISC, LOM
- **TELECOM** ajoute : Subscribers, ARPU, Churn, Capex/Revenue split

### Onglet `RATIOS` — calculs dérivés (formules)
- **Tous** : Growth rates, Marges, ROE/ROIC (si applicable)
- **BANK** : NIM, Cost/Income, ROA, Loan/Deposit, P/TBV, P/PPOP
- **INSURANCE** : Combined / Loss / Expense ratios, UW Margin, Inv Yield
- **REIT** : FFO = NI + D&A, AFFO = FFO − Recurring Capex − SL Rent, P/FFO, P/NAV, LTV
- **UTILITY** : Earned ROE vs Allowed, Debt/RAB, FFO/Debt, Capex/D&A
- **OIL_GAS** : EV/DACF, EV/EBITDAX, EV/Production, Price/Reserves, Breakeven, F&D
- **TECH** : Rule of 40, EV/Revenue, EV/GP, CAC Payback, Magic Number
- **RETAIL** : SSSG components (traffic × ticket), GMROI, Inventory Turns
- **PHARMA** : R&D/Rev, Pipeline rNPV, Peak sales concentration
- **AIRLINES** : CASM ex-fuel, RASM, PRASM, EV/EBITDAR, Load Factor
- **METALS** : AISC per unit, NAV per mine, Production growth, P/NAV
- **TELECOM** : ARPU, Churn, Capex intensity, Net Debt/EBITDA

### Onglet `DCF` — valorisation principale
- **STANDARD / TECH / RETAIL / PHARMA / AIRLINES / TELECOM** : DCF 3-phases classique (FCF → WACC → Terminal)
- **BANK** : DDM (Gordon Growth) ou Justified P/B à partir du ROE durable — **pas de DCF**
- **INSURANCE (P&C)** : Multiple P/B ancré ROE — P&C simplifié
- **INSURANCE (Life)** : Embedded Value + NBV margin
- **REIT** : NAV par segment (cap rate × NOI) + dette = NAV/share — **remplace DCF**
- **UTILITY** : SOTP RAB × multiple régulatoire (remplace DCF)
- **OIL_GAS** : NAV 1P + 2P par price deck (remplace DCF)
- **METALS** : NAV par mine (remplace DCF) + cross-check EV/EBITDA spot

### Onglet `COMPARABLES` — pairs trading
- **STANDARD** : Ticker | Rev | Growth | Marges | EV/EBITDA | P/E | EV/Rev | ROE
- **BANK** : Ticker | Rev | Growth | ROE | P/E | P/TBV | Div Yield | CET1 | NPL | Cost/Income
- **INSURANCE** : Ticker | NPE | Growth | Combined Ratio | P/B | P/E | Div Yield | Solvency II
- **REIT** : Ticker | FFO | Growth | P/FFO | P/AFFO | P/NAV | Div Yield | Occupancy | LTV
- **UTILITY** : Ticker | Rev | RAB growth | EV/EBITDA | P/E | P/RAB | Div Yield | Allowed vs Earned ROE
- **OIL_GAS** : Ticker | Production | Reserves | EV/DACF | EV/EBITDAX | Price/Reserves | Breakeven
- **TECH** : Ticker | Rev | Growth | Gross Mg | Rule of 40 | EV/Rev | EV/GP | NRR | FCF Margin
- **RETAIL** : Ticker | Rev | SSSG | Gross Mg | EV/EBITDA | P/E | Store count | Div Yield
- **PHARMA** : Ticker | Rev | Growth | Op Margin | EV/Rev | P/E | R&D/Rev | Pipeline size | Div Yield
- **AIRLINES** : Ticker | ASM growth | RASM | CASM ex-fuel | Load Factor | EV/EBITDAR | Fleet age
- **METALS** : Ticker | Production | Reserves | AISC | P/NAV | EV/EBITDA | Div Yield | Net Debt/EBITDA
- **TELECOM** : Ticker | Rev | Subs | ARPU | Churn | EV/EBITDA | FCF Yield | Div Yield | Net Debt/EBITDA

### Onglet `SCENARIOS` — Bull / Base / Bear
Toujours 3 scenarios. Paramètres-clé par profil :
- **STANDARD** : Revenue growth ± 2pts, EBITDA margin ± 2pts, exit multiple ± 2x
- **BANK** : NIM ± 20bps, Cost/Income ± 5pts, NPL provisions ± 50bps, ROE ± 2pts
- **INSURANCE** : Combined Ratio ± 3pts, Investment Yield ± 50bps
- **REIT** : Cap Rate ± 50bps, Same-Store NOI growth ± 1pt, Occupancy ± 2pts
- **UTILITY** : Allowed ROE ± 50bps, Rate case timing ± 1 an, Capex plan ± 10%
- **OIL_GAS** : Oil price $60/$75/$90, Production ± 5%, Hedging 30/60%
- **TECH / SaaS** : NRR ± 5pts, Revenue growth ± 10pts, Rule of 40 ± 10
- **RETAIL** : SSSG ± 2pts, Gross Margin ± 1pt, Store count growth
- **PHARMA** : Pipeline success rate (POS) ± 20%, Peak sales ± 25%, Patent timing
- **AIRLINES** : Fuel cost ± $1/gal, Load Factor ± 3pts, Fare pricing ± 5%
- **METALS** : Commodity price ± 20%, AISC ± 10%, Production ± 5%
- **TELECOM** : ARPU ± 5%, Churn ± 50bps, Capex ± 2pts of revenue

### Onglet `DASHBOARD` — synthèse exécutive
- **Tous profils** : Prix cible | Upside | Conviction | Rating | Top 3 KPIs du profil | Chart secteur vs S&P

Top 3 KPIs par profil à afficher en dashboard :
- **STANDARD** : EV/EBITDA + FCF Yield + ROIC
- **BANK** : P/TBV + ROE + CET1
- **INSURANCE** : P/B + Combined Ratio + Solvency II
- **REIT** : P/NAV + Occupancy + FFO Growth
- **UTILITY** : P/RAB + Earned ROE + RAB Growth
- **OIL_GAS** : EV/DACF + Breakeven WTI + Reserve Life
- **TECH** : EV/Rev + Rule of 40 + NRR
- **RETAIL** : EV/EBITDA + SSSG + Inventory Turns
- **PHARMA** : EV/Rev NTM + R&D/Rev + Pipeline rNPV
- **AIRLINES** : EV/EBITDAR + CASM ex-fuel + Load Factor
- **METALS** : P/NAV + AISC + Reserve Life
- **TELECOM** : EV/EBITDA + FCF Yield + ARPU Growth
