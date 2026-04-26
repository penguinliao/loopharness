"""Hermes 三层清单加载。

层级（越具体优先级越高）:
  L0 builtin   <install>/hermes/implicit_expectations.md
  L1 user      ~/.claude-hh/hermes/implicit_expectations.md
  L2 project   <project>/.claude-hh/hermes/project.md

同名判定: 同 ## section 下同 **bullet_key** 视为同一条；后加载层覆盖。
"""
from __future__ import annotations
import re
from pathlib import Path

L0_BUILTIN = Path(__file__).parent.parent / "hermes" / "implicit_expectations.md"
L1_USER = Path.home() / ".claude-hh" / "hermes" / "implicit_expectations.md"


def project_l2(root: Path) -> Path:
    return root / ".claude-hh" / "hermes" / "project.md"


_BULLET_RE = re.compile(r"^\s*-\s+\*\*([^*]+?)\*\*")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def _parse(text: str):
    """返回 [(section, key, full_line)] 列表 + section 顺序。"""
    items, sections = [], []
    cur = "(no section)"
    for line in text.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            cur = h.group(1).strip()
            if cur not in sections:
                sections.append(cur)
            continue
        b = _BULLET_RE.match(line)
        if b:
            items.append((cur, b.group(1).strip(), line))
    return items, sections


def load_layers(root=None):
    """合并三层为 markdown。同(section, key)由后层覆盖。无任何层时返回空。"""
    sources = [L0_BUILTIN, L1_USER]
    if root:
        sources.append(project_l2(root))

    merged = {}
    section_order = []
    for src in sources:
        if not src.exists():
            continue
        items, secs = _parse(src.read_text())
        for s in secs:
            if s not in section_order:
                section_order.append(s)
        for sec, key, line in items:
            merged[(sec, key)] = line

    if not merged:
        return ""

    header = "# Hermes implicit expectations (merged: builtin + user + project)"
    out = [header + chr(10)]
    for sec in section_order:
        bullets = [line for (s, _), line in merged.items() if s == sec]
        if not bullets:
            continue
        out.append(chr(10) + "## " + sec + chr(10))
        out.extend(bullets)
    return chr(10).join(out) + chr(10)
