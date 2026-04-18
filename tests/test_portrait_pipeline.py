"""Tests unitaires pour core/portrait/pipeline."""
import pytest
from unittest.mock import MagicMock, patch
from core.portrait.pipeline import PortraitState, _llm_call
from core.portrait.sources import CompanyContext, Officer


def test_portrait_state_defaults():
    """PortraitState s'instancie avec les defaults attendus."""
    ctx = CompanyContext(ticker="AAPL", name="Apple")
    state = PortraitState(
        ticker="AAPL",
        generated_at="2026-04-19T00:00:00",
        context=ctx,
    )
    assert state.ticker == "AAPL"
    assert state.snapshot is None
    assert state.warnings == []


def test_company_context_defaults():
    """CompanyContext s'instancie avec defaults."""
    ctx = CompanyContext(ticker="MSFT", name="Microsoft")
    assert ctx.ticker == "MSFT"
    assert ctx.officers == []
    assert ctx.wiki_history is None


def test_officer_defaults():
    o = Officer(name="Tim Cook", title="CEO")
    assert o.name == "Tim Cook"
    assert o.bio is None
    assert o.photo_url is None


def test_md_to_html_conversion():
    """_md_to_html convertit markdown LLM en tags ReportLab."""
    from outputs.portrait_pdf_writer import _md_to_html
    # Bold
    assert "<b>important</b>" in _md_to_html("**important**")
    # Italic
    assert "<i>nuance</i>" in _md_to_html("*nuance*")
    # Bullets en début de ligne
    assert "·" in _md_to_html("- premier point\n- second point")
    # Échappement &
    assert "&amp;" in _md_to_html("R&D investment")


def test_md_to_html_empty():
    from outputs.portrait_pdf_writer import _md_to_html
    assert _md_to_html("") == ""
    assert _md_to_html(None) == ""


def test_md_to_html_no_markdown_pass_through():
    """Texte sans markdown reste intact (sauf escape & si présent)."""
    from outputs.portrait_pdf_writer import _md_to_html
    text = "Apple est une société remarquable."
    assert _md_to_html(text) == text
