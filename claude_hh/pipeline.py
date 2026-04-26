"""Claude H-H v1.0 — spec-first pipeline CLI."""
from __future__ import annotations
import argparse, glob, json, subprocess, sys, textwrap
from datetime import datetime, timezone
from pathlib import Path

STAGE_LABELS = {"spec":"SPEC","implement":"IMPLEMENT","review":"REVIEW","test":"TEST","done":"DONE","stuck":"STUCK"}
PROMPTS = {s: Path(__file__).parent.parent/"prompts"/f"0{i+1}_{s}.md" for i,s in enumerate(["spec","implement","review","test"])}
NEXT_STEPS = {
    "spec": "编写 .harness/spec.md（≥3 P0）+ .harness/test_*.py，然后 `harness advance`",
    "implement": "修改代码文件，然后 `harness advance`",
    "review": "让 AI 写 .harness/review_report.md（末尾含 PROCEED），然后 `harness advance`",
    "test": "运行 `harness advance` 跑测试",
    "done": "Pipeline 已完成",
    "stuck": "运行 `harness reset` 重新开始，或检查 .harness/stuck_notice.md",
}

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _hdir(root: Path) -> Path: d = root/".harness"; d.mkdir(exist_ok=True); return d
def _pj(root: Path) -> Path: return root/".harness"/"pipeline.json"
def _load(root: Path) -> dict: return json.loads(_pj(root).read_text())
def _save(root: Path, s: dict) -> None: _pj(root).write_text(json.dumps(s, indent=2, ensure_ascii=False))

def _find_root(start: "Path|None" = None) -> "Path|None":
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        if _pj(parent).exists(): return parent
    return None

def _prompt(stage: str) -> None:
    f = PROMPTS.get(stage)
    if f and f.exists(): print("-"*60 + f.read_text() + "-"*60)

def _ruff_mypy(root: Path) -> bool:
    ok = True
    r = subprocess.run(["ruff","check",str(root)], capture_output=True, text=True)
    if r.returncode != 0: print("ruff FAIL: " + r.stdout[:600]); ok = False
    else: print("ruff OK")
    try:
        r2 = subprocess.run(["mypy",str(root),"--ignore-missing-imports"], capture_output=True, text=True, timeout=30)
        if r2.returncode != 0: print("mypy FAIL: " + r2.stdout[:600]); ok = False
        else: print("mypy OK")
    except FileNotFoundError: print("mypy not installed, skipping")
    return ok

def _check_spec(root: Path) -> "tuple[bool,str]":
    spec = root/".harness"/"spec.md"
    if not spec.exists(): return False, "spec.md 不存在，请先创建 .harness/spec.md"
    if spec.read_text().count("P0") < 3: return False, "spec.md P0 不足 3 条。"
    if not glob.glob(str(root/".harness"/"test_*.py")): return False, "需要至少 1 个 .harness/test_*.py。"
    return True, ""

def _check_impl(root: Path, state: dict) -> "tuple[bool,str]":
    hist = state.get("stage_history", [])
    ts = datetime.fromisoformat(hist[-1]["entered_at"]).timestamp() if hist else 0
    for py in root.rglob("*.py"):
        if ".harness" not in py.parts and py.stat().st_mtime > ts: return True, ""
    return False, "还没有修改任何代码文件（.py）。"

def _check_review(root: Path) -> "tuple[bool,str]":
    rp = root/".harness"/"review_report.md"
    if not rp.exists(): return False, "review_report.md 不存在（末尾需含 PROCEED）。"
    t = rp.read_text()
    if "FAIL" in t: return False, "review_report.md 含 FAIL，请先修复。"
    if "PROCEED" not in t: return False, "review_report.md 需包含 PROCEED。"
    if not _ruff_mypy(root): return False, "ruff/mypy 未通过。"
    return True, ""

def _run_tests(root: Path) -> "tuple[bool,str]":
    tests = glob.glob(str(root/".harness"/"test_*.py"))
    if not tests: return False, "没有 .harness/test_*.py。"
    for tf in tests:
        r = subprocess.run([sys.executable,"-m","pytest",tf,"-v"], timeout=120, cwd=str(root))
        if r.returncode != 0: return False, f"测试失败：{Path(tf).name}"
    return True, ""

def _retreat(root: Path, state: dict, reason: str) -> None:
    state["retreat_count"] = n = state.get("retreat_count", 0) + 1
    if n > 3:
        state["current_stage"] = "stuck"
        (_hdir(root)/"stuck_notice.md").write_text(f"# Pipeline 停滞\n\nretreat {n} 次失败。原因：{reason}\n\n运行 `harness reset` 重新开始。\n")
        _save(root, state); print("已 retreat 3 次仍失败，详见 .harness/stuck_notice.md"); return
    state["current_stage"] = "implement"
    state.setdefault("stage_history",[]).append({"stage":"implement","entered_at":_now(),"reason":f"retreat #{n}"})
    _save(root, state); print(f"retreat 到 IMPLEMENT（第 {n}/3 次）。原因：{reason}  请修复后运行 `harness advance`。")

def _require_root(args: argparse.Namespace) -> Path:
    root = _find_root(Path(args.project) if args.project else None)
    if root is None: print("找不到 pipeline。请先 `harness init` + `harness start`。"); sys.exit(1)
    return root

