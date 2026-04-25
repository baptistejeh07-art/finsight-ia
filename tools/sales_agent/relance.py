# -*- coding: utf-8 -*-
"""tools/sales_agent/relance.py — Relances J+3 et J+7 automatiques.

Logique : un prospect "sent" depuis ≥ 3 jours sans réponse est candidat à
relance J+3. Si toujours pas de réponse 7 jours après le DM initial,
relance J+7. Au-delà → ghosted (auto-cleanup).

Le texte de la relance utilise un angle DIFFÉRENT du DM initial (sinon
le prospect le voit comme spam) :
- J+3 : « j'ai oublié de te demander » + question ouverte ciblée
- J+7 : « dernier ping » + offre asymétrique (« si pas pour toi, dis-le
  moi, je te promets ne plus te rebondir »)

Variabilité forcée comme pour le DM initial : 2 styles tirés random.

Anti-ban : ces relances comptent dans le cap 15 DM/jour. Si Baptiste en
a déjà 12 nouveaux + 5 relances à envoyer, il dépasse → on alerte sur
le dashboard.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from tools.sales_agent.tracking import _supabase_creds, _headers

log = logging.getLogger(__name__)


_RELANCE_3_STYLES = (
    ("question_ouverte",
      "Démarre par « J'ai oublié de te demander : » et pose une question "
      "ouverte ciblée sur le ticker analysé (ex: « comment tu vois la "
      "guidance pour Q4 ? »). Pas de ré-pitch, juste curiosité."),
    ("partage_observation",
      "Démarre par « Je suis tombé sur ça aujourd'hui, ça m'a fait penser "
      "à ton analyse » et partage une observation ou une donnée nouvelle "
      "(ex: insider buying, dépréciation goodwill, concurrent news). "
      "Donne d'abord, demande ensuite."),
)

_RELANCE_7_STYLES = (
    ("offre_asymetrique",
      "« Dernier ping de ma part. Si FinSight n'est pas pour toi, "
      "réponds-moi juste 'pas le bon timing' et je te promets de ne pas "
      "te rebondir. Sinon je te garde une des 10 places Early Backer "
      "encore une semaine. » Ton humble, ne pas relancer après."),
    ("compliment_decision",
      "Reconnaît qu'il n'a pas répondu (« je comprends que tu n'aies pas "
      "eu le temps »), affirme que tu respectes son choix, et relance "
      "sur un angle ROI concret (« le seul truc que je voulais vraiment "
      "te montrer c'est X — voilà la version 1 minute »)."),
)


def find_pending_relances() -> dict:
    """Identifie les prospects qui devraient recevoir une relance.

    Retourne {prospects_to_relance_3: [...], prospects_to_relance_7: [...]}
    où chaque entrée est un row Supabase avec joint sur sales_prospects.
    """
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return {"prospects_to_relance_3": [], "prospects_to_relance_7": []}
    now = datetime.now(timezone.utc)
    cutoff_3 = (now - timedelta(days=3)).isoformat()
    cutoff_7 = (now - timedelta(days=7)).isoformat()
    cutoff_recent = (now - timedelta(days=2, hours=22)).isoformat()
    try:
        # Tous les status "sent" et qui ont pas encore reçu de relance_1
        r = httpx.get(
            f"{surl}/rest/v1/sales_prospect_status",
            headers=_headers(skey),
            params={
                "status": "eq.sent",
                "select": "*,sales_prospects(*)",
                "limit": "100",
            },
            timeout=8.0,
        )
        rows = r.json() if r.status_code < 300 else []
        relance_3, relance_7 = [], []
        for row in rows:
            sent_at = row.get("sent_at")
            if not sent_at:
                continue
            try:
                sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            age_days = (now - sent_dt).days
            r1_sent = bool(row.get("relance_1_sent_at"))
            r2_sent = bool(row.get("relance_2_sent_at"))
            # J+3 : si pas encore de relance_1 et ≥ 3 jours
            if age_days >= 3 and not r1_sent:
                relance_3.append(row)
            # J+7 : si relance_1 déjà envoyée et ≥ 4 jours après (donc ~7j
            # après le DM initial), pas encore de relance_2
            elif r1_sent and not r2_sent:
                r1_dt_str = row.get("relance_1_sent_at")
                if r1_dt_str:
                    try:
                        r1_dt = datetime.fromisoformat(
                            r1_dt_str.replace("Z", "+00:00"))
                        if (now - r1_dt).days >= 4:
                            relance_7.append(row)
                    except ValueError:
                        pass
        log.info(f"[sales/relance] {len(relance_3)} J+3, {len(relance_7)} J+7")
        return {
            "prospects_to_relance_3": relance_3,
            "prospects_to_relance_7": relance_7,
        }
    except Exception as e:
        log.warning(f"[sales/relance] find_pending : {e}")
        return {"prospects_to_relance_3": [], "prospects_to_relance_7": []}


def generate_relance_text(
    prospect_name: str,
    prospect_headline: str,
    initial_dm: str,
    target_ticker: Optional[str],
    relance_type: str,  # "J3" ou "J7"
) -> str:
    """Rédige le texte d'une relance via Claude. Style tiré au hasard pour
    la variabilité (anti pattern detection)."""
    if relance_type == "J3":
        styles = _RELANCE_3_STYLES
        max_words = 80
    else:
        styles = _RELANCE_7_STYLES
        max_words = 90
    style_id, style_desc = random.choice(styles)

    prompt = (
        f"Tu écris une relance LinkedIn ({relance_type} = {'3 jours' if relance_type == 'J3' else '7 jours'} "
        f"après le DM initial). Aucune réponse encore. La relance doit "
        f"être courte ({max_words} mots max) et utiliser un angle DIFFÉRENT "
        f"du DM initial (sinon ressemble à du spam).\n\n"
        f"PROSPECT\n"
        f"Nom : {prospect_name}\n"
        f"Headline : {prospect_headline}\n"
        f"Ticker analysé envoyé en PJ : {target_ticker or 'non spécifié'}\n\n"
        f"DM INITIAL ENVOYÉ (ne pas répéter le contenu)\n"
        f"« {(initial_dm or '')[:600]} »\n\n"
        f"STYLE DE RELANCE ({style_id})\n"
        f"{style_desc}\n\n"
        f"RÈGLES\n"
        f"- {max_words} mots max, ton humble, pas pushy\n"
        f"- Pas de URL (LinkedIn pénalise)\n"
        f"- Pas de markdown\n"
        f"- Salutation simple « Salut {prospect_name.split()[0] if prospect_name else 'Prénom'} »\n"
        f"- Termine par « Baptiste »\n"
        f"- Français avec accents complets\n\n"
        f"Rédige uniquement la relance, rien d'autre. Pas de préambule."
    )
    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="anthropic",
                            model="claude-haiku-4-5-20251001")
        return (llm.generate(prompt,
                              system="Copywriter sales sobre.",
                              max_tokens=350) or "").strip()
    except Exception as e:
        log.warning(f"[sales/relance] LLM échec : {e}")
        return ""


def draft_relance(prospect_status_row: dict, relance_type: str) -> Optional[str]:
    """Génère et stocke le texte de la relance. Retourne le texte rédigé."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return None
    p = prospect_status_row.get("sales_prospects") or {}
    text = generate_relance_text(
        prospect_name=p.get("name") or "",
        prospect_headline=p.get("headline") or "",
        initial_dm=p.get("dm_draft") or "",
        target_ticker=p.get("target_ticker"),
        relance_type=relance_type,
    )
    if not text:
        return None
    field = "relance_1_text" if relance_type == "J3" else "relance_2_text"
    try:
        r = httpx.patch(
            f"{surl}/rest/v1/sales_prospect_status",
            headers={**_headers(skey), "Prefer": "return=minimal"},
            params={"id": f"eq.{prospect_status_row['id']}"},
            json={field: text,
                   "updated_at": datetime.now(timezone.utc).isoformat()},
            timeout=6.0,
        )
        if r.status_code >= 300:
            log.warning(f"[sales/relance] patch fail : {r.text[:200]}")
            return None
        return text
    except Exception as e:
        log.warning(f"[sales/relance] draft_relance : {e}")
        return None


