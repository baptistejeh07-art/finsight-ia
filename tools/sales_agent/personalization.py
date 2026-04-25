# -*- coding: utf-8 -*-
"""tools/sales_agent/personalization.py — Génère un DM LinkedIn et un PDF
démo personnalisé pour un prospect qualifié.

Le DM suit le template validé par Baptiste :
- Hook : référence à un post récent du prospect (factuel/question/observation)
- Pitch : 2-3 phrases FinSight + chiffre dur (Score backtest +8.9% alpha)
- PJ : analyse FinSight du ticker que le prospect a mentionné
- CTA soft : « ton avis » (zero commitment, 3× meilleur taux réponse)
- Mention Early Backer 20€/mois à vie en mode info

Anti-ban : variabilité forcée — le LLM tire 1 hook style sur 3 (factuel,
question ouverte, partage observation) au hasard pour qu'aucun DM ne soit
identique à un autre. Ne génère jamais 2 DM en parallèle pour 2 prospects
sur le même ticker — diversité préservée.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


_HOOK_STYLES = (
    ("factuel",
      "Démarre par une observation factuelle sur le post du prospect "
      "(« J'ai vu ton analyse sur X — ton angle sur Y est juste »)"),
    ("question",
      "Démarre par une question ouverte qui rebondit sur son post "
      "(« Ton point sur X m'a fait penser — comment tu vois Y ? »)"),
    ("partage",
      "Démarre par un partage : « ton post sur X m'a fait sortir mon "
      "analyse sur le même sujet, je te la partage »"),
)


@dataclass
class PersonalizationResult:
    dm_text: str                  # DM rédigé prêt à envoyer (~150 mots)
    pdf_demo_path: Optional[str]  # chemin local du PDF démo généré
    hook_style: str               # factuel | question | partage
    target_ticker: Optional[str]


def generate_dm(
    prospect_name: str,
    prospect_headline: str,
    prospect_recent_post: Optional[str],
    target_ticker: Optional[str],
) -> str:
    """Rédige un DM LinkedIn personnalisé (~140-160 mots).

    Le LLM tire un style de hook au hasard pour la variabilité. Si pas de
    post récent fourni, on tombe sur un hook générique (« J'ai vu ton
    profil… ») moins puissant mais utilisable.
    """
    style_id, style_desc = random.choice(_HOOK_STYLES)
    log.info(f"[perso] hook style tiré : {style_id}")

    post_block = ""
    if prospect_recent_post:
        post_block = (
            f"\nPost récent du prospect (à utiliser pour le hook) :\n"
            f"« {prospect_recent_post[:500]} »\n"
        )

    ticker_block = ""
    if target_ticker:
        ticker_block = (
            f"\nTicker pertinent à mentionner : {target_ticker} "
            f"(je joindrai au DM une analyse FinSight de ce ticker)"
        )

    prompt = (
        f"Tu écris un DM LinkedIn pour le compte de Baptiste, fondateur de "
        f"FinSight IA (plateforme d'analyse financière niveau institutionnel "
        f"pour particuliers). L'objectif est d'avoir un retour, pas de "
        f"vendre frontalement.\n\n"
        f"PROSPECT\n"
        f"Nom : {prospect_name}\n"
        f"Headline : {prospect_headline}\n"
        f"{post_block}{ticker_block}\n\n"
        f"INSTRUCTIONS\n"
        f"Style de hook à utiliser : {style_id} — {style_desc}\n\n"
        f"Structure obligatoire (140-160 mots total) :\n"
        f"1. Salutation perso avec prénom (« Bonjour {prospect_name.split()[0] if prospect_name else 'Prénom'} »)\n"
        f"2. Hook (1-2 phrases) selon le style ci-dessus\n"
        f"3. Pitch FinSight (2-3 phrases) : « Je construis FinSight, "
        f"analyses financières niveau sell-side générées en 2 minutes. "
        f"Score propriétaire backtesté +8.9% alpha sur 10 ans (t=2.10). »\n"
        f"4. PJ : « Je te joins l'analyse {target_ticker if target_ticker else 'du ticker que tu suis'} "
        f"que j'ai sortie ce matin. 15-20 pages, rien de magique — le "
        f"workflow buy-side en 2 min. »\n"
        f"5. CTA soft : « J'aimerais ton avis sur la lecture. Pas de vente, "
        f"juste vérifier si c'est utile à quelqu'un qui stock-pick "
        f"sérieusement. »\n"
        f"6. Mention Early Backer (1 phrase, ton décontracté, pas pushy) : "
        f"« Si tu aimes, je lance une Early Backer fin de semaine prochaine "
        f"— 20€/mois à vie, 10 places. Sinon ton feedback vaut déjà le "
        f"coup. »\n"
        f"7. Signature : « Baptiste »\n\n"
        f"RÈGLES\n"
        f"- Pas de markdown (LinkedIn ne rend pas)\n"
        f"- Pas de URL (LinkedIn pénalise les liens dans DM)\n"
        f"- Pas de jargon corporate (« nous proposons », « notre solution »)\n"
        f"- Ton humble, comme un fondateur solo qui demande un avis\n"
        f"- Français avec accents complets\n\n"
        f"Rédige uniquement le DM, rien d'autre. Pas de préambule type "
        f"« Voici le DM » ou de note de bas de page."
    )

    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="anthropic",
                            model="claude-sonnet-4-5-20250929")
        raw = llm.generate(prompt,
                             system="Tu es un copywriter sales B2C sobre.",
                             max_tokens=500)
    except Exception as e:
        log.warning(f"[perso] anthropic échec, fallback mistral : {e}")
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral", model="mistral-small-latest")
        raw = llm.generate(prompt,
                             system="Copywriter sales B2C sobre.",
                             max_tokens=500)

    return (raw or "").strip()


def generate_pdf_demo(ticker: str, timeout_sec: int = 180) -> Optional[str]:
    """Lance audit.py --preview pour générer le PDF démo personnalisé.

    Le PDF arrive dans `preview/{TICKER}/{TICKER}_report.pdf`. Retourne le
    chemin absolu si succès, None si échec.

    Note : ne JAMAIS lancer ça en parallèle pour 10 prospects sur le même
    ticker — un seul appel suffit, on cache le résultat. Pour 10 prospects
    avec 10 tickers différents, chaque preview prend 2-3 min, donc il
    vaut mieux les lancer en background séquentiel pour ne pas saturer
    Mistral/Anthropic.
    """
    if not ticker:
        return None
    import subprocess
    import sys
    repo_root = Path(__file__).resolve().parent.parent.parent
    preview_dir = repo_root / "preview" / ticker
    pdf_path = preview_dir / f"{ticker}_report.pdf"
    # Cache : si le PDF existe déjà et a moins de 24h, on le réutilise
    if pdf_path.exists():
        import time
        age_sec = time.time() - pdf_path.stat().st_mtime
        if age_sec < 24 * 3600:
            log.info(f"[perso] PDF démo {ticker} cache hit ({int(age_sec/3600)}h old)")
            return str(pdf_path)
    log.info(f"[perso] génération PDF démo {ticker}…")
    try:
        r = subprocess.run(
            [sys.executable, "tools/audit.py", "--preview", ticker],
            cwd=str(repo_root),
            capture_output=True,
            timeout=timeout_sec,
            text=True,
        )
        if pdf_path.exists():
            log.info(f"[perso] PDF démo {ticker} OK : {pdf_path}")
            return str(pdf_path)
        log.warning(f"[perso] PDF démo {ticker} non généré (rc={r.returncode}) : "
                    f"{(r.stderr or r.stdout)[-300:]}")
        return None
    except subprocess.TimeoutExpired:
        log.warning(f"[perso] PDF démo {ticker} timeout après {timeout_sec}s")
        return None
    except Exception as e:
        log.warning(f"[perso] PDF démo {ticker} exception : {e}")
        return None


def personalize_prospect(
    name: str,
    headline: str,
    recent_post: Optional[str],
    target_ticker: Optional[str],
    generate_pdf: bool = True,
) -> PersonalizationResult:
    """Pipeline complet : DM + PDF démo. À appeler par le backend pour
    chaque prospect du top 10 quotidien.
    """
    style_id = random.choice(_HOOK_STYLES)[0]
    dm_text = generate_dm(name, headline, recent_post, target_ticker)
    pdf_path = None
    if generate_pdf and target_ticker:
        pdf_path = generate_pdf_demo(target_ticker)
    return PersonalizationResult(
        dm_text=dm_text,
        pdf_demo_path=pdf_path,
        hook_style=style_id,
        target_ticker=target_ticker,
    )


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    res = personalize_prospect(
        name="Pierre Dupont",
        headline="Ingénieur informatique · Investisseur PEA depuis 8 ans",
        recent_post=("Schneider Electric (SU.PA) reste un de mes top picks. "
                      "P/E 30x peut sembler cher mais le ROIC 18% justifie."),
        target_ticker="SU.PA",
        generate_pdf=False,  # skip PDF en test rapide
    )
    print("=" * 60)
    print(res.dm_text)
    print("=" * 60)
    print(f"hook_style: {res.hook_style}")
    print(f"target_ticker: {res.target_ticker}")
    print(f"pdf_demo_path: {res.pdf_demo_path}")
