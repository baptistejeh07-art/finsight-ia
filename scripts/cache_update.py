#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Cache Supabase : documents comptables bruts
# scripts/cache_update.py
#
# Collecte les etats financiers bruts (yfinance) pour ~500 tickers.
# Stocke en JSONB dans Supabase via REST API (pas de SDK — Python 3.14).
# Met a jour uniquement si : next_earnings depasse OU last_updated > 7j.
# Zero LLM.
#
# Usage :
#   python scripts/cache_update.py                       # CAC40 par defaut
#   python scripts/cache_update.py --universe dax40
#   python scripts/cache_update.py --universe all --workers 10
#   python scripts/cache_update.py --tickers MC.PA AAPL MSFT --force
# =============================================================================

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("cache_update")

_UPDATE_INTERVAL_DAYS = 7  # refresh si last_updated > N jours

# ---------------------------------------------------------------------------
# Univers de tickers
# ---------------------------------------------------------------------------

CAC40_TICKERS: list[str] = [
    "AI.PA",    "AIR.PA",  "ALO.PA",  "CS.PA",   "BNP.PA",
    "EN.PA",    "CAP.PA",  "CA.PA",   "ACA.PA",  "BN.PA",
    "DSY.PA",   "ENGI.PA", "EL.PA",   "ERF.PA",  "RMS.PA",
    "KER.PA",   "OR.PA",   "LR.PA",   "MC.PA",   "ML.PA",
    "ORA.PA",   "RI.PA",   "PUB.PA",  "RNO.PA",  "SAF.PA",
    "SGO.PA",   "SAN.PA",  "SU.PA",   "GLE.PA",  "STM.PA",
    "HO.PA",    "TTE.PA",  "URW.PA",  "VIE.PA",  "DG.PA",
    "VIV.PA",   "WLN.PA",  "MT.AS",   "STLAM.MI","BVI.PA",
    "STMPA.PA", # STMicroelectronics — ticker yfinance correct
]

DAX40_TICKERS: list[str] = [
    "ADS.DE",  "AIR.DE",  "ALV.DE",  "BAYN.DE", "BEI.DE",
    "BMW.DE",  "BNR.DE",  "CON.DE",  "1COV.DE", "DTG.DE",
    "DB1.DE",  "DBK.DE",  "DHL.DE",  "DTE.DE",  "EOAN.DE",
    "FRE.DE",  "HNR1.DE", "HEI.DE",  "HEN3.DE", "IFX.DE",
    "MBG.DE",  "MRK.DE",  "MTX.DE",  "MUV2.DE", "NDA.DE",
    "P911.DE", "PAH3.DE", "QIA.DE",  "RHM.DE",  "RWE.DE",
    "SAP.DE",  "SIE.DE",  "SHL.DE",  "SY1.DE",  "VNA.DE",
    "VOW3.DE", "ZAL.DE",  "ENR.DE",  "DHER.DE", "SRT3.DE",
]

STOXX50_TICKERS: list[str] = [
    "ABI.BR",   "AD.AS",   "ADS.DE",  "AI.PA",   "AIR.PA",
    "ALV.DE",   "ASML.AS", "BAS.DE",  "BAYN.DE", "BNP.PA",
    "BMW.DE",   "CS.PA",   "DG.PA",   "DTE.DE",  "EOAN.DE",
    "EL.PA",    "ENI.MI",  "ENGI.PA", "GLE.PA",  "IBE.MC",
    "IFX.DE",   "ING.AS",  "ITX.MC",  "KER.PA",  "MC.PA",
    "MBG.DE",   "MUV2.DE", "NOKIA.HE","OR.PA",   "PHIA.AS",
    "PRX.AS",   "RMS.PA",  "RWE.DE",  "SAN.PA",  "SAP.DE",
    "SIE.DE",   "SU.PA",   "STLAM.MI","TTE.PA",  "VOW3.DE",
    "AZN.L",    "HSBA.L",  "SHEL.L",  "BP.L",    "RIO.L",
    "GSK.L",    "ULVR.L",  "REL.AS",  "SAN.MC",  "TEF.MC",
]

