# mypy: ignore-errors
# flake8: noqa
"""Loop 护栏强化①：错题本物理注入(AC1/AC6) + retreat 原地打转提前升级(AC2/AC3/AC4).

测试 FROM spec，不 from code：此刻 _retreat_briefing / _reason_similar 尚不存在，
本文件应在 SPEC 阶段红、IMPLEMENT 正确实现后绿。
"""
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import antagonist  # noqa: E402
from claude_hh import pipeline  # noqa: E402


def _make_project(stage: str = "test", retreat_count: int = 0) -> Path:
    root = Path(tempfile.mkdtemp(prefix="test_loopguard_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "current_stage": stage,
        "retreat_count": retreat_count,
        "description": "假任务",
        "started_at": now,
        "updated_at": now,
        "stage_history": [{"stage": "implement", "entered_at": now}],
    }
    (h / "pipeline.json").write_text(json.dumps(state))
    return root


def _stage(root: Path) -> str:
    return json.loads((root / ".harness" / "pipeline.json").read_text())["current_stage"]


def _state(root: Path) -> dict:
    return json.loads((root / ".harness" / "pipeline.json").read_text())


def test_ac1_briefing_aggregates_recent_reasons() -> None:
    """AC1: _retreat_briefing 汇总最近失败原因，供物理注入用（不靠 AI 主动去读）。"""
    root = _make_project()
    try:
        pipeline._retreat(root, _state(root), "原因一：test_x 断言 foo 失败")
        pipeline._retreat(root, _state(root), "原因二：review 评分 52 偏低 mypy 报错")
        if not hasattr(pipeline, "_retreat_briefing"):
            raise AssertionError("pipeline 缺少 _retreat_briefing(root) helper（错题本物理注入未实现）")
        brief = pipeline._retreat_briefing(root)
        if "原因一" not in brief or "原因二" not in brief:
            raise AssertionError(f"_retreat_briefing 没汇总最近失败原因，实际：{brief!r}")
        if "Traceback" in brief:
            raise AssertionError("AC5: 错题本摘要不应包含内部异常栈 Traceback")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_retreat_output_contains_briefing(capsys) -> None:
    """AC1: _retreat 回 IMPLEMENT 的输出里直接带最近失败摘要，不只打印当前一条。"""
    root = _make_project()
    try:
        pipeline._retreat(root, _state(root), "原因甲：bandit 报 SQL 注入风险")
        capsys.readouterr()  # 清掉第 1 次输出
        pipeline._retreat(root, _state(root), "原因乙：浊龙黑盒搜索页白屏")
        out = capsys.readouterr().out
        if "原因甲" not in out:
            raise AssertionError(f"第 2 次 retreat 输出没把上一轮失败(原因甲)一并呈现，实际：{out!r}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac2_repeat_failure_triggers_early_stuck() -> None:
    """AC2: 连续 2 次几乎相同的失败原因 → 提前转 stuck，不等满 3 次。"""
    root = _make_project()
    try:
        r = "review 评分 52，type_safety 维度 mypy 报 3 个 error 没过"
        pipeline._retreat(root, _state(root), r)
        if _stage(root) != "implement":
            raise AssertionError("第 1 次 retreat 不该 stuck")
        pipeline._retreat(root, _state(root), r + "（基本同上，还是那 3 个 mypy error）")
        if _stage(root) != "stuck":
            raise AssertionError(f"连续 2 次相似失败应提前 stuck，实际 stage={_stage(root)}")
        notice = (root / ".harness" / "stuck_notice.md").read_text()
        if not any(k in notice for k in ("原地打转", "重复", "同一", "同样")):
            raise AssertionError(f"stuck_notice 没说明是原地打转/重复同一问题，实际：{notice[:150]}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_reuses_antagonist_similarity_threshold() -> None:
    """AC3: 原地打转判定复用 antagonist 的相似度阈值与算法，不新造数字。"""
    if not hasattr(pipeline, "_reason_similar"):
        raise AssertionError("pipeline 缺少 _reason_similar(a,b) helper")
    if getattr(pipeline, "SIMILARITY_THRESHOLD", None) != antagonist.SIMILARITY_THRESHOLD:
        raise AssertionError("pipeline.SIMILARITY_THRESHOLD 必须复用 antagonist.SIMILARITY_THRESHOLD，不能另写一个数")
    if not pipeline._reason_similar("mypy 报 3 个 error 没过", "mypy 报 3 个 error 没过"):
        raise AssertionError("完全相同的失败原因应判为相似")
    if pipeline._reason_similar("mypy 类型错误", "浊龙黑盒搜索页整页白屏崩溃，完全不同的另一类问题"):
        raise AssertionError("完全不同的失败原因不该判为相似")


def test_ac4_distinct_failures_keep_three_retry_budget() -> None:
    """AC4: 原因各不相同时，保持原 3 次上限（第 4 次才 stuck），新机制不误伤。"""
    root = _make_project()
    try:
        reasons = [
            "mypy 严格模式报 Optional 未处理",
            "浊龙黑盒：注册成功但跳转后页面空白",
            "bandit 扫出 f-string 拼接 SQL 注入",
            "pytest test_login 因连接未关闭超时",
        ]
        for i, r in enumerate(reasons):
            pipeline._retreat(root, _state(root), r)
            stage = _stage(root)
            if i < 3 and stage != "implement":
                raise AssertionError(f"第 {i + 1} 次不同原因 retreat 不该提前 stuck，实际 {stage}")
        if _stage(root) != "stuck":
            raise AssertionError("第 4 次（超 3 次硬上限）应正常 stuck")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac6_pre_edit_surfaces_briefing_in_implement() -> None:
    """AC6: implement 阶段 + 有 retreat_log 时，pre_edit 改代码前输出错题本提要且不阻断。"""
    root = _make_project(stage="implement", retreat_count=1)
    try:
        (root / ".harness" / "retreat_log.md").write_text(
            "# 错题本\n\n## 第 1 次没过 — 2026-06-15\n\n原因X：review 评分不够 mypy 报错\n\n"
        )
        codefile = root / "app.py"
        codefile.write_text("x = 1\n")
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(codefile)}})
        hook = REPO / "hooks" / "pre_edit.py"
        p = subprocess.run(
            [sys.executable, str(hook)], input=payload, capture_output=True, text=True
        )
        out = p.stdout + p.stderr
        if "原因X" not in out and "错题本" not in out:
            raise AssertionError(f"pre_edit 在 implement 阶段没呈现错题本提要，输出：{out!r}")
        if p.returncode == 2:
            raise AssertionError("pre_edit 不该阻断 implement 阶段的合法代码编辑（应 exit 0）")
    finally:
        shutil.rmtree(root, ignore_errors=True)
