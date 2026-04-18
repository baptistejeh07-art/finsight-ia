# FinSight IA — Déploiement Next.js + FastAPI (v2, finsight-ia.com)

Ce guide déploie la nouvelle stack :
- **Frontend** Next.js 16 sur **Vercel** (domaine `finsight-ia.com`)
- **Backend** FastAPI Python sur **Railway** (ou Render/Fly en alternative)
- **Auth + DB** Supabase (déjà configuré dans l'app Streamlit — on réutilise)

L'app Streamlit existante (`app.py`) reste en parallèle sur Streamlit Cloud et n'est pas affectée.

---

## 1. Backend — Railway

### 1.1 Compte + projet
1. Créer un compte sur [railway.app](https://railway.app) (Free tier : 500h/mois, $5 crédit).
2. Dans le dashboard → **New Project** → **Deploy from GitHub repo** → sélectionner `finsight-ia`.
3. Quand Railway demande le root directory, mettre **`backend`**.

### 1.2 Variables d'environnement
Dans l'onglet **Variables** du service, ajouter :

```
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GROQ_API_KEY_2=gsk_...        (optionnel, rotation)
GEMINI_API_KEY=...
MISTRAL_API_KEY=...
FINNHUB_API_KEY=...
FMP_API_KEY=...                (optionnel)
SUPABASE_URL=https://<projet>.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc... (service_role)
PYTHONUNBUFFERED=1
TRANSFORMERS_OFFLINE=1
IS_CLOUD=true
```

### 1.3 Commande de démarrage
Le `Procfile` définit :
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
Railway détecte ça automatiquement. Confirmer dans **Settings > Deploy**.

### 1.4 Healthcheck
Le JSON `railway.json` pointe `/health`. Vérifier dans **Settings > Deploy > Healthcheck Path** : `/health`.

### 1.5 Déployer
- Railway build le repo (~4-8 min la première fois : installe yfinance, openpyxl, reportlab, scipy…).
- Une fois deployed, Railway fournit une URL type : `https://finsight-ia-production.up.railway.app`.
- **Garder cette URL** — on la met côté frontend.

### 1.6 Test
```bash
curl https://<URL-railway>/health
# → {"status":"ok","service":"finsight-api",...}

curl https://<URL-railway>/resolve/AAPL
# → {"query":"AAPL","kind":"societe","ticker":"AAPL",...}
```

---

## 2. Frontend — Vercel

### 2.1 Déploiement
1. [vercel.com](https://vercel.com) → **Import Git Repository** → `finsight-ia`.
2. **Framework Preset** : Next.js (auto-détecté).
3. **Root Directory** : `frontend` (important).
4. **Build Command** : `next build` (par défaut).
5. **Output Directory** : `.next` (par défaut).

### 2.2 Variables d'environnement (Vercel)
Dans **Settings > Environment Variables** :

```
NEXT_PUBLIC_API_URL=https://<URL-railway>
NEXT_PUBLIC_SUPABASE_URL=https://<projet>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...
```

Redéployer une fois les vars ajoutées (Vercel ne les réinjecte pas automatiquement sur le build déjà fait).

### 2.3 Domaine custom finsight-ia.com
1. Dans Vercel → **Settings > Domains > Add** → `finsight-ia.com` + `www.finsight-ia.com`.
2. Vercel affiche les enregistrements DNS requis :
   - `A @ 76.76.21.21`
   - `CNAME www cname.vercel-dns.com`
3. Aller chez le registrar (OVH/Gandi/Google Domains) → zone DNS → créer ces records.
4. Retour sur Vercel → attendre propagation (15 min à 24h) → cadenas SSL auto (Let's Encrypt).

### 2.4 Test
- Ouvrir `https://finsight-ia.com` → homepage Bloomberg-style doit s'afficher.
- Cliquer "Analyser" avec ticker AAPL → page /analyse → redirection /resultats.

---

## 3. Supabase (Auth)

L'app Streamlit utilise déjà Supabase Auth. Rien à changer côté DB. Vérifier simplement :

### 3.1 URL Auth redirect
Dans Supabase → **Authentication > URL Configuration** :
- Site URL : `https://finsight-ia.com`
- Redirect URLs (whitelist) : ajouter
  ```
  https://finsight-ia.com/**
  https://www.finsight-ia.com/**
  https://*.vercel.app/**
  http://localhost:3000/**
  ```

### 3.2 Google OAuth (si activé)
- Dans Google Cloud Console → OAuth 2.0 Client ID → **Authorized redirect URIs** : ajouter
  `https://<projet>.supabase.co/auth/v1/callback`
- Supabase s'occupe du reste.

---

## 4. DNS — récapitulatif pour finsight-ia.com

Chez le registrar (probablement OVH vu la TLD française), zone DNS :

```
Type   Nom  Valeur                    TTL
A      @    76.76.21.21               3600
CNAME  www  cname.vercel-dns.com      3600
```

Éventuellement pour emails (plus tard) :
```
MX     @    aspmx.l.google.com        3600     (si Google Workspace)
TXT    @    v=spf1 include:_spf.google.com ~all
```

---

## 5. Mises à jour continues

Le CI est automatique : chaque push sur `master` redéploie Vercel + Railway.

- Frontend : ~1 min build.
- Backend : ~4 min (à cause des deps Python lourdes). Peut être optimisé avec Docker caching.

---

## 6. Coûts indicatifs (MVP nuit)

| Service  | Free tier                 | Upgrade si trafic |
|----------|---------------------------|-------------------|
| Vercel   | 100 GB bande passante    | Pro $20/mois      |
| Railway  | $5 crédit/mois + 500h    | Hobby $5/mois actifs |
| Supabase | 500 MB DB + 50k MAU      | Pro $25/mois      |
| Domaine  | ~10€/an (OVH/Gandi)      | —                 |

Total MVP : **< 20€/mois** pour démarrer.

---

## 7. Limitations connues V1 (à corriger V2)

- **Sync blocking** : l'endpoint `/analyze/societe` reste bloquant 1-3 min. Si frontend ferme l'onglet → analyse perdue. V2 → queue Celery/Redis + WebSocket pour progress temps réel.
- **Pas de rate limiting** : endpoints publics exposés. Ajouter `slowapi` en V2.
- **Pas de persistence historique** : `/history` retourne liste vide. V2 → table Supabase `analyses` avec row par user+ticker+date.
- **Fichiers stockés sur Railway local** : un redéploiement = perte des PDF/PPTX générés. V2 → Supabase Storage ou S3.

---

## 8. Quick test end-to-end local (avant deploy)

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
# .env.local avec NEXT_PUBLIC_API_URL=http://localhost:8000 + Supabase
npm run dev

# Browser
open http://localhost:3000
# Tester : saisir AAPL → Analyser → doit afficher le résultat après ~60-120s
```
