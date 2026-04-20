"""Worker cron des alertes post-analyse.

Appelé toutes les 6h via Railway cron sur POST /cron/check-alerts.
Pour chaque alerte enabled + fired_at IS NULL :
  1. Évalue le trigger (price_target, earnings, dividend, news, custom_date…)
  2. Si déclenchée : notifie user (email + push) et marque fired_at
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

from core.alerts.notifier import send_email, send_push

log = logging.getLogger(__name__)


def _supabase() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    return url, key


def _fetch_active_alerts() -> list[dict]:
    url, key = _supabase()
    if not url or not key:
        return []
    try:
        r = httpx.get(
            f"{url}/rest/v1/analysis_alerts",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"enabled": "eq.true", "fired_at": "is.null", "order": "created_at.asc",
                    "limit": "500"},
            timeout=10.0,
        )
        return r.json() if r.status_code < 300 else []
    except Exception as e:
        log.warning(f"[alerts] fetch_active failed: {e}")
        return []


def _user_email(user_id: str) -> Optional[str]:
    url, key = _supabase()
    try:
        r = httpx.get(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=5.0,
        )
        if r.status_code >= 300:
            return None
        return (r.json() or {}).get("email")
    except Exception:
        return None


def _push_subs(user_id: str) -> list[dict]:
    url, key = _supabase()
    try:
        r = httpx.get(
            f"{url}/rest/v1/push_subscriptions",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"user_id": f"eq.{user_id}"},
            timeout=5.0,
        )
        return r.json() if r.status_code < 300 else []
    except Exception:
        return []


def _mark_fired(alert_id: str, payload: dict) -> None:
    url, key = _supabase()
    try:
        httpx.patch(
            f"{url}/rest/v1/analysis_alerts",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": f"eq.{alert_id}"},
            json={"fired_at": datetime.now(timezone.utc).isoformat(), "fired_payload": payload},
            timeout=5.0,
        )
    except Exception as e:
        log.warning(f"[alerts] mark_fired failed: {e}")


def _mark_checked(alert_id: str) -> None:
    url, key = _supabase()
    try:
        httpx.patch(
            f"{url}/rest/v1/analysis_alerts",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": f"eq.{alert_id}"},
            json={"last_checked": datetime.now(timezone.utc).isoformat()},
            timeout=5.0,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Évaluation des triggers
# ---------------------------------------------------------------------------

def _eval_price_target(ticker: str, value: dict) -> Optional[dict]:
    """value: {target: 200.0, direction: 'above'|'below'}. Return fired payload ou None."""
    target = value.get("target")
    direction = value.get("direction", "above")
    if not target or not ticker:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if not price:
            return None
        price = float(price)
        tgt = float(target)
        triggered = (price >= tgt) if direction == "above" else (price <= tgt)
        if triggered:
            return {"price": price, "target": tgt, "direction": direction,
                    "currency": info.get("currency"), "ticker": ticker}
        return None
    except Exception as e:
        log.warning(f"[alerts] price_target {ticker} eval failed: {e}")
        return None


def _eval_date(value: dict, grace_hours: int = 12) -> Optional[dict]:
    """value: {date: 'YYYY-MM-DD'}. Fire si now >= date - grace."""
    date_s = value.get("date")
    if not date_s:
        return None
    try:
        d = datetime.fromisoformat(date_s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now + timedelta(hours=grace_hours) >= d:
            return {"fired_date": date_s, "now": now.isoformat()}
        return None
    except Exception as e:
        log.warning(f"[alerts] date eval failed: {e}")
        return None


def _eval_earnings(ticker: str, value: dict) -> Optional[dict]:
    """Fire quand la prochaine date d'earnings ≤ 24h."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        import pandas as pd  # noqa: F401
        next_date = None
        if cal is not None:
            # yfinance retourne soit un dict ({'Earnings Date': [Timestamp]}) soit un DataFrame
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date") or cal.get("Earnings date")
                if ed and len(ed) > 0:
                    next_date = ed[0]
            else:
                try:
                    next_date = cal.loc["Earnings Date"].iloc[0]
                except Exception:
                    pass
        if next_date is None:
            return None
        try:
            ts = next_date.to_pydatetime() if hasattr(next_date, "to_pydatetime") else next_date
        except Exception:
            ts = next_date
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta_h = (ts - now).total_seconds() / 3600
            if 0 <= delta_h <= 24:
                return {"earnings_at": ts.isoformat(), "hours_remaining": round(delta_h, 1),
                        "ticker": ticker}
        return None
    except Exception as e:
        log.warning(f"[alerts] earnings {ticker} eval failed: {e}")
        return None


