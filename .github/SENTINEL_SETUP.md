# Sentinel Auto-Fix — Setup (5 min, action one-shot)

Architecture : quand le sentinel détecte un bug en prod
(`pipeline_errors` severity error/critical/warn-récurrent), il déclenche
un workflow GitHub Actions qui spawn un agent Claude Code en mode
headless. Cet agent lit le contexte du bug, modifie le code, lance les
tests, commit et push avec préfixe `[sentinel-auto]`.

## 1. Créer un GitHub Personal Access Token (1 min)

Le sentinel a besoin de pouvoir déclencher des workflows via l'API
GitHub `repository_dispatch`. Tu crées un PAT (Personal Access Token)
classique avec un seul scope : `repo`.

1. Va sur **<https://github.com/settings/tokens/new>**
2. **Note** : "FinSight Sentinel Dispatch"
3. **Expiration** : 1 an (renouvellement annuel acceptable)
4. **Scopes cochés** :
   - `repo` (suffit, donne accès aux dispatches + lecture du repo)
5. Clique "Generate token"
6. **Copie immédiatement le token** (il commence par `ghp_...`) — tu ne pourras plus le revoir.

## 2. Ajouter le PAT dans Railway (1 min)

1. Va sur **<https://railway.com/project/cb440b10-9c69-4555-8f9e-1a667ec7b2a9/service/0a7fdac0-3840-4a88-86c7-07d7464d298f/variables>**
2. Bouton "+ New Variable"
3. **Name** : `GITHUB_DISPATCH_TOKEN`
4. **Value** : `ghp_...` (le token de l'étape 1)
5. Save → Railway redéploie automatiquement (~2 min)

(Optionnel) Ajoute aussi `GITHUB_REPO=baptistejeh07-art/finsight-ia` si
ton repo change de nom — sinon le default codé dans
`core/sentinel/github_dispatch.py` suffit.

## 3. Ajouter les secrets dans GitHub Actions (2 min)

Le workflow `.github/workflows/sentinel-fix.yml` a besoin de :
- `ANTHROPIC_API_KEY` : pour faire tourner Claude Code en CI
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` : pour marquer la ligne
  `pipeline_errors` comme traitée à la fin du run

1. Va sur **<https://github.com/baptistejeh07-art/finsight-ia/settings/secrets/actions>**
2. Pour chacun des 3 secrets : "New repository secret"
   - **`ANTHROPIC_API_KEY`** : ta clé `sk-ant-api03-...` standard (NE PAS
     utiliser le token OAuth claude.ai/code, c'est pas le même format).
     Si tu n'en as pas, génère sur <https://console.anthropic.com/settings/keys>.
   - **`SUPABASE_URL`** : copie depuis Railway (déjà configurée là-bas)
     → typiquement `https://ugmqiawmszffqgtvsghz.supabase.co`
   - **`SUPABASE_SERVICE_KEY`** : copie aussi depuis Railway, c'est la
     `service_role` key qui commence par `eyJh...`

## 4. Tester le pipeline complet (1 min)

Une fois Railway redéployé après l'étape 2 :

```bash
# Test 1 : le dispatch lui-même (sans déclencher Claude Code)
curl -X POST https://api.github.com/repos/baptistejeh07-art/finsight-ia/dispatches \
  -H "Authorization: Bearer ghp_TON_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"sentinel-error","client_payload":{"test":true,"error_type":"manual_test","ticker":"DEBUG"}}'
# Réponse attendue : 204 No Content (pas de body)
```

→ Va sur <https://github.com/baptistejeh07-art/finsight-ia/actions> :
tu dois voir un nouveau run "Sentinel Auto-Fix" en cours.

```bash
# Test 2 : depuis le sentinel applicatif (via /admin/sentinel/test)
# Tu peux le lancer depuis Chrome console sur finsight-ia.com/app :
fetch('https://finsight-ia-production.up.railway.app/admin/sentinel/test?severity=error', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer ' + (
    JSON.parse(atob(
      document.cookie.split('sb-ugmqiawmszffqgtvsghz-auth-token.0=')[1]
        .split(';')[0].replace('base64-', '')
    )).access_token
  )}
}).then(r => r.json()).then(console.log)
```

→ Tu dois voir le row_id en console + un nouveau run GitHub Actions
qui démarre dans les 30s.

## 5. Surveiller les runs

- **UI Actions** : <https://github.com/baptistejeh07-art/finsight-ia/actions>
  filtre par workflow "Sentinel Auto-Fix"
- **Artifact** : chaque run upload `claude-output.log` en artifact
  conservé 30 jours, pour voir ce que Claude a réfléchi/fait
- **Commits** : préfixe `[sentinel-auto]` pour les fix appliqués,
  `[sentinel-investigation]` quand Claude n'est pas confiant et écrit
  juste un fichier de diagnostic

## Sécurité — limites du workflow

Le workflow est volontairement contraint :
- `--allowedTools` ne liste QUE Read/Write/Edit/Glob/Grep + Bash limité
  à `python *`, `git status`, `git diff`, `git log`. Pas de `git push --force`,
  pas de `rm -rf`, pas de modif `.env` ou secrets.
- `concurrency: cancel-in-progress` empêche 5 runs parallèles sur le
  même bug si le sentinel re-fire avant que le 1er finisse.
- `timeout-minutes: 25` cap dur en cas de boucle.
- Pré-commit hook (`test_core.py`) bloque les commits qui cassent les tests.

## Désactivation temporaire

Si tu veux désactiver le sentinel auto-fix :
- **Soft kill** : supprime `GITHUB_DISPATCH_TOKEN` de Railway env →
  le sentinel continue à enregistrer les bugs, mais ne lance plus le
  workflow. Le canal email Resend continue de marcher.
- **Hard kill** : désactive le workflow dans GitHub
  (Actions → Sentinel Auto-Fix → "..." → Disable workflow)

## Coûts

- **Anthropic API** : ~$0.05-0.15 par run Sonnet 4.6 (selon longueur du fix).
  À 5-10 runs/jour = $0.5-1.5/jour = ~$15-45/mois.
- **GitHub Actions minutes** : ~5 min par run × 10/jour = 50 min/jour =
  1500 min/mois → bien dans la quota gratuite (2000 min/mois sur public
  repos, 3000 sur plan pro).
- **Mistral / Resend / Supabase** : déjà couverts par ton stack actuelle.
