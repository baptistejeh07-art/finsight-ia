# FinSight IA — Guide de déploiement Streamlit Community Cloud

## Prérequis

- Compte GitHub (repo public ou privé)
- Compte Streamlit Community Cloud : share.streamlit.io
- Clés API : Anthropic, Groq, Finnhub, FMP

---

## Étape 1 — Préparer le repo GitHub

```bash
# Initialiser git si pas encore fait
cd ~/finsight-ia
git init
git add .
git commit -m "Initial commit — FinSight IA"

# Vérifier que les secrets ne sont PAS dans le commit
git status   # .env et .streamlit/secrets.toml doivent être absents

# Pousser sur GitHub
git remote add origin https://github.com/<user>/finsight-ia.git
git push -u origin main
```

**Vérification critique avant push :**
```bash
git ls-files | grep -E "\.env$|secrets\.toml"
# Doit retourner VIDE — si non, vérifier .gitignore
```

---

## Étape 2 — TEMPLATE.xlsx (Excel)

Le fichier `TEMPLATE.xlsx` est sur OneDrive et **ne peut pas être uploadé sur SCC** tel quel.

**Option A — Inclure dans le repo** (recommandé) :
```bash
mkdir -p assets
cp "C:/Users/bapti/OneDrive/Perso/Excel Finsight/TEMPLATE.xlsx" assets/
git add assets/TEMPLATE.xlsx
git commit -m "Add Excel template"
```
Puis dans Secrets SCC : `TEMPLATE_PATH = "assets/TEMPLATE.xlsx"`

**Option B — Désactiver Excel en cloud** :
L'ExcelWriter est wrappé dans un try/except dans `output_node` — si le template est absent,
l'Excel est simplement non généré. Le PPTX et PDF fonctionnent sans template.

---

## Étape 3 — Déployer sur Streamlit Community Cloud

1. Aller sur **share.streamlit.io**
2. Cliquer **New app**
3. Sélectionner le repo GitHub `finsight-ia`
4. Branch : `main` | Main file path : `app.py`
5. Cliquer **Advanced settings** → Python version : **3.11** (recommandé)
6. Cliquer **Deploy**

---

## Étape 4 — Configurer les Secrets

Dans l'app déployée : **⋮ > Settings > Secrets**

Coller le contenu suivant (remplacer les valeurs) :

```toml
ANTHROPIC_API_KEY  = "sk-ant-api03-..."
GROQ_API_KEY       = "gsk_..."
FINNHUB_API_KEY    = "..."
FMP_API_KEY        = "..."
TEMPLATE_PATH      = "assets/TEMPLATE.xlsx"
IS_CLOUD           = "true"
```

> Les secrets sont chiffrés par Streamlit et injectés dans `os.environ`
> via `core/secrets.py` au démarrage de l'app.

---

## Étape 5 — Vérifier le déploiement

Une fois déployé, vérifier dans les logs Streamlit :
```
[Secrets] X cle(s) injectee(s) depuis st.secrets
```

Tester sur un ticker simple : `AAPL` ou `TSLA`

---

## Limitations connues en cloud (free tier)

| Fonctionnalité | Local | Cloud SCC |
|---|---|---|
| FinBERT sentiment | Oui (torch local) | **Non** — fallback Finnhub news |
| Redis cache | Oui | **Non** — pas de cache |
| ChromaDB / Gouvernance | Oui | **Non** — logs V2 désactivés |
| Ollama (LLM local) | Oui | **Non** — Groq/Anthropic API |
| Excel (TEMPLATE.xlsx) | Oui (OneDrive) | Oui si `assets/TEMPLATE.xlsx` présent |
| PPTX / PDF | Oui | Oui |

**RAM free tier : 1GB** — torch (~700MB) est exclu de `requirements.txt` pour éviter OOM.
Utiliser `requirements-local.txt` en développement local.

---

## Variables d'environnement — référence complète

| Variable | Requis | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Oui | Claude Haiku (synthèse, QA) |
| `GROQ_API_KEY` | Oui | Fallback LLM (Llama 3.3) |
| `FINNHUB_API_KEY` | Oui | News + métriques |
| `FMP_API_KEY` | Non | Source EU (403 sur free plan) |
| `GEMINI_API_KEY` | Non | Backup LLM |
| `SUPABASE_URL` | Non | Logs DB (fallback JSON si absent) |
| `SUPABASE_SECRET_KEY` | Non | Logs DB |
| `TEMPLATE_PATH` | Non | Chemin TEMPLATE.xlsx (Excel) |
| `IS_CLOUD` | Non | Flag détection cloud |
| `TRANSFORMERS_OFFLINE` | Non | FinBERT offline mode (local) |

---

## Mise à jour en production

```bash
git add -A
git commit -m "feat: ..."
git push origin main
# Streamlit Community Cloud redéploie automatiquement
```
