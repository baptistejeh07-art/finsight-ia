# Métriques sectorielles — Référence refonte XLSX

Document de référence pour la refonte des templates XLSX société et secteur par profil métier. Chaque profil liste :

- **Ce qu'il faut RETIRER** du template standard (EV/EBITDA, marges brutes, etc.) parce que non applicable ou trompeur.
- **Ce qu'il faut AJOUTER** avec les benchmarks (fourchettes typiques).
- **Le modèle de valorisation** à utiliser à la place du DCF générique.
- **Sources de données** : yfinance (`.info`), statements Supabase (IS/BS/CF), filings externes quand nécessaire.

Le profil est détecté automatiquement via `core/sector_profiles.detect_profile(sector, industry)`. La liste des constantes est dans `core/sector_profiles.py` : `STANDARD`, `BANK`, `INSURANCE`, `REIT`, `UTILITY`, `OIL_GAS`.

Contenu actuellement implémenté dans le code : les ratios par profil sont définis dans `_CONFIGS` dans `core/sector_profiles.py` et utilisés par `sector_pdf_writer` + `indice_pdf_writer`. Les writers XLSX ne les utilisent **pas encore** — c'est l'objet du chantier de refonte Baptiste.

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

**Sous-profils à éventuellement distinguer** (non implémentés dans `core/sector_profiles.py` — à ajouter si besoin) :

### 6a. TECH / SaaS
- **Rule of 40** = Revenue Growth % + EBITDA Margin % (cible > 40)
- **ARR** (Annual Recurring Revenue), **NRR** (Net Revenue Retention) > 110%
- **Gross Retention** > 92%
- **CAC Payback** < 18 mois
- **Magic Number** (ARR growth / S&M spend)
- Valorisation : EV/Revenue (5-15x) ou EV/Gross Profit quand gross margin très élevée

### 6b. RETAIL / CONSUMER STAPLES
- **Same-Store Sales Growth** (SSSG / LFL)
- **Inventory Turns**
- **GMROI** (Gross Margin Return on Inventory)
- **Store Count + Expansion Pipeline**
- **Online Mix %**
- Valorisation : EV/EBITDA (10-15x), P/E (15-25x), Div Yield (2-4%)

### 6c. PHARMA / BIOTECH
- **Pipeline** : nombre de candidats par phase (Phase I/II/III/Approved)
- **Peak Sales Estimate** par produit
- **R&D / Revenue** (> 15%)
- **Patent Cliff** : expiry dates des top produits
- **IRR par produit** (rNPV probability-adjusted)
- Valorisation : rNPV pipeline (probability-weighted) + residual value base business. DCF classique possible sur base business.

### 6d. AIRLINES
- **CASM** (Cost per Available Seat Mile, ex-fuel)
- **RASM** (Revenue per ASM)
- **Load Factor** (> 80%)
- **Capacity (ASM) growth**
- **Fuel cost / gallon hedged**
- Valorisation : EV/EBITDAR (R = Rent pour leases avions) — 5-8x

### 6e. METALS & MINING
- **Production volumes** par métal
- **All-In Sustaining Cost** (AISC) / unit
- **Proven & Probable Reserves** + grade
- **LOM** (Life of Mine)
- Valorisation : NAV discount (0.8-1.2x NAV), EV/EBITDA cyclique (4-8x), Dividend Yield

### 6f. TELECOM
- **ARPU** (Average Revenue per User)
- **Subscriber Base** + Net Adds
- **Churn** (< 15% annualisé B2C)
- **Capex / Revenue** (> 15% = 5G investment)
- **FCF Yield** (6-10%)
- Valorisation : EV/EBITDA (5-8x), Dividend Yield (4-6%)

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
6. Sous-profils tech/biotech/airlines (optionnel)

Baptiste gère l'indice XLSX lui-même. Ce document couvre **société** + **secteur**.
