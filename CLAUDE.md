# FinSight IA — Instructions Claude Code

## Règles absolues
- **Toujours committer ET pusher** après chaque modification (app déployée sur Streamlit Cloud)
- Ne jamais écraser les cellules formule dans excel_writer.py (double garde : FORMULA_CELLS + startswith("="))
- Terminal Windows cp1252 — pas de caractères Unicode dans les print() des scripts

## Commandes clés
```bash
# Analyse complète d'une société
python cli_analyze.py société AAPL

# Analyse secteur / indice
python cli_analyze.py secteur Technology "S&P 500"
python cli_analyze.py indice Technology "CAC 40"

# Rendu visuel des outputs (PDF + PPTX + Excel)
python tools/render_outputs.py AAPL
python tools/render_outputs.py AAPL --only xlsx --sheet INPUT

# Audit complet autonome (analyse + render + rapport)
python tools/audit.py AAPL
python tools/audit.py AAPL MSFT MC.PA TSLA NVDA

# Lancer l'app Streamlit (local)
streamlit run app.py
```

## Architecture pipeline
```
cli_analyze.py → core/graph.py (LangGraph, 7 noeuds)
  ├── fetch_node    : AgentData (yfinance + Finnhub + FMP fallback)
  ├── quant_node    : AgentQuant (WACC, DCF, ratios déterministes)
  ├── synthesis_node: AgentSynthese (Groq llama-3.3-70b → fallback Anthropic haiku)
  ├── qa_node       : AgentQAPython + AgentQAHaiku
  ├── devil_node    : AgentDevil (thèse inverse, conviction_delta)
  └── output_node   : ExcelWriter + PPTXWriter + PDFWriter
```

## Outputs générés
Tous dans `outputs/generated/cli_tests/` :
- `{TICKER}_report.pdf`       — rapport PDF ReportLab (9 pages)
- `{TICKER}_pitchbook.pptx`   — pitchbook PowerPoint (20 slides)
- `{TICKER}_financials.xlsx`  — template Excel injecté
- `{TICKER}_briefing.txt`     — briefing texte
- `{TICKER}_state.json`       — state complet du pipeline

Renders visuels dans `outputs/generated/cli_tests/renders/{TICKER}/` :
- `pdf/pdf_page_XX.png`
- `pptx/slide_XX.png`
- `xlsx/xlsx_{SHEET}_pXX.png`

## Providers LLM (priorité)
1. **Groq** llama-3.3-70b-versatile (principal, rapide, gratuit)
2. **Anthropic** claude-haiku-4-5-20251001 (fallback synthèse)
- Groq 401 → vérifier console.groq.com (quota mensuel)
- Anthropic désactivé par choix (clé non rechargée)

## Sources données (priorité)
1. **yfinance** — principal, 5 ans max, gratuit
2. **FMP** — fallback, souvent 401/403 free plan
3. **Finnhub** — news ticker-spécifiques (10 articles)
4. **RSS feedparser** — backup news (Yahoo Finance feed)

## Excel — colonnes (v4, alignement DROITE)
- H=le plus récent (LTM), G=N-1, F=N-2, E=N-3, D=N-4 — H TOUJOURS rempli
- 5 ans : D,E,F,G,H | 4 ans : E,F,G,H (D vide) | 3 ans : F,G,H (D,E vides)
- `_build_year_col` : right-align, reversed(labels), cols[4-i]
- D5-H5 : etiquettes d'année écrites directement comme valeurs (ex: 2022, "2025 (LTM)")
- D132-H132 : helpers backup (hors zone impression)
- D117 = ltm_year = année du label le plus récent (toujours H)
- Market data (beta, WACC inputs) : colonne de l'année la plus récente uniquement
- FORMULA_CELLS : ne jamais écrire dedans

## Notes Python 3.14
- supabase incompatible → fallback JSON local dans logs/local/
- TRANSFORMERS_OFFLINE=1 dans .env (FinBERT déjà téléchargé)
- FMP free plan : 403 sur EU, 401 sur US → yfinance prend le relais
- Supabase 401 → normal, log local seulement

## Render visuel Excel (tools/render_outputs.py)
- Zip cleanup obligatoire : supprime charts, drawings, refs dans Content_Types + sheet XMLs
- `CorruptLoad=1` (xlRepairFile) pour Excel COM
- Feuilles disponibles : INPUT, RATIOS, DCF, COMPARABLES, SCENARIOS, DASHBOARD, DASHBOARD 2
