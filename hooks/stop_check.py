#!/usr/bin/env python3
"""Claude H-H stop_check hook."""
from __future__ import annotations
import json, sys
from pathlib import Path

def _find_root() -> "Path|None":
    for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (p/".harness"/"pipeline.json").exists(): return p
    return None

def main() -> None:
    root = _find_root()
    if root is None: sys.exit(0)
    try: stage = json.loads((root/".harness"/"pipeline.json").read_text()).get("current_stage","")
    except Exception: sys.exit(0)
    if stage in ("done","stuck",""): sys.exit(0)
    print(f"[claude-hh] ⚠️  pipeline 未完成（{stage.upper()}），请运行 `python3 -m claude_hh.pipeline advance`。", file=sys.stderr)
    sys.exit(2)

if __name__ == "__main__": main()
