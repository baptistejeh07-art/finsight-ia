"""Système de rappels/alertes post-analyse.

Expose `run_check_cycle()` qui :
1. Fetch toutes les alertes enabled + non-fired
2. Évalue chaque trigger selon son type
3. Notifie l'user via email (Resend) + web push (VAPID)
4. Marque fired_at + fired_payload si déclenchée
"""
from core.alerts.checker import run_check_cycle

__all__ = ["run_check_cycle"]