FTSE100_TICKERS: list[str] = [
    "AAL.L",  "ABF.L",  "ADM.L",  "AHT.L",  "ANTO.L",
    "AZN.L",  "AUTO.L", "AV.L",   "BA.L",   "BARC.L",
    "BATS.L", "BEZ.L",  "BKG.L",  "BME.L",  "BNZL.L",
    "BP.L",   "BRBY.L", "BT-A.L", "CCH.L",  "CNA.L",
    "CPG.L",  "CRDA.L", "CRH.L",  "DCC.L",  "DGE.L",
    "DPLM.L", "EDV.L",  "EZJ.L",  "FCIT.L", "FERG.L",
    "FLTR.L", "FRES.L", "GFS.L",  "GLEN.L", "GSK.L",
    "HIK.L",  "HLMA.L", "HLN.L",  "HSBA.L", "HSX.L",
    "ICG.L",  "IHG.L",  "III.L",  "IMB.L",  "INF.L",
    "ITRK.L", "JD.L",   "JMAT.L", "KGF.L",  "LAND.L",
    "LGEN.L", "LLOY.L", "LSEG.L", "MKS.L",  "MNDI.L",
    "MNG.L",  "MRO.L",  "NG.L",   "NWG.L",  "NXT.L",
    "OCDO.L", "PHNX.L", "PRU.L",  "PSH.L",  "PSN.L",
    "PSON.L", "REL.L",  "RIO.L",  "RKT.L",  "RMV.L",
    "RR.L",   "RS1.L",  "SBRY.L", "SDR.L",  "SGE.L",
    "SGRO.L", "SHEL.L", "SKG.L",  "SMDS.L", "SMIN.L",
    "SMT.L",  "SN.L",   "SPX.L",  "SSE.L",  "STJ.L",
    "SVT.L",  "TSCO.L", "TW.L",   "ULVR.L", "UU.L",
    "VOD.L",  "WPP.L",  "WTB.L",  "DPH.L",  "RTO.L",
    "ALC.L",  "EXPN.L", "RB.L",   "RDSA.L", "STAN.L",
]


def fetch_sp500() -> list[str]:
    """
    Charge la liste S&P500 avec 3 sources en cascade :
    1. GitHub (datasets/s-and-p-500-companies) — CSV officiel maintenu
    2. datahub.io — miroir du même dataset
    3. stooq — HTML parse de l'indice ^SPX
    4. Fallback hardcodé ~100 titres si tout echoue
    """
    _HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinSightIA/1.0)"}

    def _normalize(tickers: list[str]) -> list[str]:
        # yfinance : BRK.B -> BRK-B
        return [t.strip().replace(".", "-") for t in tickers if t.strip()]

    # --- Source 1 : GitHub CSV ---
    try:
        import io
        r = requests.get(
            "https://raw.githubusercontent.com/datasets/s-and-p-500-companies"
            "/main/data/constituents.csv",
            headers=_HEADERS, timeout=10,
        )
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        tickers = _normalize(df["Symbol"].tolist())
        log.info(f"S&P500 charge depuis GitHub ({len(tickers)} tickers)")
        return tickers
    except Exception as e:
        log.warning(f"GitHub S&P500 indisponible: {e}")

    # --- Source 2 : datahub.io ---
    try:
        import io
        r = requests.get(
            "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv",
            headers=_HEADERS, timeout=10,
        )
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        tickers = _normalize(df["Symbol"].tolist())
        log.info(f"S&P500 charge depuis datahub.io ({len(tickers)} tickers)")
        return tickers
    except Exception as e:
        log.warning(f"datahub.io S&P500 indisponible: {e}")

    # --- Source 3 : stooq HTML ---
    try:
        tables = pd.read_html(
            "https://stooq.com/t/?i=500",
            attrs={"id": "fth1"},
        )
        df = tables[0]
        # La colonne symbole s'appelle "Symbol" ou la 1ere colonne
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        tickers = _normalize(df[col].astype(str).tolist())
        tickers = [t for t in tickers if t and not t.startswith("nan")]
        if tickers:
            log.info(f"S&P500 charge depuis stooq ({len(tickers)} tickers)")
            return tickers
    except Exception as e:
        log.warning(f"stooq S&P500 indisponible: {e}")

    # --- Fallback hardcode ~100 tickers ---
    log.warning("Toutes les sources S&P500 ont echoue — fallback hardcode 100 tickers")
    return [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B",
        "LLY",  "AVGO", "TSLA", "JPM",  "WMT",  "V",     "XOM",  "UNH",
        "MA",   "JNJ",  "PG",   "COST", "HD",   "ORCL",  "ABBV", "KO",
        "CVX",  "MRK",  "AMD",  "BAC",  "PEP",  "NFLX",  "TMO",  "CSCO",
        "ACN",  "CRM",  "LIN",  "WFC",  "ABT",  "GE",    "IBM",  "NOW",
        "INTU", "QCOM", "RTX",  "GS",   "DHR",  "SPGI",  "CAT",  "MCD",
        "AXP",  "MS",   "AMGN", "ISRG", "TXN",  "HON",   "PFE",  "NEE",
        "LOW",  "UNP",  "PM",   "C",    "BMY",  "SCHW",  "ETN",  "UPS",
        "DE",   "MDT",  "BLK",  "GILD", "ADI",  "MMC",   "ADP",  "CI",
        "MO",   "ICE",  "PLD",  "REGN", "SYK",  "BSX",   "VRTX", "PANW",
        "SO",   "DUK",  "ZTS",  "CB",   "CME",  "NOC",   "ITW",  "ELV",
        "HUM",  "WM",   "FI",   "KLAC", "APH",  "SNPS",  "CDNS", "ECL",
        "AON",  "MCO",  "NSC",  "GD",   "F",    "GM",
    ]