def _eval_dividend(ticker: str, value: dict) -> Optional[dict]:
    """Fire si ex-dividend date ≤ 48h."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        exd = info.get("exDividendDate")
        if not exd:
            return None
        ts = datetime.fromtimestamp(int(exd), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_h = (ts - now).total_seconds() / 3600
        if 0 <= delta_h <= 48:
            return {"ex_dividend_at": ts.isoformat(), "hours_remaining": round(delta_h, 1),
                    "dividend_rate": info.get("dividendRate"), "ticker": ticker}
        return None
    except Exception as e:
        log.warning(f"[alerts] dividend {ticker} eval failed: {e}")
        return None


def _eval_news(ticker: str, value: dict) -> Optional[dict]:
    """Fire si une news récente (<6h) sur le ticker via Finnhub.
    value: {min_importance: 'major'|'minor'} — MVP ignoré, on check juste la présence.
    """
    if not ticker:
        return None
    try:
        import os as _os
        key = _os.getenv("FINNHUB_API_KEY", "")
        if not key:
            return None
        now = datetime.now(timezone.utc)
        _from = (now - timedelta(hours=6)).strftime("%Y-%m-%d")
        _to = now.strftime("%Y-%m-%d")
        r = httpx.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": _from, "to": _to, "token": key},
            timeout=8.0,
        )
        news = r.json() if r.status_code < 300 else []
        if news and isinstance(news, list):
            # Garde les news des 6h dernières
            cutoff = int((now - timedelta(hours=6)).timestamp())
            recent = [n for n in news if n.get("datetime", 0) >= cutoff]
            if recent:
                top = recent[0]
                return {"headline": top.get("headline"), "url": top.get("url"),
                        "source": top.get("source"), "count": len(recent),
                        "ticker": ticker}
        return None
    except Exception as e:
        log.warning(f"[alerts] news {ticker} eval failed: {e}")
        return None


def _eval_quarterly(ticker: str, value: dict) -> Optional[dict]:
    """Check si résultats trimestriels récemment publiés (mostRecentQuarter change)."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        mrq = info.get("mostRecentQuarter")
        if not mrq:
            return None
        # Si last_checked était avant mrq → fire
        # Simple approx : on fire si mrq < 14 jours
        ts = datetime.fromtimestamp(int(mrq), tz=timezone.utc)
        delta_d = (datetime.now(timezone.utc) - ts).days
        if 0 <= delta_d <= 14:
            return {"quarter_end": ts.isoformat(), "days_since": delta_d,
                    "eps_ttm": info.get("trailingEps"), "ticker": ticker}
        return None
    except Exception as e:
        log.warning(f"[alerts] quarterly {ticker} eval failed: {e}")
        return None


EVAL_FUNCS = {
    "price_target": lambda a: _eval_price_target(a.get("ticker"), a.get("trigger_value") or {}),
    "earnings_date": lambda a: _eval_earnings(a.get("ticker"), a.get("trigger_value") or {}),
    "dividend_exdate": lambda a: _eval_dividend(a.get("ticker"), a.get("trigger_value") or {}),
    "news": lambda a: _eval_news(a.get("ticker"), a.get("trigger_value") or {}),
    "custom_date": lambda a: _eval_date(a.get("trigger_value") or {}),
    "quarterly_results": lambda a: _eval_quarterly(a.get("ticker"), a.get("trigger_value") or {}),
}


def _notify(alert: dict, payload: dict) -> None:
    """Envoie email + push au user selon les channels."""
    user_id = alert.get("user_id")
    channels = alert.get("channels") or ["email"]
    ticker = alert.get("ticker") or "—"
    label = alert.get("label") or f"{alert.get('trigger_type')} · {ticker}"

    # Construction message
    trigger = alert.get("trigger_type")
    if trigger == "price_target":
        body = f"{ticker} a atteint {payload.get('price')} {payload.get('currency', '')} (cible : {payload.get('target')})."
    elif trigger == "earnings_date":
        body = f"Earnings call {ticker} dans {payload.get('hours_remaining')}h."
    elif trigger == "dividend_exdate":
        body = f"Ex-dividende {ticker} dans {payload.get('hours_remaining')}h."
    elif trigger == "news":
        body = f"News {ticker} : {payload.get('headline', '')} (source : {payload.get('source', '')})"
    elif trigger == "custom_date":
        body = f"Rappel : {label}"
    elif trigger == "quarterly_results":
        body = f"Résultats {ticker} publiés il y a {payload.get('days_since')} jours (EPS TTM: {payload.get('eps_ttm')})"
    else:
        body = f"Rappel FinSight : {label}"

    if "email" in channels:
        email = _user_email(user_id)
        if email:
            send_email(email, subject=f"[FinSight] {label}", body=body, ticker=ticker)

    if "push" in channels:
        for sub in _push_subs(user_id):
            send_push(sub, title=f"FinSight · {ticker}", body=body)


def run_check_cycle() -> dict:
    """Exécute un cycle complet. Retourne un rapport."""
    alerts = _fetch_active_alerts()
    fired_count = 0
    checked = 0
    errors = 0

    for a in alerts:
        checked += 1
        trigger = a.get("trigger_type")
        fn = EVAL_FUNCS.get(trigger)
        if not fn:
            continue
        try:
            payload = fn(a)
            _mark_checked(a["id"])
            if payload:
                _notify(a, payload)
                _mark_fired(a["id"], payload)
                fired_count += 1
                log.info(f"[alerts] fired #{a['id']} ({trigger} {a.get('ticker')})")
        except Exception as e:
            errors += 1
            log.warning(f"[alerts] alert #{a.get('id')} eval error: {e}")

    log.info(f"[alerts] cycle done: checked={checked} fired={fired_count} errors={errors}")
    return {"checked": checked, "fired": fired_count, "errors": errors,
            "ts": datetime.now(timezone.utc).isoformat()}
