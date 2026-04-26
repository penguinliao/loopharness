#!/usr/bin/env python3
"""Claude H-H pre_edit hook."""
from __future__ import annotations
import json, sys
from pathlib import Path

CODE_EXTS = {".py",".ts",".tsx",".js",".jsx",".vue"}

def _find_root(start: Path) -> "Path|None":
    for p in [start, *start.parents]:
        if (p/".harness"/"pipeline.json").exists(): return p
    return None

def _block(msg: str) -> None: print(f"[claude-hh] ❌ {msg}", file=sys.stderr); sys.exit(2)

def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
        if payload.get("tool_name","") not in ("Edit","Write","MultiEdit"): sys.exit(0)
        ti = payload.get("tool_input", {})
        file_path = Path(ti.get("file_path","") or ti.get("path","")).resolve()
    except Exception: sys.exit(2)

    root = _find_root(file_path.parent)
    if root is None: sys.exit(0)
    try: stage = json.loads((root/".harness"/"pipeline.json").read_text()).get("current_stage","")
    except Exception: sys.exit(2)

    try: rel = str(file_path.relative_to(root))
    except ValueError: rel = str(file_path)
    in_harness = rel.startswith(".harness")

    if in_harness:
        name = file_path.name
        if (name == "spec.md" or name.startswith("test_")) and stage != "spec":
            _block(f"spec.md/test_*.py 只在 SPEC 阶段可编辑（当前：{stage.upper()}）。")
        sys.exit(0)

    if file_path.suffix in CODE_EXTS and stage != "implement":
        _block(f"现在是 {stage.upper()} 阶段，不能改代码文件。运行 `harness advance` 让 pipeline retreat 到 IMPLEMENT。")
    sys.exit(0)

if __name__ == "__main__": main()
