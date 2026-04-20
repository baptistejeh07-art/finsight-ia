# FinSight IA — Extension Chrome

Ajoute un bouton **"📊 Analyser avec FinSight"** sur les pages ticker de 7 sites financiers majeurs :

- Yahoo Finance
- TradingView
- Boursorama
- Google Finance
- Morningstar
- Investing.com
- Zonebourse

Clic → nouvel onglet `finsight-ia.com/app` avec le ticker pré-rempli.

## Fichiers

- `manifest.json` — Manifest v3 (MV3)
- `content.js` — content script (détection ticker + injection bouton)
- `content.css` — styles du bouton flottant
- `background.js` — service worker minimal
- `popup.html` — popup au clic sur l'icône de l'extension
- `icons/` — 16/48/128 PNG

## Développement local

1. Chrome → `chrome://extensions/`
2. Activer "Mode développeur" (haut droite)
3. Cliquer "Charger l'extension non empaquetée"
4. Sélectionner ce dossier `extension/`
5. L'icône apparaît dans la barre d'outils

Tester sur :
- https://finance.yahoo.com/quote/AAPL
- https://www.tradingview.com/symbols/NASDAQ-AAPL/
- https://www.boursorama.com/cours/1rPMC (LVMH)
- https://www.google.com/finance/quote/AAPL:NASDAQ

## Publication Chrome Web Store

1. Zip le dossier `extension/` (sans le README ni les fichiers de dev)
2. Chrome Web Store Developer Dashboard : https://chrome.google.com/webstore/devconsole
3. Coût dev account : **5 USD one-time**
4. Remplir le formulaire :
   - Screenshots 1280×800 (au moins 1 image sur chaque site supporté)
   - Description courte (132 chars max)
   - Description longue (16000 chars max)
   - Catégorie : "Productivity" ou "Shopping" → prendre **Productivity**
   - Langues : fr, en
   - Privacy policy URL : https://finsight-ia.com/privacy
5. Review Google : 3-7 jours
6. Après publication : URL `chrome.google.com/webstore/detail/...`

## Icons à générer

Placer 3 PNG dans `icons/` :
- `icon-16.png` (16×16)
- `icon-48.png` (48×48)
- `icon-128.png` (128×128)

Utiliser le logo FinSight existant (`frontend/public/icon.png`).

## Version

1.0.0 — Initial release.
