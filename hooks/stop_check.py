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
    # v1.0.7: tolerate v0.3.x int stages (1/3/4/5) — coerce to str to avoid AttributeError
    label = stage.upper() if isinstance(stage, str) else f"stage-{stage}"
    print(f"[claude-hh] ⚠️  pipeline 未完成（{label}），请运行 `harness advance`。", file=sys.stderr)
    sys.exit(2)

if __name__ == "__main__": main()
