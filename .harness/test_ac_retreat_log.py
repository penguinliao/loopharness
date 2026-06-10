# mypy: ignore-errors
# flake8: noqa
"""AC1 + AC2: retreat 错题本落盘 + IMPLEMENT prompt 指示先读错题本."""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import pipeline  # noqa: E402


def _make_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="test_retreatlog_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "current_stage": "test",
        "retreat_count": 0,
        "description": "假任务",
        "started_at": now,
        "updated_at": now,
        "stage_history": [{"stage": "implement", "entered_at": now}, {"stage": "test", "entered_at": now}],
    }
    (h / "pipeline.json").write_text(json.dumps(state))
    return root


def test_ac1_retreat_reason_appended_to_log() -> None:
    """AC1: 每次 retreat 的原因都追加进 retreat_log.md，append-only 不覆盖."""
    root = _make_project()
    try:
        state = json.loads((root / ".harness" / "pipeline.json").read_text())
        pipeline._retreat(root, state, "原因一：测试 test_x 断言 foo 失败")
        state = json.loads((root / ".harness" / "pipeline.json").read_text())
        pipeline._retreat(root, state, "原因二：浊龙黑盒报 FAIL 搜索页白屏")

        log = root / ".harness" / "retreat_log.md"
        if not log.exists():
            raise AssertionError("retreat 之后 .harness/retreat_log.md 不存在（原因没落盘）")
        text = log.read_text()
        if "原因一：测试 test_x 断言 foo 失败" not in text:
            raise AssertionError("第 1 次 retreat 的原因没写进 retreat_log.md")
        if "原因二：浊龙黑盒报 FAIL 搜索页白屏" not in text:
            raise AssertionError("第 2 次 retreat 的原因没写进 retreat_log.md（append 被覆盖了？）")
        if text.index("原因一") > text.index("原因二"):
            raise AssertionError("retreat_log.md 不是按时间顺序追加的")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_log_survives_stuck_transition() -> None:
    """AC1 边界: 第 4 次 retreat 进 stuck 时，原因同样要落盘到 retreat_log.md."""
    root = _make_project()
    try:
        state = json.loads((root / ".harness" / "pipeline.json").read_text())
        state["retreat_count"] = 3
        pipeline._retreat(root, state, "原因四：还是修不过")
        text = (root / ".harness" / "retreat_log.md").read_text()
        if "原因四：还是修不过" not in text:
            raise AssertionError("进 stuck 的那次 retreat 原因没落盘")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac2_implement_prompt_mentions_retreat_log() -> None:
    """AC2: prompts/02_implement.md 指示 AI 先读错题本."""
    prompt = (REPO / "prompts" / "02_implement.md").read_text()
    if "retreat_log.md" not in prompt:
        raise AssertionError("prompts/02_implement.md 没有指示 AI 读 .harness/retreat_log.md")
