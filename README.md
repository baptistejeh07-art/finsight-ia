# FinSight IA

> **Votre propre analyste, où que vous soyez, quand vous en avez besoin.**

FinSight IA est une plateforme d'analyse financière institutionnelle propulsée par
l'intelligence artificielle. Elle produit, à partir d'un ticker boursier, d'un
secteur ou d'un indice, des analyses complètes incluant valorisation DCF, ratios
financiers, scénarios bull/base/bear, comparables, et livrables professionnels
(PDF, PowerPoint, Excel) — le tout en quelques minutes.

🌐 **Production** : [finsight-ia.com](https://finsight-ia.com)

---

## ✨ Fonctionnalités

### Analyses
- **Société** : DCF complet, ratios sur 5 ans, comparables sectoriels, scénarios, devil's advocate
- **Secteur** : screening multi-factoriel (Value/Growth/Quality/Momentum), top performers
- **Indice** : ERP, allocation optimale (Markowitz), valorisations agrégées
- **Comparatif** : benchmark côte à côte de 2 sociétés
- **Portrait d'entreprise** (V1) : rapport qualitatif 15 pages avec photos dirigeants Wikipedia

### Livrables
- **PDF** : rapport ~20 pages format Bloomberg-grade
- **PowerPoint** : pitchbook 20 slides éditoriales
- **Excel** : modèle DCF complet, comparables, sensibilités, dashboards

### Plateforme
- Conversation **Q&A** contextuelle sur chaque analyse (LLM avec accès au state complet)
- **Authentification** Google OAuth + email/password (Supabase)
- **Mode édition** dashboard (Ctrl+Alt+E) : drag & drop des blocs (V1 visuel, V2 fonctionnel)
- **Monitoring** admin avec timings par node, providers LLM, warnings audit
- **Site vitrine** complet style Anthropic : Hero, méga-menus, tarification, FAQ, Méthodologie, Sécurité

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Frontend (Vercel)                     │
│  Next.js 16 + React 19 + Tailwind + shadcn + framer     │
│  finsight-ia.com / admin / api routes Q&A & vitrine     │
└──────────────────┬───────────────────────────────────────┘
                   │ REST + SSE
┌──────────────────▼───────────────────────────────────────┐
│                  Backend (Railway)                       │
│  FastAPI + LangGraph + Pydantic + jobstore mémoire+DB   │
│  finsight-ia-production.up.railway.app                  │
└──────────────────┬───────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────┐
│         Pipeline 7 agents (LangGraph)                    │
│  fetch → quant → synthesis → qa → entry_zone → output   │
│         ↑                                                │
│         AgentDataAudit (warnings post-pipeline)         │
└──────────────────┬───────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────┐
│   Sources & LLM    │   Storage           │  Cache       │
│   yfinance / FMP   │   Supabase Storage  │  yfinance    │
│   Finnhub / FRED   │   PostgreSQL        │  15 min TTL  │
│   Wikipedia        │   - analyses_history│              │
│   Groq / Mistral   │   - jobs_state      │              │
│   Anthropic Haiku  │                     │              │
│   Gemini Flash     │                     │              │
└──────────────────────────────────────────────────────────┘
```

### Pipeline 7 agents (LangGraph)
1. **AgentData** — yfinance + Finnhub + FMP (fallback en cascade) + sentiment FinBERT
2. **AgentQuant** — DCF, WACC, ratios déterministes (Python pur, jamais LLM)
3. **AgentSynthese** — LLM avec cascade Groq → Mistral → Cerebras → Anthropic
4. **AgentQA** — vérifications croisées Python + Haiku
5. **AgentDevil** — thèse inverse, ajuste la conviction
6. **AgentEntryZone** — 5 conditions techniques satisfaites (signaux d'achat)
7. **OutputWriters** — Excel + PPTX + PDF en parallèle (ThreadPool×3)

### Gouvernance V2
- Constitution stricte (7 articles)
- ChromaDB pour mémoire vectorielle
- 4 agents observateurs (verdict ALERTES si violation)

---

## 🚀 Installation locale

### Prérequis
- Python 3.12+
- Node.js 20+
- Compte Supabase (free tier OK)
- Clés API : Groq, Mistral, Anthropic (au moins une)

### Backend

```bash
git clone https://github.com/baptistejeh07-art/finsight-ia.git
cd finsight-ia

# Env Python
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configuration .env (copier .env.example)
cp .env.example .env
# → renseigner GROQ_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY,
#   SUPABASE_URL, SUPABASE_SERVICE_KEY

# Lancer le backend FastAPI
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Configuration .env.local
cp .env.local.example .env.local
# → renseigner NEXT_PUBLIC_API_URL=http://localhost:8000
#   et NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY

npm run dev
# → http://localhost:3000
```

### Tables Supabase (one-shot)

```sql
-- Historique d'analyses (déjà existant)
CREATE TABLE IF NOT EXISTS analyses_history (...);

-- Persistance jobstore (fix bug 404 zombie après restart Railway)
CREATE TABLE IF NOT EXISTS jobs_state (
    job_id      uuid PRIMARY KEY,
    kind        text NOT NULL,
    status      text NOT NULL,
    progress    int DEFAULT 0,
    user_id     text,
    label       text,
    created_at  timestamptz DEFAULT now(),
    started_at  timestamptz,
    finished_at timestamptz,
    result      jsonb,
    error       text
);
CREATE INDEX idx_jobs_state_created ON jobs_state (created_at DESC);
```

---

## 📊 Performance

Cible : **analyse société < 90 secondes**

Optimisations en place :
- ✅ Pipeline parallélisé (fetch_node, output_node, comparables, sector_data, indice_data)
- ✅ Fail-fast Groq sur 429 (gain ~45s/analyse)
- ✅ PDF DPI 110 (au lieu de 180, gain ~40s)
- ✅ Cache yfinance 15 min (gain 10-30s répétée)
- ✅ Pré-warming Railway au mount /app (gain ~30s cold start)

Mesuré sur AAPL (post-fixes) : ~70-90s.

---

## 🔐 Sécurité

- Hébergement intégralement UE (Vercel Frankfurt + Railway Amsterdam + Supabase Frankfurt)
- TLS 1.3 + AES-256 at-rest
- Aucune donnée client utilisée pour entraîner les modèles
- Sous-traitants listés publiquement : [/securite](https://finsight-ia.com/securite)
- RGPD by design : [/privacy](https://finsight-ia.com/privacy)

---

## 📝 Disclaimer

FinSight IA fournit un **outil d'aide à l'analyse**, et **non un conseil en
investissement personnalisé** au sens de l'article L.321-1 du code monétaire et
financier. L'utilisateur reste seul juge de ses décisions et assume entièrement
les risques associés. Voir [/disclaimer](https://finsight-ia.com/disclaimer).

---

## 👤 Créateur

**Baptiste Jehanno** — étudiant en BTS Comptabilité & Gestion en alternance,
diplômé du FMVA (Financial Modeling & Valuation Analyst, CFI), en préparation
du CFA niveau I.

Entrepreneur individuel (micro-entreprise) — SIREN 101 364 859 — Toulouse.

---

## 🛣️ Roadmap

### Q2 2026
- Portrait d'entreprise via Pappers V2 (sociétés non cotées)
- Streaming LLM responses (SSE)
- Mode édition V2 : drag & drop fonctionnel + persistance Supabase

### Courant 2026
- Comptes utilisateurs persistants + watchlists
- API publique (pay-per-use)
- Connecteurs Pennylane, Sage, FEC

### Fin 2026
- Score FinSight propriétaire (note composite qualité/valorisation/momentum/gouvernance)
- White-label complet pour Enterprise

---

## 📜 Licence

Code source propriétaire. Tous droits réservés © 2026 FinSight IA.

Sources tierces utilisées dans le respect de leurs CGU respectives :
yfinance (Yahoo), Finnhub, FMP, FRED, EDGAR, Wikipedia, Damodaran, FinBERT,
Anthropic, Groq, Mistral.
