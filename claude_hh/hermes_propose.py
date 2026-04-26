"""Hermes: propose implicit expectations + interactive review."""
from __future__ import annotations
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

GLOBAL_HERMES = Path.home() / ".claude-hh" / "hermes" / "implicit_expectations.md"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _claude_p(prompt: str, timeout: int = 30) -> str:
    """调一次 claude -p。失败返回空串。"""
    try:
        r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def propose_from_self_reflect(root: Path) -> int:
    """自反思：从 spec.md 和测试反推 PM 没说但应该想到的。写 proposed_auto.md。"""
    spec_path = root / ".harness" / "spec.md"
    spec = spec_path.read_text()[:600] if spec_path.exists() else ""
    tests = next(((root / ".harness").glob("test_*.py")), None)
    test_txt = tests.read_text()[:300] if tests else ""
    if not spec:
        return 0
    nl = chr(10)
    prompt = (
        "你是 Hermes。看了以下 spec 和测试，列出 PM 没说但 AI 必须考虑的隐含期望。"
        + "每条一行，格式：- **<短名>** — <描述>。输出 3-7 条。" + nl + nl
        + "# spec" + nl + spec + nl + nl + "# tests" + nl + test_txt
    )
    out = _claude_p(prompt)
    if not out:
        return 0
    target = root / ".harness" / "proposed_auto.md"
    target.write_text("# Hermes 自反思提议（待审核）" + nl + nl + out + nl)
    return len([l for l in out.splitlines() if l.strip().startswith("-")])


def propose_from_inbox(root: Path) -> int:
    """消化 inbox.md（PM 反馈）。写 proposed_feedback.md，归档 inbox。"""
    inbox = root / ".harness" / "inbox.md"
    if not inbox.exists() or not inbox.read_text().strip():
        return 0
    inbox_text = inbox.read_text()
    spec_path = root / ".harness" / "spec.md"
    spec = spec_path.read_text()[:400] if spec_path.exists() else ""
    nl = chr(10)
    prompt = (
        "你是 Hermes。PM 在用产品后给出了以下反馈。把这些反馈翻译成可重用的隐含期望条目。"
        + "每条一行，格式：- **<短名>** — <描述>。输出 1-5 条。" + nl + nl
        + "# spec（上下文）" + nl + spec + nl + nl + "# PM 反馈" + nl + inbox_text
    )
    out = _claude_p(prompt)
    if out:
        target = root / ".harness" / "proposed_feedback.md"
        target.write_text("# Hermes 来自 PM 反馈的提议（待审核）" + nl + nl + out + nl)
        n = len([l for l in out.splitlines() if l.strip().startswith("-")])
    else:
        n = 0
    archive = root / ".harness" / f"inbox.archive.{_now_stamp()}.md"
    shutil.move(str(inbox), str(archive))
    return n


def propose(root: Path) -> None:
    """pipeline done 时调用。先消化 inbox，再自反思。"""
    n_fb = propose_from_inbox(root)
    n_auto = propose_from_self_reflect(root)
    total = n_fb + n_auto
    if total > 0:
        brain = "🧠"
        msg = chr(10) + brain + f" Hermes 发现 {total} 条提议（{n_auto} 自反思 + {n_fb} PM 反馈），运行 harness hermes-review 审核。"
        print(msg)


def _read_proposals(root: Path):
    """读两个 proposed 文件，返回 [(source, line)]。"""
    items = []
    for src, fname in [("auto", "proposed_auto.md"), ("feedback", "proposed_feedback.md")]:
        p = root / ".harness" / fname
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith("-"):
                    items.append((src, line))
    return items


def interactive_review() -> None:
    from claude_hh.pipeline import _find_root

    root = _find_root()
    if root is None:
        print("❌ 找不到 pipeline.")
        return
    items = _read_proposals(root)
    if not items:
        print("📭 没有待审核提议。")
        return

    project_l2 = root / ".claude-hh" / "hermes" / "project.md"
    g_lines: list = []
    p_lines: list = []
    for src, line in items:
        prompt_str = chr(10) + "[" + src + "] " + line.lstrip(chr(45)).lstrip() + chr(10) + "  加入清单？[y/N] "
        ans = input(prompt_str).strip().lower()
        if ans != "y":
            continue
        loc = input("  保存到? [P]roject / [G]lobal (默认 P): ").strip().lower()
        if loc == "g":
            g_lines.append(line)
        else:
            p_lines.append(line)

    if g_lines:
        GLOBAL_HERMES.parent.mkdir(parents=True, exist_ok=True)
        with GLOBAL_HERMES.open("a") as f:
            f.writelines(l + chr(10) for l in g_lines)
        print("✅ 已添加 " + str(len(g_lines)) + " 条到 " + str(GLOBAL_HERMES) + "（L1 全局）")
    if p_lines:
        project_l2.parent.mkdir(parents=True, exist_ok=True)
        with project_l2.open("a") as f:
            f.writelines(l + chr(10) for l in p_lines)
        rel = str(project_l2.relative_to(root))
        print("✅ 已添加 " + str(len(p_lines)) + " 条到 " + rel + "（L2 项目级）")

    for fname in ("proposed_auto.md", "proposed_feedback.md"):
        p = root / ".harness" / fname
        if p.exists():
            p.unlink()
