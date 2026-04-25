# -*- coding: utf-8 -*-
"""tools/sales_agent/discovery_csv.py — Import bulk de prospects depuis un CSV.

Phase 1 (immédiate) : Baptiste copie-colle 30-50 URLs profils LinkedIn dans
un CSV simple, on parse, on insère en table sales_prospects.

Phase 2 (plus tard) : remplacé par scraping via stickerdaniel/linkedin-mcp-server
qui utilise les cookies LinkedIn de Baptiste pour chercher des posts FR
avec keywords PEA/DCF/stock picking.

Format CSV attendu (3 colonnes minimum, headers au choix) :
    linkedin_url, name, headline
    https://linkedin.com/in/pierre-dupont,Pierre Dupont,Ingénieur PEA
    ...

Colonnes optionnelles :
    bio, recent_post_1, recent_post_2, recent_post_3

Si recent_post_X présent, c'est une string (texte du post). On peut aussi
fournir recent_posts_json avec un JSON.
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ProspectInput:
    linkedin_url: str
    name: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    recent_posts: Optional[list[dict]] = None


def parse_csv(csv_text: str) -> list[ProspectInput]:
    """Parse un CSV (texte brut) et retourne une liste ProspectInput.

    Tolère :
    - headers en français ou anglais
    - séparateurs , ou ; ou \t
    - guillemets autour des champs
    - lignes vides
    """
    if not csv_text or not csv_text.strip():
        return []

    # Détection du séparateur
    sample = csv_text[:2000]
    sep = ","
    for s in (";", "\t", ","):
        if sample.count(s) > sample.count(sep):
            sep = s
    log.info(f"[discovery_csv] séparateur détecté : {sep!r}")

    reader = csv.DictReader(StringIO(csv_text), delimiter=sep)
    out: list[ProspectInput] = []
    for row in reader:
        # Normalise les clés (lowercase, strip)
        nrow = {(k or "").strip().lower(): (v or "").strip()
                 for k, v in row.items()}
        url = (nrow.get("linkedin_url") or nrow.get("url")
                or nrow.get("linkedin") or nrow.get("profile_url") or "").strip()
        if not url or "linkedin.com" not in url:
            continue
        # Normalisation URL : retire les query strings de tracking
        url = url.split("?")[0].rstrip("/")
        name = nrow.get("name") or nrow.get("nom") or nrow.get("full_name")
        headline = nrow.get("headline") or nrow.get("title") or nrow.get("titre")
        bio = nrow.get("bio") or nrow.get("about") or nrow.get("description")
        # Posts récents : 3 colonnes string OU recent_posts_json
        posts: list[dict] = []
        if nrow.get("recent_posts_json"):
            try:
                posts = json.loads(nrow["recent_posts_json"])
                if not isinstance(posts, list):
                    posts = []
            except (json.JSONDecodeError, TypeError):
                posts = []
        else:
            for i in range(1, 6):
                txt = nrow.get(f"recent_post_{i}")
                if txt:
                    posts.append({"text": txt, "date": "", "url": ""})
        out.append(ProspectInput(
            linkedin_url=url, name=name, headline=headline,
            bio=bio, recent_posts=posts or None,
        ))
    log.info(f"[discovery_csv] {len(out)} prospects parsés")
    return out


def get_csv_template() -> str:
    """Retourne un CSV template à partager avec Baptiste pour qu'il sache
    quoi remplir."""
    return (
        "linkedin_url,name,headline,bio,recent_post_1,recent_post_2,recent_post_3\n"
        "https://linkedin.com/in/exemple,Pierre Dupont,Ingénieur PEA depuis 8 ans,"
        "\"Passionné analyse fondamentale, focus valeurs européennes\","
        "\"Schneider Electric reste mon top pick — P/E 30x mais ROIC 18%\","
        "\"LVMH 27x vs Hermès 50x — qui mérite la prime ?\",\n"
    )
