#!/usr/bin/env python3
"""Claude H-H stop_check hook — PM-friendly natural-language version."""
from __future__ import annotations
import json, sys, time
from pathlib import Path

# 自然语言 stage 描述（和 pipeline.py 的 STAGE_LABELS 对齐）
STAGE_TEXT = {
    "spec": "在写规格",
    "implement": "在写代码",
    "review": "在自审",
    "test": "在跑测试",
}


def _find_root() -> "Path|None":
    for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (p / ".harness" / "pipeline.json").exists():
            return p
    return None


def main() -> None:
    root = _find_root()
    if root is None:
        sys.exit(0)
    pj = root / ".harness" / "pipeline.json"
    try:
        data = json.loads(pj.read_text())
    except Exception:
        sys.exit(0)
    stage = data.get("current_stage", "")
    if stage in ("done", "stuck", ""):
        sys.exit(0)

    # v0.3.x 旧版整数 stage：明确告知是僵尸记录
    if isinstance(stage, int):
        age_h = (time.time() - pj.stat().st_mtime) / 3600
        print(
            f"[claude-hh] 有一份上次没收尾的旧版开发记录（已放 {age_h:.0f} 小时）。"
            "新版工具看不懂旧格式，建议清掉重来。",
            file=sys.stderr,
        )
        sys.exit(2)

    # 计算 pipeline 闲置时长
    age_h = (time.time() - pj.stat().st_mtime) / 3600
    stage_text = STAGE_TEXT.get(stage, str(stage))

    if age_h > 24:
        # 超过 24 小时基本是僵尸
        print(
            f"[claude-hh] 这次开发（{stage_text}）已经放了 {age_h:.0f} 小时没动。"
            "可能是上次没收尾留下的，建议清掉重来。",
            file=sys.stderr,
        )
    elif age_h > 4:
        # 4-24 小时之间，温和提醒
        print(
            f"[claude-hh] 这次开发（{stage_text}）暂停了 {age_h:.1f} 小时。"
            "要继续做完吗？",
            file=sys.stderr,
        )
    else:
        # 4 小时内，活跃中断
        print(
            f"[claude-hh] 这次开发还没做完（{stage_text}）。继续做完还是先放一放？",
            file=sys.stderr,
        )
    sys.exit(2)


if __name__ == "__main__":
    main()
