"""Résolveur nom de société → ticker yfinance.

Hiérarchie :
1. Match direct ticker (AAPL, MC.PA, ABBN.SW) → retour tel quel
2. Dict hardcodé des ~200 plus grosses capis FR/US/UK/DE/CH/JP/CN (instant, $0)
3. Fallback LLM Groq : "quelle est le ticker yfinance pour X ?" (seulement si miss)
4. Validation yfinance fast_info (évite ticker halluciné)
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dict hardcodé — top capis monde (nom normalisé lower → ticker yfinance)
# Utiliser uniquement : nom commercial COURT (pas "Société Anonyme Hermès
# International" mais "hermes"). Ajouter variantes populaires.
# ---------------------------------------------------------------------------

_COMPANIES: dict[str, str] = {
    # --- US Mega-caps ---
    "apple": "AAPL", "microsoft": "MSFT", "alphabet": "GOOGL", "google": "GOOGL",
    "amazon": "AMZN", "meta": "META", "facebook": "META", "nvidia": "NVDA",
    "tesla": "TSLA", "berkshire": "BRK-B", "berkshire hathaway": "BRK-B",
    "visa": "V", "mastercard": "MA", "jpmorgan": "JPM", "jp morgan": "JPM",
    "exxon": "XOM", "exxonmobil": "XOM", "chevron": "CVX",
    "walmart": "WMT", "procter gamble": "PG", "p&g": "PG",
    "johnson johnson": "JNJ", "j&j": "JNJ", "coca cola": "KO", "pepsi": "PEP",
    "disney": "DIS", "netflix": "NFLX", "adobe": "ADBE", "salesforce": "CRM",
    "oracle": "ORCL", "cisco": "CSCO", "intel": "INTC", "amd": "AMD",
    "broadcom": "AVGO", "qualcomm": "QCOM", "ibm": "IBM", "paypal": "PYPL",
    "airbnb": "ABNB", "uber": "UBER", "spotify": "SPOT", "palantir": "PLTR",
    "costco": "COST", "home depot": "HD", "starbucks": "SBUX", "mcdonald": "MCD",
    "mcdonalds": "MCD", "nike": "NKE", "boeing": "BA", "ford": "F",
    "general motors": "GM", "gm": "GM", "ge": "GE", "general electric": "GE",
    "pfizer": "PFE", "merck": "MRK", "eli lilly": "LLY", "lilly": "LLY",
    "abbvie": "ABBV", "unitedhealth": "UNH", "bank of america": "BAC",
    "wells fargo": "WFC", "goldman sachs": "GS", "morgan stanley": "MS",
    "blackrock": "BLK", "snowflake": "SNOW", "zoom": "ZM",
    "crowdstrike": "CRWD", "datadog": "DDOG", "cloudflare": "NET",
    "shopify": "SHOP", "square": "SQ", "block": "SQ", "robinhood": "HOOD",
    "coinbase": "COIN", "rivian": "RIVN", "lucid": "LCID",
    "amd ryzen": "AMD",

    # --- France (CAC 40 et grandes capis) ---
    "lvmh": "MC.PA", "louis vuitton": "MC.PA", "moet hennessy": "MC.PA",
    "hermes": "RMS.PA", "hermès": "RMS.PA",
    "l'oreal": "OR.PA", "loreal": "OR.PA", "l oreal": "OR.PA",
    "kering": "KER.PA", "gucci": "KER.PA",
    "totalenergies": "TTE.PA", "total": "TTE.PA", "total energies": "TTE.PA",
    "airbus": "AIR.PA", "safran": "SAF.PA", "thales": "HO.PA",
    "dassault": "AM.PA", "dassault aviation": "AM.PA",
    "dassault systemes": "DSY.PA", "dassault systèmes": "DSY.PA",
    "schneider": "SU.PA", "schneider electric": "SU.PA",
    "sanofi": "SAN.PA", "danone": "BN.PA",
    "axa": "CS.PA", "bnp": "BNP.PA", "bnp paribas": "BNP.PA",
    "societe generale": "GLE.PA", "société générale": "GLE.PA", "socgen": "GLE.PA",
    "credit agricole": "ACA.PA", "crédit agricole": "ACA.PA",
    "pernod ricard": "RI.PA", "pernod": "RI.PA",
    "carrefour": "CA.PA", "vinci": "DG.PA",
    "stellantis": "STLAP.PA", "peugeot": "STLAP.PA", "fiat": "STLAP.PA",
    "saint-gobain": "SGO.PA", "saint gobain": "SGO.PA",
    "michelin": "ML.PA", "veolia": "VIE.PA",
    "engie": "ENGI.PA", "edf": "EDF.PA",
    "orange": "ORA.PA", "capgemini": "CAP.PA",
    "renault": "RNO.PA", "publicis": "PUB.PA",
    "essilor": "EL.PA", "essilorluxottica": "EL.PA", "luxottica": "EL.PA",
    "bouygues": "EN.PA", "legrand": "LR.PA",
    "air liquide": "AI.PA", "accor": "AC.PA",
    "eurofins": "ERF.PA", "teleperformance": "TEP.PA",
    "worldline": "WLN.PA", "stmicroelectronics": "STMPA.PA", "stm": "STMPA.PA",

    # --- Allemagne (DAX) ---
    "sap": "SAP.DE", "siemens": "SIE.DE", "allianz": "ALV.DE",
    "deutsche bank": "DBK.DE", "deutsche telekom": "DTE.DE",
    "basf": "BAS.DE", "bayer": "BAYN.DE", "volkswagen": "VOW3.DE",
    "vw": "VOW3.DE", "bmw": "BMW.DE", "mercedes": "MBG.DE",
    "mercedes-benz": "MBG.DE", "porsche": "P911.DE",
    "adidas": "ADS.DE", "puma": "PUM.DE",
    "munich re": "MUV2.DE", "munichre": "MUV2.DE",
    "rwe": "RWE.DE", "eon": "EOAN.DE", "e.on": "EOAN.DE",
    "fresenius": "FRE.DE", "heidelberg": "HEI.DE",
    "henkel": "HEN3.DE", "beiersdorf": "BEI.DE",
    "infineon": "IFX.DE", "zalando": "ZAL.DE",

    # --- UK ---
    "astrazeneca": "AZN.L", "glaxo": "GSK.L", "glaxosmithkline": "GSK.L",
    "gsk": "GSK.L", "shell": "SHEL.L", "bp": "BP.L",
    "hsbc": "HSBA.L", "barclays": "BARC.L", "lloyds": "LLOY.L",
    "natwest": "NWG.L", "standard chartered": "STAN.L",
    "unilever": "ULVR.L", "diageo": "DGE.L", "british american tobacco": "BATS.L",
    "bat": "BATS.L", "reckitt": "RKT.L", "rolls royce": "RR.L",
    "bae systems": "BA.L", "vodafone": "VOD.L", "tesco": "TSCO.L",
    "sainsbury": "SBRY.L", "m&s": "MKS.L", "marks spencer": "MKS.L",
    "burberry": "BRBY.L", "rio tinto": "RIO.L", "anglo american": "AAL.L",

    # --- Suisse ---
    "nestle": "NESN.SW", "nestlé": "NESN.SW",
    "roche": "ROG.SW", "novartis": "NOVN.SW",
    "ubs": "UBSG.SW", "credit suisse": "CSGN.SW",
    "richemont": "CFR.SW", "cartier": "CFR.SW",
    "abb": "ABBN.SW", "zurich insurance": "ZURN.SW",
    "swiss re": "SREN.SW", "logitech": "LOGN.SW",
    "holcim": "HOLN.SW", "givaudan": "GIVN.SW",

    # --- Pays-Bas / Belgique ---
    "asml": "ASML.AS", "heineken": "HEIA.AS",
    "ing": "INGA.AS", "philips": "PHIA.AS",
    "prosus": "PRX.AS", "ahold": "AD.AS", "ahold delhaize": "AD.AS",
    "ab inbev": "ABI.BR", "anheuser busch": "ABI.BR", "anheuser-busch inbev": "ABI.BR",
    "kbc": "KBC.BR", "solvay": "SOLB.BR",

    # --- Italie / Espagne ---
    "ferrari": "RACE", "enel": "ENEL.MI", "eni": "ENI.MI",
    "unicredit": "UCG.MI", "intesa sanpaolo": "ISP.MI",
    "banco santander": "SAN.MC", "santander": "SAN.MC",
    "bbva": "BBVA.MC", "iberdrola": "IBE.MC",
    "inditex": "ITX.MC", "zara": "ITX.MC",
    "telefonica": "TEF.MC", "telefónica": "TEF.MC",

    # --- Japon ---
    "toyota": "7203.T", "sony": "6758.T", "nintendo": "7974.T",
    "softbank": "9984.T", "honda": "7267.T", "mitsubishi": "8058.T",
    "mitsui": "8031.T", "sumitomo": "8316.T",
    "keyence": "6861.T", "fast retailing": "9983.T", "uniqlo": "9983.T",
    "nissan": "7201.T", "panasonic": "6752.T",

    # --- Chine / HK ---
    "alibaba": "BABA", "tencent": "0700.HK", "byd": "1211.HK",
    "jd": "JD", "jd.com": "JD", "baidu": "BIDU", "nio": "NIO",
    "xpeng": "XPEV", "pinduoduo": "PDD", "temu": "PDD",
    "meituan": "3690.HK", "xiaomi": "1810.HK",

    # --- Canada ---
    "shopify canada": "SHOP.TO", "royal bank": "RY.TO", "rbc": "RY.TO",
    "td": "TD.TO", "td bank": "TD.TO", "enbridge": "ENB.TO",
    "bombardier": "BBD-B.TO",
}


def _normalize(q: str) -> str:
    """Normalise un nom : lower, strip ponctuation, espaces uniques."""
    q = q.lower().strip()
    q = re.sub(r"[^\w\s&-]", " ", q, flags=re.UNICODE)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def resolve_from_dict(query: str) -> Optional[str]:
    """Cherche dans le dict hardcodé. None si miss."""
    norm = _normalize(query)
    if not norm:
        return None
    if norm in _COMPANIES:
        return _COMPANIES[norm]
    # Fuzzy : enlève "sa", "plc", "ag", "inc", "ltd", "corp"
    cleaned = re.sub(r"\b(sa|plc|ag|inc|ltd|corp|co|group|sas|se|nv|bv)\b", "", norm).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned and cleaned != norm and cleaned in _COMPANIES:
        return _COMPANIES[cleaned]
    return None


def resolve_via_llm(query: str) -> Optional[str]:
    """Appelle Groq pour convertir un nom en ticker yfinance.
    Retourne un ticker ou None. Validation fast_info derrière."""
    try:
        from core.llm_provider import LLMProvider
    except Exception:
        return None

    prompt = (
        f"Give me the exact Yahoo Finance ticker symbol for this company: \"{query}\".\n"
        f"Rules:\n"
        f"- Return ONLY the ticker (e.g. AAPL, MC.PA, ABBN.SW, 7203.T, 0700.HK).\n"
        f"- Use the correct exchange suffix when not US (PA, DE, L, MI, MC, SW, T, HK, TO).\n"
        f"- If unknown, return 'NONE'.\n"
        f"- No explanation, no quotes, no markdown."
    )

    for provider, model in [
        ("groq", "llama-3.3-70b-versatile"),
        ("mistral", "mistral-small-latest"),
        ("cerebras", "qwen-3-235b-a22b-instruct-2507"),
    ]:
        try:
            llm = LLMProvider(provider=provider, model=model)
            raw = llm.generate(prompt=prompt, max_tokens=20)
            if not raw:
                continue
            candidate = raw.strip().upper().split()[0].strip(".,;:\"'`")
            if candidate == "NONE" or not candidate:
                return None
            # Validation format
            if not re.fullmatch(r"[A-Z0-9]{1,6}(\.[A-Z]{1,3})?(-[A-Z])?", candidate):
                continue
            return candidate
        except Exception as e:
            log.debug(f"[ticker_resolver] {provider} failed: {e}")
            continue
    return None


def _validate_ticker(ticker: str) -> bool:
    """Valide via yfinance fast_info.last_price > 0. Évite les tickers hallucinés."""
    try:
        from core.yfinance_cache import get_ticker
        fi = get_ticker(ticker).fast_info
        px = getattr(fi, "last_price", None)
        return bool(px and float(px) > 0)
    except Exception:
        return False


def resolve(query: str) -> Optional[str]:
    """Résout un nom/ticker → ticker yfinance validé. None si introuvable.

    Ordre :
      1. Si query ressemble déjà à un ticker valide (majuscules + suffixe) : retour direct
      2. Dict hardcodé
      3. LLM fallback + validation fast_info
    """
    q = (query or "").strip()
    if not q:
        return None

    # 1. Ticker direct (majuscules court + suffixe optionnel)
    if re.fullmatch(r"[A-Z0-9]{1,6}(\.[A-Z]{1,3})?(-[A-Z])?", q):
        return q

    # 2. Dict hardcodé (pas de validation API — les mappings sont sûrs)
    found = resolve_from_dict(q)
    if found:
        return found

    # 3. LLM fallback
    cand = resolve_via_llm(q)
    if cand and _validate_ticker(cand):
        log.info(f"[ticker_resolver] LLM resolved '{q}' → {cand}")
        return cand

    return None
