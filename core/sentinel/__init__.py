"""Sentinelle — monitoring prod FinSight.

Expose :
  - record_error(severity, error_type, ...) : log dans pipeline_errors
  - check_missing_data(state) : détecte les champs critiques absents
  - @watched_node(name) : décorateur hook pour les nodes du graph
"""
from core.sentinel.recorder import record_error, check_missing_data, watched_node, trigger_wakeup_if_new

__all__ = ["record_error", "check_missing_data", "watched_node", "trigger_wakeup_if_new"]
