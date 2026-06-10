# mypy: ignore-errors
# flake8: noqa
"""AC3 + AC4 + AC5: 浊龙 FAIL 自动回炉；预算耗尽带病交付；PASS 正常 done."""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import hermes_propose, pipeline  # noqa: E402

DUMMY_TEST = (
    "def test_ok() -> None:\n"
    "    if 1 != 1:\n"
    "        raise AssertionError('math broke')\n"
)


def _make_project(retreat_count: int, zhuolong_verdict: str) -> Path:
    """tempdir 假项目：测试脚本全过 + 浊龙 brief/report 就位."""
    root = Path(tempfile.mkdtemp(prefix="test_zhuolong_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "current_stage": "test",
        "retreat_count": retreat_count,
        "description": "假任务",
        "started_at": now,
        "updated_at": now,
        "stage_history": [{"stage": "implement", "entered_at": now}, {"stage": "test", "entered_at": now}],
    }
    (h / "pipeline.json").write_text(json.dumps(state))
    (h / "test_ok.py").write_text(DUMMY_TEST)
    (h / "zhuolong_brief.md").write_text("# 黑盒测试交付单\n\n场景：搜索用户能看到结果\n")
    if zhuolong_verdict == "FAIL":
        (h / "zhuolong_report.md").write_text("# 浊龙报告\n\n搜索页白屏，控制台报错。\n\n判定：FAIL\n")
    else:
        (h / "zhuolong_report.md").write_text("# 浊龙报告\n\n全部场景符合预期。\n\n判定：PASS\n")
    return root


def _state(root: Path) -> dict:
    return json.loads((root / ".harness" / "pipeline.json").read_text())


def test_ac3_zhuolong_fail_triggers_auto_retreat(monkeypatch) -> None:
    """AC3: 浊龙 FAIL 且预算未耗尽 → 自动回炉到 implement，不原地干等."""
    monkeypatch.setattr(hermes_propose, "propose", lambda root: None)
    root = _make_project(retreat_count=0, zhuolong_verdict="FAIL")
    try:
        pipeline._finish_test(root)
        s = _state(root)
        if s["current_stage"] != "implement":
            raise AssertionError(
                f"浊龙 FAIL 后应自动回炉到 implement，实际 stage={s['current_stage']}（原地干等？）"
            )
        if s.get("retreat_count", 0) != 1:
            raise AssertionError(f"回炉后 retreat_count 应为 1，实际 {s.get('retreat_count')}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac4_budget_exhausted_degraded_delivery(monkeypatch) -> None:
    """AC4: 浊龙 FAIL 且 retreat_count>=3 → 带病交付：done + delivery_report.md，不 stuck."""
    monkeypatch.setattr(hermes_propose, "propose", lambda root: None)
    root = _make_project(retreat_count=3, zhuolong_verdict="FAIL")
    try:
        pipeline._finish_test(root)
        s = _state(root)
        if s["current_stage"] == "stuck":
            raise AssertionError("浊龙修不过 3 轮应带病交付，不应进 stuck（挂起违反 PM 决策）")
        if s["current_stage"] != "done":
            raise AssertionError(f"带病交付应置 done，实际 stage={s['current_stage']}")
        report = root / ".harness" / "delivery_report.md"
        if not report.exists():
            raise AssertionError("带病交付必须生成 .harness/delivery_report.md 交付报告")
        text = report.read_text()
        if "遗留问题" not in text:
            raise AssertionError("delivery_report.md 必须含'遗留问题'字样（诚实标注）")
        if "浊龙" not in text:
            raise AssertionError("delivery_report.md 必须写明浊龙黑盒失败这一事实")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac5_zhuolong_pass_clean_done(monkeypatch) -> None:
    """AC5: 浊龙 PASS → 正常 done，不产生 delivery_report.md."""
    monkeypatch.setattr(hermes_propose, "propose", lambda root: None)
    root = _make_project(retreat_count=0, zhuolong_verdict="PASS")
    try:
        pipeline._finish_test(root)
        s = _state(root)
        if s["current_stage"] != "done":
            raise AssertionError(f"浊龙 PASS 应正常 done，实际 stage={s['current_stage']}")
        if (root / ".harness" / "delivery_report.md").exists():
            raise AssertionError("正常交付不应产生 delivery_report.md（带病交付专用）")
    finally:
        shutil.rmtree(root, ignore_errors=True)
