"""
tools/audit.py — FinSight IA
Audit autonome complet : analyse + render visuel + rapport markdown.

Usage :
  python tools/audit.py AAPL
  python tools/audit.py AAPL MSFT MC.PA TSLA NVDA
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT    = Path(__file__).parent.parent
CLI_DIR = ROOT / "outputs" / "generated" / "cli_tests"
REPORTS = ROOT / "outputs" / "generated" / "audits"
REPORTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       cwd=str(ROOT), encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def _load_state(ticker: str) -> dict:
    p = CLI_DIR / f"{ticker}_state.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _load_briefing(ticker: str) -> str:
    p = CLI_DIR / f"{ticker}_briefing.txt"
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _file_kb(ticker: str, suffix: str) -> str:
    matches = list(CLI_DIR.glob(f"{ticker}*{suffix}"))
    if not matches:
        return "absent"
    size = matches[-1].stat().st_size // 1024
    return f"{size} Ko"


# ---------------------------------------------------------------------------
# Analyse d'un ticker
# ---------------------------------------------------------------------------

def analyze(ticker: str) -> dict:
    """Lance cli_analyze.py et retourne le résultat."""
    print(f"\n{'='*60}")
    print(f"  ANALYSE : {ticker}")
    print(f"{'='*60}")

    t0 = time.time()
    code, out = _run([sys.executable, "cli_analyze.py", "societe", ticker])
    elapsed = time.time() - t0

    print(out[-2000:] if len(out) > 2000 else out)
    return {"code": code, "elapsed": elapsed, "output": out}


def render(ticker: str) -> dict:
    """Lance render_outputs.py et retourne les chemins PNG."""
    print(f"\n  [RENDER] {ticker}...")
    code, out = _run([sys.executable, "tools/render_outputs.py", ticker])
    print(out)

    renders_dir = CLI_DIR / "renders" / ticker
    return {
        "pdf":  sorted(renders_dir.glob("pdf/*.png")),
        "pptx": sorted(renders_dir.glob("pptx/*.png")),
        "xlsx": sorted(renders_dir.glob("xlsx/*.png")),
    }


# ---------------------------------------------------------------------------
# Génération du rapport markdown
# ---------------------------------------------------------------------------

def _flag_icon(level: str) -> str:
    return {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🟢"}.get(level, "⚪")


def build_report(ticker: str, run_result: dict, renders: dict) -> str:
    state    = _load_state(ticker)
    briefing = _load_briefing(ticker)
    lines    = []

    # ── En-tête ──────────────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines += [
        f"# Audit FinSight — {ticker}",
        f"*Généré le {now} — temps pipeline : {run_result['elapsed']:.1f}s*",
        "",
    ]

    # ── Pipeline status ───────────────────────────────────────────────────────
    lines += ["## Statut pipeline", ""]
    synth   = state.get("synthesis")
    qa_py   = state.get("qa_python", "")
    qa_haiku = state.get("qa_haiku")
    devil   = state.get("devil")
    errors  = state.get("errors", [])

    def _agent_row(name, obj, ok_check):
        icon = "✅" if ok_check else "❌"
        return f"| {icon} | {name} | {str(obj)[:80] if obj else 'None'} |"

    lines += [
        "| # | Agent | Résultat |",
        "|---|---|---|",
        _agent_row("AgentData",    state.get("raw_data"),       state.get("data_quality", 0) > 0),
        _agent_row("AgentSentiment", state.get("sentiment"),    state.get("sentiment") is not None),
        _agent_row("AgentQuant",   state.get("ratios"),         state.get("ratios") is not None),
        _agent_row("AgentSynthese", synth,                      synth is not None),
        _agent_row("AgentQAPython", qa_py,                      "passed=True" in str(qa_py)),
        _agent_row("AgentQAHaiku", qa_haiku,                    qa_haiku is not None),
        _agent_row("AgentDevil",   devil,                       devil is not None),
        "",
    ]

    if errors:
        lines += ["**Erreurs pipeline :**", ""]
        for e in errors:
            lines.append(f"- 🔴 {e}")
        lines.append("")

    # ── Synthèse LLM ─────────────────────────────────────────────────────────
    if synth:
        lines += ["## Synthèse LLM", ""]
        for field in ["recommendation", "conviction", "target_base", "target_bull",
                      "target_bear", "summary", "company_description"]:
            val = str(synth).split(f"{field}=")
            if len(val) > 1:
                lines.append(f"- **{field}** : {val[1].split(',')[0][:120]}")
        lines.append("")

        # Devil's advocate
        if devil:
            lines += ["## Devil's Advocate", ""]
            for field in ["counter_thesis", "conviction_delta", "bear_case"]:
                val = str(devil).split(f"{field}=")
                if len(val) > 1:
                    lines.append(f"- **{field}** : {val[1].split(',')[0][:120]}")
            lines.append("")

    # ── QA flags ─────────────────────────────────────────────────────────────
    if qa_py:
        lines += ["## QA Python — flags", ""]
        for flag in str(qa_py).split("QAFlag("):
            if "level=" in flag:
                level = flag.split("level='")[1].split("'")[0] if "level='" in flag else "INFO"
                msg   = flag.split("message='")[1].split("'")[0] if "message='" in flag else ""
                lines.append(f"- {_flag_icon(level)} {msg}")
        lines.append("")

    # ── Fichiers générés ─────────────────────────────────────────────────────
    lines += [
        "## Fichiers générés",
        "",
        f"| Fichier | Taille |",
        f"|---|---|",
        f"| PDF | {_file_kb(ticker, 'report.pdf')} |",
        f"| PPTX | {_file_kb(ticker, 'pitchbook.pptx')} |",
        f"| Excel | {_file_kb(ticker, 'financials.xlsx')} |",
        "",
    ]

    # ── Renders disponibles ───────────────────────────────────────────────────
    lines += ["## Renders visuels disponibles", ""]
    for kind, paths in renders.items():
        lines.append(f"- **{kind.upper()}** : {len(paths)} image(s)")
        for p in paths:
            lines.append(f"  - `{p.name}`")
    lines.append("")

    # ── Briefing ─────────────────────────────────────────────────────────────
    if briefing:
        lines += ["## Briefing (extrait)", "", "```", briefing[:800], "```", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def audit_ticker(ticker: str) -> Path:
    ticker = ticker.upper().replace("/", "-")

    run_result = analyze(ticker)
    renders    = render(ticker)
    report_md  = build_report(ticker, run_result, renders)

    report_path = REPORTS / f"audit_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\n  [AUDIT] Rapport : {report_path.name}")
    return report_path


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL"]
    if not tickers:
        print("Usage: python tools/audit.py TICKER [TICKER2 ...]")
        sys.exit(1)

    reports = []
    for t in tickers:
        try:
            r = audit_ticker(t)
            reports.append(r)
        except Exception as e:
            print(f"  [ERREUR] {t} : {e}")

    print(f"\n{'='*60}")
    print(f"  AUDIT TERMINE — {len(reports)}/{len(tickers)} succes")
    for r in reports:
        print(f"  • {r.name}")
    print(f"{'='*60}\n")
