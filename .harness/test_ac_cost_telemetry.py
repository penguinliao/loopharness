# mypy: ignore-errors
# flake8: noqa
"""Loop 护栏强化②：LLM 审查调用成本遥测 + 软上限提醒（最小版，不硬熔断）。

测试 FROM spec：此刻 _bump_review_calls / _review_budget_warning / SOFT_REVIEW_BUDGET
尚不存在，本文件应在 SPEC 阶段红、IMPLEMENT 正确实现后绿。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import pipeline  # noqa: E402


def _make_project(extra: dict | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="test_cost_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "current_stage": "review",
        "retreat_count": 0,
        "description": "假任务",
        "started_at": now,
        "updated_at": now,
        "stage_history": [{"stage": "implement", "entered_at": now}],
    }
    if extra:
        state.update(extra)
    (h / "pipeline.json").write_text(json.dumps(state))
    return root


def _calls(root: Path) -> int:
    return json.loads((root / ".harness" / "pipeline.json").read_text()).get("llm_review_calls", 0)


def test_ac1_bump_accumulates_and_persists() -> None:
    """AC1: _bump_review_calls 累加并落盘到 pipeline.json。"""
    root = _make_project()
    try:
        if not hasattr(pipeline, "_bump_review_calls"):
            raise AssertionError("pipeline 缺少 _bump_review_calls(root) helper")
        pipeline._bump_review_calls(root)
        pipeline._bump_review_calls(root)
        if _calls(root) != 2:
            raise AssertionError(f"连调 2 次 _bump_review_calls 后计数应为 2，实际 {_calls(root)}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac2_skip_does_not_count_but_real_call_does() -> None:
    """AC2: 二审短路跳过(无diff)不计数；实际调用 LLM 后计数 +1。"""
    root = _make_project()
    (root / ".harness" / "spec.md").write_text("# 假 spec\n")
    (root / ".harness" / "review_report.md").write_text("PROCEED\n")
    orig_diff = pipeline._impl_period_diff
    orig_run = pipeline.subprocess.run
    try:
        # (a) 无 diff → 短路跳过，不计数
        pipeline._impl_period_diff = lambda root: ""
        pipeline._fresh_context_review(root)
        if _calls(root) != 0:
            raise AssertionError(f"无 diff 短路时不该计数，实际 {_calls(root)}")

        # (b) 有 diff + claude 返回成功 → 实际调用，计数 +1
        pipeline._impl_period_diff = lambda root: "fake diff 内容若干"
        pipeline.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="PROCEED")
        pipeline._fresh_context_review(root)
        if _calls(root) != 1:
            raise AssertionError(f"实际调用二审后计数应为 1，实际 {_calls(root)}")
    finally:
        pipeline._impl_period_diff = orig_diff
        pipeline.subprocess.run = orig_run
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_budget_warning_soft_only() -> None:
    """AC3: 超软上限返回中文提醒，未超返回空；提醒是 str（软提醒，不熔断）。"""
    if not hasattr(pipeline, "_review_budget_warning") or not hasattr(pipeline, "SOFT_REVIEW_BUDGET"):
        raise AssertionError("pipeline 缺少 _review_budget_warning / SOFT_REVIEW_BUDGET")
    budget = pipeline.SOFT_REVIEW_BUDGET
    under = pipeline._review_budget_warning(1)
    over = pipeline._review_budget_warning(budget + 1)
    if under != "":
        raise AssertionError(f"未超软上限应返回空串，实际 {under!r}")
    if not isinstance(over, str) or not over.strip():
        raise AssertionError("超软上限应返回非空中文提醒")
    if "Traceback" in over:
        raise AssertionError("AC5: 提醒不应含内部异常栈")


def test_ac4_status_shows_review_call_count() -> None:
    """AC4: harness status 输出里能看到累计 LLM 审查调用次数。"""
    root = _make_project(extra={"llm_review_calls": 7})
    try:
        env = {**os.environ, "PYTHONPATH": str(REPO)}
        p = subprocess.run(
            [sys.executable, "-m", "claude_hh.pipeline", "status"],
            cwd=str(root), env=env, capture_output=True, text=True, timeout=30,
        )
        out = p.stdout + p.stderr
        if "7" not in out:
            raise AssertionError(f"status 没显示审查调用次数(7)，输出：{out!r}")
        if not any(k in out for k in ("审查", "LLM", "调用")):
            raise AssertionError(f"status 没有可识别的审查调用次数标签，输出：{out!r}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
