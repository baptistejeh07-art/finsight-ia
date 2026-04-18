"""Tests unitaires pour core/data_audit (warnings post-pipeline)."""
import pytest
from core.data_audit import audit_state


def test_empty_state_returns_errors():
    warnings = audit_state({})
    fields = [w["field"] for w in warnings]
    assert "synthesis" in fields
    assert "ratios.years" in fields
    assert "raw_data.company_info" in fields


def test_full_state_returns_no_warnings():
    state = {
        "raw_data": {"company_info": {"sector": "Technology"}},
        "ratios": {"years": {"2024": {"pe_ratio": 20.5, "ev_ebitda": 12.3,
                                      "ebitda_margin": 0.35, "roe": 0.45}}},
        "synthesis": {
            "target_base": 150.0,
            "comparable_peers": [{"ticker": "MSFT"}],
            "conviction": 0.78,
        },
    }
    warnings = audit_state(state)
    assert len(warnings) == 0


def test_low_conviction_triggers_info():
    state = {
        "raw_data": {"company_info": {"sector": "Tech"}},
        "ratios": {"years": {"2024": {"pe_ratio": 20, "ev_ebitda": 10,
                                      "ebitda_margin": 0.3, "roe": 0.2}}},
        "synthesis": {"target_base": 100, "comparable_peers": [{"x": 1}], "conviction": 0.20},
    }
    warnings = audit_state(state)
    sevs = {w["severity"] for w in warnings}
    assert "info" in sevs


def test_missing_target_base_triggers_warning():
    state = {
        "raw_data": {"company_info": {"sector": "Tech"}},
        "ratios": {"years": {"2024": {"pe_ratio": 20, "ev_ebitda": 10,
                                      "ebitda_margin": 0.3, "roe": 0.2}}},
        "synthesis": {"target_base": None, "comparable_peers": [{"x": 1}], "conviction": 0.7},
    }
    warnings = audit_state(state)
    fields = [w["field"] for w in warnings]
    assert "synthesis.target_base" in fields


def test_no_peers_triggers_warning():
    state = {
        "raw_data": {"company_info": {"sector": "Tech"}},
        "ratios": {"years": {"2024": {"pe_ratio": 20, "ev_ebitda": 10,
                                      "ebitda_margin": 0.3, "roe": 0.2}}},
        "synthesis": {"target_base": 100, "comparable_peers": [], "conviction": 0.7},
    }
    warnings = audit_state(state)
    fields = [w["field"] for w in warnings]
    assert "synthesis.comparable_peers" in fields


def test_critical_ratios_missing():
    state = {
        "raw_data": {"company_info": {"sector": "Tech"}},
        "ratios": {"years": {"2024": {"pe_ratio": None, "ev_ebitda": None,
                                      "ebitda_margin": 0.3, "roe": 0.2}}},
        "synthesis": {"target_base": 100, "comparable_peers": [{"x": 1}], "conviction": 0.7},
    }
    warnings = audit_state(state)
    fields = [w["field"] for w in warnings]
    assert "ratios.latest" in fields
