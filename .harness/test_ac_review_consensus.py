# mypy: ignore-errors
# flake8: noqa
"""改进③：REVIEW 门禁 (N-1) 共识 + 完美主义熔断.

测试 FROM spec：此刻 _check_review 仍是"两审查全过才放行"的旧逻辑，
连续相似反对熔断未实现 → test_ac3 应红，正确实现后绿。
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))

from claude_hh import pipeline  # noqa: E402


def _make_project(last_dissent=None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="test_consensus_"))
    h = root / ".harness"
    h.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "current_stage": "review",
        "retreat_count": 0,
        "description": "x",
        "started_at": now,
        "updated_at": now,
        "stage_history": [],
    }
    if last_dissent is not None:
        state["last_review_dissent"] = last_dissent
    (h / "pipeline.json").write_text(json.dumps(state))
    (h / "review_report.md").write_text("# review\n\nPROCEED\n")
    return root


class _Patch:
    """临时替换 pipeline 的两个审查函数 + ruff/mypy，退出时还原."""

    def __init__(self, fresh_ret, cross_ret) -> None:
        self.fresh_ret = fresh_ret
        self.cross_ret = cross_ret

    def __enter__(self):
        self._orig = (
            pipeline._fresh_context_review,
            pipeline._cross_family_review,
            pipeline._ruff_mypy,
        )
        pipeline._fresh_context_review = lambda root: self.fresh_ret
        pipeline._cross_family_review = lambda root: self.cross_ret
        pipeline._ruff_mypy = lambda root: True
        return self

    def __exit__(self, *a) -> None:
        (
            pipeline._fresh_context_review,
            pipeline._cross_family_review,
            pipeline._ruff_mypy,
        ) = self._orig


def test_ac1_both_pass_proceeds() -> None:
    """AC1: 两审查都 PROCEED → 放行（行为不变）."""
    root = _make_project()
    try:
        with _Patch((True, ""), (True, "")):
            ok, _ = pipeline._check_review(root)
        if not ok:
            raise AssertionError("两审查都 PROCEED 应放行")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac2_first_dissent_blocks() -> None:
    """AC2: 首次单边反对仍回炉（保质量，不放水）."""
    root = _make_project()
    try:
        with _Patch((True, ""), (False, "三審说 SQL 没参数化，存在注入风险")):
            ok, _ = pipeline._check_review(root)
        if ok:
            raise AssertionError("首次新反对应回炉，不该放行")
        d = json.loads((root / ".harness" / "pipeline.json").read_text()).get("last_review_dissent", {})
        if not d.get("cross"):
            raise AssertionError("首次反对应记入 last_review_dissent.cross 供下轮比对")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_repeated_similar_dissent_circuit_breaks() -> None:
    """AC3: 同一审查连续 2 轮相似反对 + 另一审查通过 → 熔断放行 + 记 advisory."""
    prev = "三審说 _bump 计数点放在判定前，无效响应仍计数，违反 AC2 实际调用后才计数"
    root = _make_project(last_dissent={"fresh": "", "cross": prev})
    try:
        cur = prev + "（基本同上，还是这个计数点位置问题）"
        with _Patch((True, ""), (False, cur)):
            ok, _ = pipeline._check_review(root)
        if not ok:
            raise AssertionError("连续相似的单边反对应熔断放行（治完美主义死循环）")
        adv = root / ".harness" / "review_advisory.md"
        if not adv.exists():
            raise AssertionError("熔断放行后应把反对记入 review_advisory.md")
        txt = adv.read_text()
        if prev[:12] not in txt:
            raise AssertionError("review_advisory.md 应包含被熔断的反对内容")
        if "Traceback" in txt:
            raise AssertionError("AC5: advisory 不应含内部异常栈")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac4_both_dissent_always_blocks() -> None:
    """AC4: 两审查都反对 → 永不放行（即使各自有历史相似反对）."""
    root = _make_project(last_dissent={"fresh": "二审说 X 问题", "cross": "三審说 Y 问题"})
    try:
        with _Patch((False, "二审说 X 问题 还是没改"), (False, "三審说 Y 问题 还是没改")):
            ok, _ = pipeline._check_review(root)
        if ok:
            raise AssertionError("两审查都反对必须回炉，绝不放行")
    finally:
        shutil.rmtree(root, ignore_errors=True)