UNIVERSES: dict[str, list[str]] = {
    "cac40":   CAC40_TICKERS,
    "dax40":   DAX40_TICKERS,
    "stoxx50": STOXX50_TICKERS,
    "ftse100": FTSE100_TICKERS,
}

# ---------------------------------------------------------------------------
# Client Supabase REST (pas de SDK Python — incompatible Python 3.14)
# ---------------------------------------------------------------------------

class SupabaseCache:
    """
    Wrapper REST API Supabase pour la table tickers_cache.
    Utilise PostgREST directement via requests.
    """

    TABLE = "tickers_cache"

    def __init__(self, url: str, secret_key: str) -> None:
        self.base = url.rstrip("/") + f"/rest/v1/{self.TABLE}"
        self._headers = {
            "apikey":        secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type":  "application/json",
        }

    def upsert(self, row: dict) -> bool:
        """Upsert un ticker (conflict resolution sur PRIMARY KEY ticker)."""
        try:
            r = requests.post(
                self.base + "?on_conflict=ticker",
                headers={**self._headers, "Prefer": "resolution=merge-duplicates"},
                data=json.dumps(row, ensure_ascii=False, default=str),
                timeout=20,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Supabase upsert ({row.get('ticker', '?')}): {e}")
            return False

    def get_all_meta(self) -> dict[str, dict]:
        """
        Retourne {ticker: {last_updated, next_earnings}} pour toute la table.
        Utilise la pagination (max 1000 par page) pour les grands univers.
        """
        result: dict[str, dict] = {}
        offset = 0
        page_size = 1000

        while True:
            try:
                r = requests.get(
                    self.base,
                    headers={**self._headers, "Range-Unit": "items",
                              "Range": f"{offset}-{offset + page_size - 1}"},
                    params={"select": "ticker,last_updated,next_earnings"},
                    timeout=15,
                )
                r.raise_for_status()
                page = r.json()
                if not page:
                    break
                for row in page:
                    result[row["ticker"]] = row
                if len(page) < page_size:
                    break
                offset += page_size
            except Exception as e:
                log.warning(f"Supabase get_all_meta (offset={offset}): {e}")
                break

        return result


# ---------------------------------------------------------------------------
# Helpers yfinance
# ---------------------------------------------------------------------------

def _df_to_dict(df: Optional[pd.DataFrame]) -> dict:
    """
    Convertit un DataFrame yfinance en dict JSON-serialisable.
    Format : {"Total Revenue": {"2024-12-31": 84345000000.0, ...}, ...}
    Valeurs NaN -> null.
    """
    if df is None or df.empty:
        return {}

    out: dict = {}
    for idx in df.index:
        row: dict = {}
        for col in df.columns:
            try:
                key = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                val = df.at[idx, col]
                row[key] = None if pd.isna(val) else float(val)
            except Exception:
                continue
        out[str(idx)] = row
    return out


def _get_next_earnings(tk: yf.Ticker) -> Optional[str]:
    """Retourne la prochaine date de resultats (YYYY-MM-DD) ou None."""
    try:
        cal = tk.calendar
        if cal is None:
            return None

        # yfinance >= 0.2.x retourne un dict
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date") or cal.get("earningsDate") or []
            if not isinstance(dates, list):
                dates = [dates]
            for d in dates:
                try:
                    ts = pd.Timestamp(d)
                    if ts.date() >= date.today():
                        return ts.strftime("%Y-%m-%d")
                except Exception:
                    continue

        # yfinance plus ancien : DataFrame
        elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
            val = cal.at["Earnings Date", cal.columns[0]]
            if pd.notna(val):
                ts = pd.Timestamp(val)
                if ts.date() >= date.today():
                    return ts.strftime("%Y-%m-%d")

    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Logique de rafraichissement
# ---------------------------------------------------------------------------

def should_update(
    cached: Optional[dict],
    force: bool = False,
) -> tuple[bool, str]:
    """
    Retourne (doit_mettre_a_jour, raison).

    Conditions de mise a jour :
    1. force=True
    2. Ticker absent du cache
    3. next_earnings <= aujourd'hui (nouveaux resultats disponibles)
    4. last_updated > _UPDATE_INTERVAL_DAYS jours
    5. last_updated absent
    """
    if force:
        return True, "force"

    if not cached:
        return True, "nouveau ticker"

    today = date.today()

    next_e = cached.get("next_earnings")
    if next_e:
        try:
            ne = date.fromisoformat(str(next_e)[:10])
            if ne <= today:
                return True, f"next_earnings {next_e} depasse"
        except (ValueError, TypeError):
            pass

    last_upd = cached.get("last_updated")
    if not last_upd:
        return True, "last_updated absent"

    try:
        lu = datetime.fromisoformat(str(last_upd).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - lu).days
        if age >= _UPDATE_INTERVAL_DAYS:
            return True, f"last_updated il y a {age}j"
    except (ValueError, TypeError):
        return True, "last_updated invalide"

    return False, "cache valide"


# ---------------------------------------------------------------------------
# Fetch brut yfinance
# ---------------------------------------------------------------------------

_RATE_LIMIT_SLEEP = 90  # secondes d'attente si YFRateLimitError


def fetch_raw(ticker: str, _retry: bool = True) -> Optional[dict]:
    """
    Collecte les documents comptables bruts pour un ticker.
    Fetch parallele : income_stmt + balance_sheet + cashflow + calendar + info.
    Zero calcul. Zero LLM.
    Retry automatique une fois si YFRateLimitError (pause _RATE_LIMIT_SLEEP s).
    Retourne un dict pret pour Supabase ou None si donnees absentes.
    """
    try:
        tk = yf.Ticker(ticker)

        def _is():
            return tk.income_stmt

        def _bs():
            return tk.balance_sheet

        def _cf():
            return tk.cashflow

        def _cal():
            return _get_next_earnings(tk)

        def _info():
            try:
                return tk.info or {}
            except Exception:
                return {}

        with ThreadPoolExecutor(max_workers=5) as pool:
            f_is   = pool.submit(_is)
            f_bs   = pool.submit(_bs)
            f_cf   = pool.submit(_cf)
            f_cal  = pool.submit(_cal)
            f_info = pool.submit(_info)

        is_df  = f_is.result()
        bs_df  = f_bs.result()
        cf_df  = f_cf.result()
        next_e = f_cal.result()
        info   = f_info.result()

        # Validation : au moins un document disponible
        if not any(df is not None and not df.empty for df in [is_df, bs_df, cf_df]):
            log.warning(f"[{ticker}] aucun document financier")
            return None

        return {
            "ticker":           ticker.upper(),
            "company_name":     info.get("longName") or info.get("shortName") or ticker,
            "sector":           info.get("sector") or info.get("industryDisp") or "",
            "exchange":         info.get("exchange") or "",
            "currency":         info.get("currency") or "",
            "income_statement": _df_to_dict(is_df),
            "balance_sheet":    _df_to_dict(bs_df),
            "cash_flow":        _df_to_dict(cf_df),
            "last_updated":     datetime.now(timezone.utc).isoformat(),
            "next_earnings":    next_e,
        }

    except Exception as e:
        # Rate limit yfinance : pause et retry une fois
        if _retry and "YFRateLimitError" in type(e).__name__:
            log.warning(f"[{ticker}] rate limit yfinance — pause {_RATE_LIMIT_SLEEP}s puis retry")
            time.sleep(_RATE_LIMIT_SLEEP)
            return fetch_raw(ticker, _retry=False)
        log.error(f"[{ticker}] fetch_raw: {e}")
        return None


# ---------------------------------------------------------------------------
# Worker unitaire
# ---------------------------------------------------------------------------

def process_ticker(
    ticker: str,
    cache: SupabaseCache,
    meta_cache: dict[str, dict],
    force: bool = False,
) -> tuple[str, str]:
    """
    Traite un ticker : verifie si update necessaire, fetch, upsert.
    Retourne (ticker, statut) parmi : updated | skipped | no_data | error
    """
    cached = meta_cache.get(ticker.upper())
    do_update, reason = should_update(cached, force=force)

    if not do_update:
        log.debug(f"[{ticker}] skip ({reason})")
        return ticker, "skipped"

    log.info(f"[{ticker}] mise a jour ({reason}) ...")
    t0 = time.time()

    row = fetch_raw(ticker)
    if row is None:
        return ticker, "no_data"

    ok = cache.upsert(row)
    elapsed = round(time.time() - t0, 1)
    status = "updated" if ok else "error"
    ne = row.get("next_earnings") or "N/A"
    log.info(f"[{ticker}] {status} en {elapsed}s  next_earnings={ne}")
    return ticker, status


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

def run(
    tickers: list[str],
    cache: SupabaseCache,
    workers: int = 8,
    force: bool = False,
    delay: float = 0.0,
) -> dict[str, int]:
    """
    Lance le cache update en parallele. Retourne {statut: count}.
    delay : secondes entre chaque soumission (evite le rate limit Yahoo).
    """
    log.info("Chargement meta cache Supabase ...")
    meta_cache = cache.get_all_meta()
    log.info(f"{len(meta_cache)} tickers deja en cache.")
    log.info(f"Traitement de {len(tickers)} tickers ({workers} workers, delay={delay}s) ...")

    counts: dict[str, int] = {"updated": 0, "skipped": 0, "no_data": 0, "error": 0}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for t in tickers:
            futures[pool.submit(process_ticker, t, cache, meta_cache, force)] = t
            if delay > 0:
                time.sleep(delay)

        for future in as_completed(futures):
            ticker, status = future.result()
            counts[status] = counts.get(status, 0) + 1
            if status in ("error", "no_data"):
                errors.append(f"{ticker}:{status}")

    log.info("=" * 60)
    log.info(
        f"DONE  updated={counts['updated']}  skipped={counts['skipped']}"
        f"  no_data={counts['no_data']}  errors={counts['error']}"
    )
    if errors:
        log.warning(f"Problemes : {', '.join(errors)}")

    return counts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinSight IA — Cache Supabase (documents comptables bruts yfinance)",
    )
    parser.add_argument(
        "--universe",
        choices=["cac40", "dax40", "stoxx50", "ftse100", "sp500", "all"],
        default="cac40",
        help="Univers de tickers (defaut: cac40)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Tickers specifiques (ex: MC.PA AAPL MSFT). Prioritaire sur --universe.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Workers paralleles (defaut: 8)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force la mise a jour meme si le cache est valide",
    )
    parser.add_argument(
        "--interval-days",
        type=int,
        default=_UPDATE_INTERVAL_DAYS,
        dest="interval_days",
        help=f"Intervalle de refresh en jours (defaut: {_UPDATE_INTERVAL_DAYS})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delai en secondes entre soumissions (ex: 0.5 pour eviter rate limit)",
    )
    args = parser.parse_args()

    # Credentials
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        log.error("SUPABASE_URL et SUPABASE_SECRET_KEY requis dans .env")
        sys.exit(1)

    cache = SupabaseCache(url, key)

    # Selection des tickers
    if args.tickers:
        tickers = list(dict.fromkeys(t.upper() for t in args.tickers))
        log.info(f"Mode manuel : {len(tickers)} tickers")

    elif args.universe == "sp500":
        log.info("Chargement S&P500 depuis Wikipedia ...")
        tickers = fetch_sp500()
        log.info(f"{len(tickers)} tickers charges")

    elif args.universe == "all":
        log.info("Chargement S&P500 depuis Wikipedia ...")
        sp500 = fetch_sp500()
        all_tickers = (
            CAC40_TICKERS + DAX40_TICKERS + STOXX50_TICKERS
            + FTSE100_TICKERS + sp500
        )
        tickers = list(dict.fromkeys(t.upper() for t in all_tickers))
        log.info(f"{len(tickers)} tickers uniques (univers complet)")

    else:
        tickers = UNIVERSES[args.universe]
        log.info(f"Univers {args.universe} : {len(tickers)} tickers")

    run(tickers, cache, workers=args.workers, force=args.force, delay=args.delay)


if __name__ == "__main__":
    main()
