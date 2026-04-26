"""Hermes: propose implicit expectations after pipeline completes."""
from __future__ import annotations
import subprocess
from pathlib import Path

GLOBAL_HERMES = Path.home()/".claude-hh"/"hermes"/"implicit_expectations.md"

def propose(root: Path) -> None:
    spec = (root/".harness"/"spec.md").read_text()[:600] if (root/".harness"/"spec.md").exists() else ""
    tests = next(((root/".harness").glob("test_*.py")), None)
    test_txt = tests.read_text()[:300] if tests else ""
    prompt = ("你是 Hermes。看了以下 spec 和测试，列出 PM 没说但 AI 必须考虑的隐含期望。"
              "每条一行，格式：[分类] 描述。输出 3-7 条。

"
              f"# spec
{spec}

# tests
{test_txt}")
    out = root/".harness"/"proposed_skills.md"
    try:
        r = subprocess.run(["claude","-p",prompt], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            out.write_text("# Hermes 提议（待审核）

" + r.stdout.strip() + "
")
            n = len([l for l in r.stdout.strip().splitlines() if l.strip()])
            print(f"
🧠 Hermes 发现 {n} 条提议，运行 `harness hermes-review` 审核。"); return
    except (FileNotFoundError, subprocess.TimeoutExpired): pass
    print("
⚠️  Hermes 提议跳过（claude CLI 不可用或超时）。")

def interactive_review() -> None:
    from claude_hh.pipeline import _find_root
    root = _find_root()
    if root is None: print("❌ 找不到 pipeline。"); return
    proposed = root/".harness"/"proposed_skills.md"
    if not proposed.exists(): print("📭 没有待审核提议。先完成一个 pipeline。"); return
    lines = [l for l in proposed.read_text().splitlines() if l.strip() and not l.startswith("#")]
    if not lines: print("📭 提议为空。"); return
    approved = [l for l in lines if input(f"
加入全局清单？
  {l}
  [y/N] ").strip().lower() == "y"]
    if not approved: print("
没有批准任何条目。"); return
    GLOBAL_HERMES.parent.mkdir(parents=True, exist_ok=True)
    with GLOBAL_HERMES.open("a") as f:
        f.writelines(l+"
" for l in approved)
    print(f"
✅ 已添加 {len(approved)} 条到 {GLOBAL_HERMES}"); proposed.unlink()