def mark_relance_sent(prospect_status_id: str, relance_type: str) -> bool:
    """Marque la relance comme envoyée (Baptiste l'a copiée-collée
    manuellement dans LinkedIn natif)."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return False
    field = ("relance_1_sent_at" if relance_type == "J3"
             else "relance_2_sent_at")
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        r = httpx.patch(
            f"{surl}/rest/v1/sales_prospect_status",
            headers={**_headers(skey), "Prefer": "return=minimal"},
            params={"id": f"eq.{prospect_status_id}"},
            json={field: now_iso, "updated_at": now_iso},
            timeout=6.0,
        )
        if r.status_code >= 300:
            log.warning(f"[sales/relance] mark_sent fail : {r.text[:200]}")
            return False
        log.info(f"[sales/relance] {prospect_status_id[:8]} → relance {relance_type} sent")
        return True
    except Exception as e:
        log.warning(f"[sales/relance] mark_sent : {e}")
        return False


def auto_ghost_old_prospects(days_threshold: int = 14) -> int:
    """Marque comme 'ghosted' tous les prospects 'sent' qui ont reçu 2
    relances et ont >14 jours sans réponse. Hygiène de la queue."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_threshold)).isoformat()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/sales_prospect_status",
            headers=_headers(skey),
            params={
                "status": "eq.sent",
                "relance_2_sent_at": f"lte.{cutoff}",
                "select": "id",
                "limit": "100",
            },
            timeout=8.0,
        )
        rows = r.json() if r.status_code < 300 else []
        if not rows:
            return 0
        ids = ",".join(row["id"] for row in rows)
        rp = httpx.patch(
            f"{surl}/rest/v1/sales_prospect_status",
            headers={**_headers(skey), "Prefer": "return=minimal"},
            params={"id": f"in.({ids})"},
            json={"status": "ghosted",
                   "updated_at": datetime.now(timezone.utc).isoformat()},
            timeout=8.0,
        )
        log.info(f"[sales/relance] auto-ghosted {len(rows)} prospects")
        return len(rows)
    except Exception as e:
        log.warning(f"[sales/relance] auto_ghost : {e}")
        return 0
