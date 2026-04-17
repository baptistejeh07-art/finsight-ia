# Relance Claude Code dans le projet finsight-ia (nightly run)
# Lancé par Task Scheduler Windows toutes les 2h

$ErrorActionPreference = "Continue"
$logDir = "C:\Users\bapti\finsight-ia\logs\nightly"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "relaunch_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Ajoute npm bin dir au PATH (claude code est installé via npm)
$env:PATH = "$env:APPDATA\npm;$env:PATH"

Set-Location "C:\Users\bapti\finsight-ia"

"=== Relance Claude $(Get-Date) ===" | Out-File -FilePath $logFile -Append

# Le prompt de reprise — donne le contexte complet pour reprendre où on en était
$prompt = @"
NUIT DU 17/04 AU 18/04 - REPRISE AUTONOME.

Contexte : Baptiste m'a confié la migration Streamlit -> Next.js + FastAPI
pendant qu'il dort. Le domaine finsight-ia.com a été acheté.

Plan général :
1. backend/ FastAPI : wrap toutes les fonctions cli_analyze (societe,
   secteur, indice, comparatifs) en endpoints REST. Reuse 100% du code
   Python existant (agents, writers, currency).
2. frontend/ Next.js : MVP avec auth Supabase + 3-5 pages (home, analyse,
   resultats, comparatif). UI Bloomberg-style + branding navy/logo.
3. Streamlit reste fonctionnel en parallele (pas touche).
4. CGU + Privacy Policy templates.

Cycle 30min travail / 30min repos via ScheduleWakeup.

Reprend OU tu en etais. Verifie commits recents + memoire pour contexte.
Continue jusqu'a terminer ou que Baptiste te dise stop au matin.
"@

# Lance Claude Code en mode dangereux (skip permissions) avec le prompt
try {
    & claude --dangerously-skip-permissions -p $prompt 2>&1 | Tee-Object -FilePath $logFile -Append
    "=== Fin run a $(Get-Date) ===" | Out-File -FilePath $logFile -Append
} catch {
    "ERREUR: $_" | Out-File -FilePath $logFile -Append
}
