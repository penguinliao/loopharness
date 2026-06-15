#!/usr/bin/env python3
"""Claude H-H pre_edit hook."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

CODE_EXTS = {".py",".ts",".tsx",".js",".jsx",".vue"}

def _find_root(start: Path) -> "Path|None":
    for p in [start, *start.parents]:
        if (p/".harness"/"pipeline.json").exists(): return p
    return None

def _block(msg: str) -> None: print(f"[claude-hh] ❌ {msg}", file=sys.stderr); sys.exit(2)

def _retreat_brief(root: Path, n: int = 3) -> str:
    """轻量读 retreat_log.md 尾部最近 n 次失败原因（hook 独立运行，不 import claude_hh）。"""
    log = root/".harness"/"retreat_log.md"
    if not log.exists(): return ""
    sections = re.split(r"(?=^## 第 )", log.read_text(), flags=re.M)
    entries = [s.strip() for s in sections if s.strip().startswith("## 第 ")]
    if not entries: return ""
    return "[claude-hh] 📕 改代码前先看错题本（最近没过的原因，别重复踩）：\n" + "\n\n".join(entries[-n:])

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
        # 只锁 spec.md 和 test_*.py 测试脚本；test_bug_report.md 等 .md 上报通道必须放行
        if (name == "spec.md" or (name.startswith("test_") and name.endswith(".py"))) and stage != "spec":
            _block(f"spec.md/test_*.py 只在 SPEC 阶段可编辑（当前：{stage.upper()}）。")
        sys.exit(0)

    if file_path.suffix in CODE_EXTS:
        if stage != "implement":
            _block(f"现在是 {stage.upper()} 阶段，不能改代码文件。运行 `harness advance` 让 pipeline retreat 到 IMPLEMENT。")
        # implement 阶段改代码前：把错题本提要顶到眼前（错题本物理注入，第二道），非阻断
        brief = _retreat_brief(root)
        if brief: print(brief, file=sys.stderr)
    sys.exit(0)

if __name__ == "__main__": main()