# CLI commands

def cmd_init(args: argparse.Namespace) -> None:
    root = Path(args.project) if args.project else Path.cwd()
    sd = root/".claude"; sd.mkdir(exist_ok=True); sf = sd/"settings.json"
    cfg = json.loads(sf.read_text()) if sf.exists() else {}
    hh = Path(__file__).parent.parent
    h = cfg.setdefault("hooks", {})
    h.setdefault("PreToolUse",[]).append({"matcher":"Edit|Write|MultiEdit","hooks":[{"type":"command","command":f"python3 {hh}/hooks/pre_edit.py"}]})
    h.setdefault("Stop",[]).append({"hooks":[{"type":"command","command":f"python3 {hh}/hooks/stop_check.py"}]})
    sf.write_text(json.dumps(cfg, indent=2)); _hdir(root)
    print(f"Claude H-H 初始化在 {root}  运行 `harness start [描述]` 开始。")

def cmd_start(args: argparse.Namespace) -> None:
    root = Path(args.project) if args.project else Path.cwd()
    if _pj(_hdir(root)).exists(): print("已有 pipeline，请先 `harness reset`。"); sys.exit(1)
    desc = " ".join(args.desc) if args.desc else "未命名任务"
    _save(root,{"current_stage":"spec","retreat_count":0,"description":desc,"started_at":_now(),"updated_at":_now(),"stage_history":[{"stage":"spec","entered_at":_now()}]})
    print(f"Pipeline 已启动：{desc}  当前阶段：SPEC"); _prompt("spec"); print("完成后运行 `harness advance`。")

def cmd_advance(args: argparse.Namespace) -> None:
    root = _require_root(args); state = _load(root); stage = state["current_stage"]
    if stage == "done": print("Pipeline 已完成！"); return
    if stage == "stuck": print("Pipeline 已停滞，请 `harness reset`。"); return
    checks = {
        "spec":(_check_spec,"implement","已进入 IMPLEMENT 阶段。现在可以编辑代码文件。"),
        "implement":(_check_impl,"review","已进入 REVIEW 阶段。请让 AI 写 .harness/review_report.md。"),
        "review":(_check_review,"test","已进入 TEST 阶段，开始跑测试…"),
    }
    if stage in checks:
        fn, nxt, msg = checks[stage]
        ok, err = fn(root, state) if stage=="implement" else fn(root)
        if not ok:
            print(f"advance 失败：{err}")
            if stage=="review" and any(kw in err for kw in ("FAIL","ruff","mypy")): _retreat(root,state,err)
            return
        state["current_stage"]=nxt; state["stage_history"].append({"stage":nxt,"entered_at":_now()})
        _save(root,state); print(msg); _prompt(nxt)
        if nxt=="test": _finish_test(root)
    elif stage=="test": _finish_test(root)

def _finish_test(root: Path) -> None:
    state = _load(root)
    ok, msg = _run_tests(root)
    state = _load(root)
    if not ok: _retreat(root,state,msg); return
    state["current_stage"]="done"; state["updated_at"]=_now(); _save(root,state)
    print("所有测试通过！Pipeline 完成。")
    from claude_hh import hermes_propose; hermes_propose.propose(root)

def cmd_retreat(args: argparse.Namespace) -> None:
    root = _require_root(args); _retreat(root, _load(root), "手动 retreat")

def cmd_status(args: argparse.Namespace) -> None:
    root = _find_root(Path(args.project) if args.project else None)
    if root is None: print("没有活跃 pipeline。运行 `harness init` + `harness start` 开始。"); return
    s = _load(root); stage = s["current_stage"]
    desc = s.get("description", "-")
    rc = s.get("retreat_count", 0)
    st = s.get("started_at", "-")[:19]
    lbl = STAGE_LABELS.get(stage, stage.upper())
    nxt = NEXT_STEPS.get(stage, "-")
    print(f"Pipeline: {desc}  [{lbl}]  retreat:{rc}/3  start:{st}")
    print(f"  下一步: {nxt}")

def cmd_reset(args: argparse.Namespace) -> None:
    root = _require_root(args); _pj(root).unlink(missing_ok=True); print("Pipeline 已重置。运行 `harness start` 开始新任务。")

def cmd_hermes_review(args: argparse.Namespace) -> None:
    from claude_hh import hermes_propose; hermes_propose.interactive_review()

def main() -> None:
    ap = argparse.ArgumentParser(prog="harness", description="Claude H-H v1.0 — spec-first pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""  init            初始化项目\n  start [desc]    开始 pipeline\n  advance         推进阶段\n  retreat         手动回退\n  status          查看状态\n  reset           重置\n  hermes-review   审核提议"""))
    ap.add_argument("--project", default=None)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("init"); ps = sub.add_parser("start"); ps.add_argument("desc",nargs="*")
    for c in ("advance","retreat","status","reset","hermes-review"): sub.add_parser(c)
    args = ap.parse_args()
    {"init":cmd_init,"start":cmd_start,"advance":cmd_advance,"retreat":cmd_retreat,
     "status":cmd_status,"reset":cmd_reset,"hermes-review":cmd_hermes_review}.get(args.cmd, lambda _: ap.print_help())(args)

if __name__ == "__main__": main()
