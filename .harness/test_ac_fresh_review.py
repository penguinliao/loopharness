# mypy: ignore-errors
# flake8: noqa
"""AC1-AC6: Claude 干净上下文二审（自动化双重验证）."""
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import pipeline  # noqa: E402


class _FakeResult:
    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _make_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="test_freshrev_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    (h / "pipeline.json").write_text(json.dumps({
        "current_stage": "review", "retreat_count": 0, "description": "假任务",
        "stage_history": [{"stage": "implement", "entered_at": now}, {"stage": "review", "entered_at": now}],
    }))
    (h / "spec.md").write_text("# 假 spec\n\n| AC1 | x | P0 |\n")
    (h / "review_report.md").write_text("# 自审\n\n看过了。\n\nPROCEED\n")
    return root


def _patch_claude(monkeypatch, result, calls: list) -> None:
    """只拦 claude 调用，其余 subprocess 原样放行."""
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        if cmd and cmd[0] == "claude":
            calls.append(cmd)
            if isinstance(result, BaseException):
                raise result
            return result
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)


def test_ac1_proceed_passes(monkeypatch) -> None:
    """AC1: claude 末行 PROCEED → 二审通过."""
    root = _make_project()
    try:
        monkeypatch.setattr(pipeline, "_impl_period_diff", lambda r: "+ fake diff line")
        calls: list = []
        _patch_claude(monkeypatch, _FakeResult(0, "审查意见若干\n\nPROCEED"), calls)
        ok, msg = pipeline._fresh_context_review(root)
        if not ok:
            raise AssertionError(f"末行 PROCEED 应通过，实际 ok={ok} msg={msg}")
        if len(calls) != 1:
            raise AssertionError(f"应恰好调用 claude 一次，实际 {len(calls)} 次")
        prompt = calls[0][2] if len(calls[0]) > 2 else calls[0][-1]
        if "fake diff line" not in prompt:
            raise AssertionError("二审 prompt 里没有本期 diff")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac2_fail_returns_block_with_keyword(monkeypatch) -> None:
    """AC2: claude 末行 FAIL → 返回不通过，消息含'判定不通过'+原因."""
    root = _make_project()
    try:
        monkeypatch.setattr(pipeline, "_impl_period_diff", lambda r: "+ fake diff line")
        _patch_claude(monkeypatch, _FakeResult(0, "发现问题\n\nFAIL: 带病交付分支漏判 None"), [])
        ok, msg = pipeline._fresh_context_review(root)
        if ok:
            raise AssertionError("末行 FAIL 应返回不通过")
        if "判定不通过" not in msg:
            raise AssertionError(f"FAIL 消息必须含'判定不通过'（自动回炉关键词），实际：{msg}")
        if "带病交付分支漏判 None" not in msg:
            raise AssertionError(f"FAIL 消息必须带上原因（要进错题本），实际：{msg}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_fail_open(monkeypatch) -> None:
    """AC3: CLI 缺失/超时/退出码非0/输出无法解析 → 一律放行."""
    root = _make_project()
    try:
        monkeypatch.setattr(pipeline, "_impl_period_diff", lambda r: "+ fake diff line")
        cases = [
            FileNotFoundError("claude not found"),
            subprocess.TimeoutExpired(cmd="claude", timeout=180),
            _FakeResult(1, "boom"),
            _FakeResult(0, "我觉得还行但忘了给判定"),
            _FakeResult(0, ""),
        ]
        for case in cases:
            _patch_claude(monkeypatch, case, [])
            ok, msg = pipeline._fresh_context_review(root)
            if not ok:
                raise AssertionError(f"fail-open 失效：{case!r} 应放行，实际 msg={msg}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac4_empty_diff_skips_claude(monkeypatch) -> None:
    """AC4: diff 为空 → 不调用 claude 直接放行."""
    root = _make_project()
    try:
        monkeypatch.setattr(pipeline, "_impl_period_diff", lambda r: "")
        calls: list = []
        _patch_claude(monkeypatch, _FakeResult(0, "PROCEED"), calls)
        ok, _ = pipeline._fresh_context_review(root)
        if not ok:
            raise AssertionError("空 diff 应放行")
        if calls:
            raise AssertionError("空 diff 不应调用 claude（浪费额度）")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac5_review_chain_order_and_short_circuit(monkeypatch) -> None:
    """AC5: 顺序 自审→ruff/mypy→二审→三审；前面不过后面不执行."""
    root = _make_project()
    try:
        order: list = []
        monkeypatch.setattr(pipeline, "_ruff_mypy", lambda r: (order.append("static"), False)[1])
        monkeypatch.setattr(
            pipeline, "_fresh_context_review",
            lambda r: (order.append("fresh"), (True, ""))[1],
        )
        monkeypatch.setattr(
            pipeline, "_cross_family_review",
            lambda r: (order.append("cross"), (True, ""))[1],
        )
        ok, _ = pipeline._check_review(root)
        if ok:
            raise AssertionError("静态检查不过时 _check_review 应返回不通过")
        if "fresh" in order or "cross" in order:
            raise AssertionError(f"静态检查不过时不应烧 LLM 额度，实际执行链：{order}")

        # 静态过、二审 FAIL → 三审不执行
        order.clear()
        monkeypatch.setattr(pipeline, "_ruff_mypy", lambda r: (order.append("static"), True)[1])
        monkeypatch.setattr(
            pipeline, "_fresh_context_review",
            lambda r: (order.append("fresh"), (False, "二审判定不通过：X"))[1],
        )
        ok2, msg2 = pipeline._check_review(root)
        if ok2:
            raise AssertionError("二审 FAIL 时 _check_review 应返回不通过")
        if "判定不通过" not in msg2:
            raise AssertionError(f"二审 FAIL 消息应原样上抛，实际：{msg2}")
        if order != ["static", "fresh"]:
            raise AssertionError(f"执行链应为 static→fresh 且 cross 被短路，实际：{order}")

        # 全过 → 三道都执行且顺序正确
        order.clear()
        monkeypatch.setattr(
            pipeline, "_fresh_context_review",
            lambda r: (order.append("fresh"), (True, ""))[1],
        )
        ok3, _ = pipeline._check_review(root)
        if not ok3:
            raise AssertionError("三道全过时 _check_review 应通过")
        if order != ["static", "fresh", "cross"]:
            raise AssertionError(f"执行链顺序应为 static→fresh→cross，实际：{order}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac6_cross_family_fail_msg_has_retreat_keyword() -> None:
    """AC6: 跨家族 FAIL 消息含'判定不通过'（源码级检查 + cmd_advance 关键词表对照）."""
    src = (REPO / "claude_hh" / "pipeline.py").read_text()
    if '"独立审查判定不通过' not in src and "f\"独立审查判定不通过" not in src:
        raise AssertionError(
            "_cross_family_review 的 FAIL 消息应含'独立审查判定不通过'，"
            "否则 cmd_advance 关键词匹配不到，FAIL 后卡死在 REVIEW 阶段"
        )
    if '"判定不通过"' not in src:
        raise AssertionError("cmd_advance 的回炉关键词表里应有'判定不通过'")


def test_ac7_ac8_docs() -> None:
    """AC7/AC8: prompts/03_review.md 与 README 说明二审."""
    review_doc = (REPO / "prompts" / "03_review.md").read_text()
    if "二审" not in review_doc:
        raise AssertionError("prompts/03_review.md 没有说明二审机制")
    readme = (REPO / "README.md").read_text()
    if "二审" not in readme:
        raise AssertionError("README 无人值守章节没更新二审说明")
