# Changelog

## [Unreleased] — Avril 2026

### ✨ Features

- **Portrait d'entreprise V1** : rapport qualitatif PDF 15 pages avec photos
  dirigeants Wikipedia, pipeline LLM cascade Groq → Mistral → Anthropic
- **Site vitrine complet** style Anthropic : Hero, méga-menus, tarification 3 onglets,
  FAQ, footer multi-colonnes, animations typewriter + flottement mockups
- **Pages institutionnelles** : Méthodologie, Sécurité & conformité, Mentions légales,
  CGU, Privacy, Disclaimer, Collaboration, Cas d'utilisation
- **Auth Google OAuth** complet via Supabase
- **Mode édition** dashboard (Ctrl+Alt+E) : V1 visuelle (bordures + nom de bloc)
- **Page admin /admin/monitoring** : timing par node, provider LLM utilisé, warnings
- **Writer XLSX énergie** : template scoring multi-factoriel pour secteur Énergie
- **AgentDataAudit** : warnings post-pipeline si data critique manquante (encart
  jaune dans /resultats)

### ⚡ Performance

- **Cache yfinance 15 min** TTL via `core/yfinance_cache` (gain -10 à -30s répétée)
- **Pré-warming Railway** au mount /app (gain -30s cold start)
- **Fail-fast Groq sur 429** : retry [5,15,30]→[1.5], gain ~45s/analyse société
- **PDFWriter DPI 110** (au lieu de 180) : gain ~40s sur output_node
- **Persistance jobstore Supabase** : jobs survivent aux restarts Railway (table
  `jobs_state`)
- **Zombie jobs timeout** : status='running' depuis >10min auto-marqué error

### 🐛 Bug fixes

- **sessionStorage QuotaExceeded** sur Tesla/indices riches → try fallback sans
  raw_data + skip + redirect quand même
- **Logo flou footer** : SVG vectorisé VTracer (~600 nuances anti-aliasées) →
  PNG hi-res 2x dédié (logo-finsight-2x.png + logo-finsight-white-2x.png)
- **Markdown `**`** non converti dans PDF Portrait → fonction `_md_to_html`
- **Sauts de page injustifiés** Portrait → flow naturel ReportLab + `KeepTogether`
- **Photos dirigeants manquantes** Portrait → max_kb 500→2500, conversion PIL pour
  formats exotiques (WebP/AVIF)
- **Box valorisation déborde** sous graph cours → limitée à largeur col Reco
- **Citation Buffett dans sidebar /app** → retirée
- **Alt+E ne marche pas** sur Windows (conflit menu Chrome) → capture+stopPropagation
  + Ctrl+Alt+E + e.code === 'KeyE'
- **Titre 'Base 100'** incohérent avec valeurs affichées → renommé 'Performance comparée'

### 🎨 UI

- Logo PNG vrai-transparent (cropped + alpha=0 sur pixels blancs)
- Sidebar /app logo h-24 (vraie taille)
- Sources cliquables footer /app (yfinance, FMP, Finnhub…)
- Traduction FR secteurs (Consumer Defensive → Consommation défensive, etc.)
- Page /app : `min-h-screen` + footer sous le fold (visible au scroll)
- Glossaire refondu en tabs catégories (Valorisation/Rentabilité/Structure/Risque)

### 🏗️ Backend

- Endpoint `/admin/monitoring` : breakdown timings + providers + warnings
- Endpoint `/portrait/societe` async + writer dédié
- Instrumentation timings par writer (excel_ms, pptx_ms, pdf_ms) dans output_node
- Synthesis logs : provider utilisé + ms par essai + providers échoués
- Multi-clés Groq (rotation existante GROQ_API_KEY_1, GROQ_API_KEY_2…)

### 📚 Documentation

- README.md complet
- CHANGELOG.md (ce fichier)
- Inline docs dans tous les nouveaux modules (`core/portrait/`, `core/data_audit.py`,
  `outputs/sector_energy_xlsx_writer.py`, `frontend/src/components/edit-mode-provider.tsx`)

---

## [Initial Release] — Mars-Avril 2026

- Migration Streamlit → Next.js + FastAPI
- Pipeline 7 agents LangGraph (fetch, quant, synthesis, qa, devil, entry_zone, output)
- Constitution V2 + 4 agents observateurs
- 3 livrables : PDF (ReportLab), PPTX (python-pptx), XLSX (openpyxl)
- Domaine finsight-ia.com (Namecheap + Vercel + Railway + Supabase)
- Auth Supabase email/password
