# -*- coding: utf-8 -*-
"""
outputs/pdf_utils.py — Utilitaires partagés pour tous les PDF writers.

Centralise les fonctions communes (sanitization, Unicode, markdown→ReportLab)
pour éviter la duplication dans chaque writer.
"""
from __future__ import annotations

import html as _html_mod
import re as _re

# Caractères Unicode problématiques dans ReportLab (rendus comme carrés noirs)
# → remplacés par leurs équivalents ASCII/Latin-1
_UNICODE_FIXES = {
    # Subscripts / Superscripts (CO₂ → CO2)
    "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3",
    "\u2084": "4", "\u2085": "5", "\u2086": "6", "\u2087": "7",
    "\u2088": "8", "\u2089": "9",
    "\u00b2": "2", "\u00b3": "3", "\u00b9": "1",
    # Symboles géométriques / bullets
    "\u25b6": ">", "\u25ba": ">", "\u25c0": "<", "\u25c4": "<",
    "\u2022": "-", "\u2023": "-", "\u25cf": "-", "\u25cb": "o",
    "\u25a0": "-", "\u25a1": "-",  # carrés noir/blanc
    "\u2713": "OK", "\u2714": "OK", "\u2717": "X", "\u2718": "X",  # checkmarks
    # Smart quotes / apostrophes
    "\u2019": "'", "\u2018": "'",
    "\u201c": '"', "\u201d": '"',
    "\u00ab": '"', "\u00bb": '"',  # guillemets français
    # Tirets
    "\u2013": "-",   # en dash
    "\u2014": " - ", # em dash
    "\u2012": "-",   # figure dash
    # Autres
    "\u2026": "...",  # ellipsis
    "\u20ac": "EUR",  # euro (si pas dans la police)
    "\u2030": "%%",   # per mille
    "\u00a0": " ",    # non-breaking space
    "\u202f": " ",    # narrow non-breaking space
    "\u200b": "",     # zero-width space
    "\u200c": "",     # zero-width non-joiner
    "\ufeff": "",     # BOM
}


def clean_unicode(text: str) -> str:
    """Remplace les caractères Unicode problématiques par des équivalents ASCII.

    Appeler AVANT l'échappement XML (&amp; etc.) car certains remplacements
    contiennent des caractères qui doivent ensuite être échappés.
    """
    for uc, repl in _UNICODE_FIXES.items():
        text = text.replace(uc, repl)
    # Strip block elements / box drawings non mappés explicitement, qui apparaissent
    # en ZapfDingbats 'n' dans le PDF (bug audit AAPL vs MSFT page 3 : 1000 'n'
    # ZapfDingbats sur 14 lignes = un séparateur LLM unicode mal rendu).
    # Plages Unicode :
    #   U+2500-257F box drawings (─━│┃┌┐└┘├┤┬┴┼)
    #   U+2580-259F block elements (▀▁▂▃▄▅▆▇█▉)
    #   U+25A0-25FF geometric shapes restants après _UNICODE_FIXES
    text = _re.sub(r"[─-▟]+", "", text)
    text = _re.sub(r"[▢-◿]+", "", text)
    return text


def safe_text(s) -> str:
    """Sanitize une string pour injection dans un ReportLab Paragraph.

    1. Décode les entités HTML du LLM (&gt; → >)
    2. Normalise les entités cassées (« S&P; 500 », « AT&T; ») que les LLM
       sortent parfois par semi-tokenisation HTML.
    3. Remplace les caractères Unicode problématiques (CO₂ → CO2)
    4. Échappe les caractères XML (&, <, >)
    5. Convertit le markdown **bold** en <b>bold</b>
    6. Convertit le markdown __bold__ en <b>bold</b>
    """
    if not s:
        return ""
    decoded = _html_mod.unescape(str(s))
    # Fix entités parasites sorties par certains LLM : « S&P; 500 » →
    # « S&P 500 », « AT&T; » → « AT&T », « M&A; » → « M&A ».
    # Le LLM a halluciné un `;` après le `&X` comme s'il fermait une entité.
    decoded = _re.sub(r"&([A-Z][A-Za-z]{0,3});(?=\s|$|[^A-Za-z])", r"&\1", decoded)
    decoded = clean_unicode(decoded)
    out = decoded.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Markdown bold → ReportLab <b>
    out = _re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', out)
    out = _re.sub(r'__([^_]+?)__', r'<b>\1</b>', out)
    return out
