# Migration 002 : Bucket Supabase Storage `analyses`

À configurer manuellement dans le dashboard Supabase Storage :
https://supabase.com/dashboard/project/ugmqiawmszffqgtvsghz/storage/buckets

## Étapes

1. **New bucket** → nom : `analyses` (default si la var `SUPABASE_BUCKET` n'est pas définie côté Railway)
2. **Public bucket** : ✅ activé (pour que les URLs publiques fonctionnent sans token)
3. (Optionnel) **File size limit** : 50 MB (PDF/PPTX/XLSX rarement > 5 MB)
4. (Optionnel) **Allowed MIME types** : laisser vide pour accepter PDF/PPTX/XLSX

## Variable d'environnement

Si vous voulez un nom de bucket différent, ajouter sur Railway :
```
SUPABASE_BUCKET=mon_bucket_perso
```

## Comment ça marche côté backend

À chaque job done (`/analyze/societe`, `/analyze/secteur`, etc.) :
1. Les fichiers sont générés localement dans `outputs/generated/cli_tests/`
2. `_upload_files_to_storage()` les upload vers `analyses/{kind}/{stem}_{timestamp}.{ext}`
3. La réponse contient les URLs publiques Supabase au lieu des chemins relatifs
4. Le frontend télécharge directement depuis Supabase (CDN, persistant après redeploy Railway)

Si Storage non configuré (clé manquante / bucket inexistant), le backend retombe
sur les chemins relatifs locaux + endpoint `/file/{path}` (comportement V1).
