"""
tools/hook_post_analyze.py
Hook PostToolUse : lance render_outputs.py apres cli_analyze.py.
Reçoit le JSON Claude Code sur stdin.
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

data = json.load(sys.stdin)
cmd  = data.get("tool_input", {}).get("command", "")

if "cli_analyze.py" not in cmd:
    sys.exit(0)

m = re.search(r"cli_analyze\.py\s+\S+\s+(\S+)", cmd)
if not m:
    sys.exit(0)

ticker = m.group(1).upper()
_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
subprocess.Popen(
    [sys.executable, "tools/render_outputs.py", ticker],
    cwd=str(ROOT),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=_flags,
)
print(json.dumps({"systemMessage": f"[Hook] Render {ticker} lance en arriere-plan"}))
