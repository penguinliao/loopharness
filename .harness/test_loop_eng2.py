# mypy: ignore-errors
# flake8: noqa
"""loop 化②：外测独立验收(不押注浊龙) + fresh-context 派工指令。

AC1 外测放行只看 external_review，不看浊龙
AC2 浊龙仅旁证、永不改判
AC3 外测 FAIL 自动回炉；预算耗尽带病交付；永不挂起
AC4 错题本每轮 fresh worker 必读 + 有界派工指令
AC5 独立验收跑在干净上下文、fail-open（落在 prompts/06_external_test.md）
"""
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent  # symlink-safe: .absolute() 不展开
import sys
sys.path.insert(0, str(REPO))

from claude_hh import pipeline  # noqa: E402

PASS_REPORT = "# 独立验收\n\n逐条核对 AC，全部满足。\n\n判定：PASS\n"
FAIL_REPORT = "# 独立验收\n\nAC2 未满足：浊龙仍参与门禁。\n\n判定：FAIL\n"
NO_VERDICT = "# 独立验收\n\n还在核对中……\n"


def _mk(external: str = None, zhuolong: str = None, retreat_count: int = 0) -> Path:
    """临时假项目：可选写 external_review.md / zhuolong_report.md。"""
    root = Path(tempfile.mkdtemp(prefix="test_loopeng2_"))
    h = root / ".harness"
    h.mkdir()
    if external is not None:
        (h / "external_review.md").write_text(external)
    if zhuolong is not None:
        (h / "zhuolong_report.md").write_text(zhuolong)
    return root, {"current_stage": "test", "retreat_count": retreat_count}


# ---------- AC1：外测放行只看 external_review ----------

def test_ac1_external_pass_returns_pass() -> None:
    root, _ = _mk(external=PASS_REPORT)
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "pass":
            raise AssertionError(f"external_review=PASS 应返回 pass，实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_external_fail_returns_fail() -> None:
    root, _ = _mk(external=FAIL_REPORT)
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "fail":
            raise AssertionError(f"external_review=FAIL 应返回 fail，实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_external_missing_returns_wait() -> None:
    root, _ = _mk(external=None)
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "wait":
            raise AssertionError(f"external_review 缺失应返回 wait（不烧预算），实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_external_no_verdict_returns_wait() -> None:
    root, _ = _mk(external=NO_VERDICT)
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "wait":
            raise AssertionError(f"external_review 无判定应返回 wait，实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_external_pass_with_zhuolong_fail_still_pass() -> None:
    """浊龙 FAIL 不拦：external PASS 即放行。"""
    root, _ = _mk(external=PASS_REPORT, zhuolong="判定：FAIL\n")
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "pass":
            raise AssertionError(f"external PASS + 浊龙 FAIL 仍应 pass（浊龙不拦），实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac1_external_fail_with_zhuolong_pass_still_fail() -> None:
    """浊龙 PASS 不放水：external FAIL 即回炉。"""
    root, _ = _mk(external=FAIL_REPORT, zhuolong="判定：PASS\n")
    try:
        status, _msg = pipeline._check_external_review(root)
        if status != "fail":
            raise AssertionError(f"external FAIL + 浊龙 PASS 仍应 fail（浊龙不放水），实际 {status}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------- AC2：浊龙仅旁证、永不改判 ----------

def test_ac2_zhuolong_variants_never_change_decision() -> None:
    """同一 external 判定下，浊龙 PASS/FAIL/缺失三种，门禁决策必须完全一致。"""
    results = []
    for z in ("判定：PASS\n", "判定：FAIL\n", None):
        root, state = _mk(external=PASS_REPORT, zhuolong=z)
        try:
            results.append(pipeline._check_external_review(root)[0])
            # 经 _external_gate 同样验证一次
            action, _ = pipeline._external_gate(root, state)
            results.append(action)
        finally:
            shutil.rmtree(root, ignore_errors=True)
    if len(set(results)) != 1:
        raise AssertionError(f"浊龙不同取值改变了门禁决策（应全部一致）：{results}")


# ---------- AC3：外测 FAIL 回炉 / 预算耗尽带病交付 / 永不挂起 ----------

def test_ac3_external_fail_under_budget_retreats() -> None:
    root, state = _mk(external=FAIL_REPORT, retreat_count=0)
    try:
        action, _msg = pipeline._external_gate(root, state)
        if action != "retreat":
            raise AssertionError(f"external FAIL 且预算未耗尽应 retreat，实际 {action}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_external_fail_budget_exhausted_degraded() -> None:
    root, state = _mk(external=FAIL_REPORT, retreat_count=3)
    try:
        action, _msg = pipeline._external_gate(root, state)
        if action != "degraded":
            raise AssertionError(f"external FAIL 且 retreat_count>=3 应带病交付(degraded)，实际 {action}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_external_pass_gate_passes() -> None:
    root, state = _mk(external=PASS_REPORT, retreat_count=0)
    try:
        action, _msg = pipeline._external_gate(root, state)
        if action != "pass":
            raise AssertionError(f"external PASS 应放行(pass)，实际 {action}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac3_external_missing_gate_waits() -> None:
    """永不挂起的前提：缺验收时是 wait（等独立 agent），不烧 retreat 预算也不卡死。"""
    root, state = _mk(external=None, retreat_count=0)
    try:
        action, _msg = pipeline._external_gate(root, state)
        if action != "wait":
            raise AssertionError(f"external 缺失应 wait，实际 {action}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------- AC4：错题本必读 + 有界派工（prompts/02_implement.md）----------

def test_ac4_implement_prompt_reads_errata_and_bounded_dispatch() -> None:
    p = REPO / "prompts" / "02_implement.md"
    if not p.exists():
        raise AssertionError("prompts/02_implement.md 不存在")
    text = p.read_text()
    if "retreat_log" not in text:
        raise AssertionError("02_implement.md 必须指示先读 retreat_log.md（错题本）")
    if "子 agent" not in text and "子Agent" not in text and "fresh" not in text.lower():
        raise AssertionError("02_implement.md 必须含 fresh 子 agent 派工指令")


# ---------- AC5：独立验收干净上下文 + fail-open（prompts/06_external_test.md）----------

def test_ac5_external_prompt_clean_context_and_failopen() -> None:
    p = REPO / "prompts" / "06_external_test.md"
    if not p.exists():
        raise AssertionError("prompts/06_external_test.md 不存在")
    text = p.read_text()
    if "external_review.md" not in text:
        raise AssertionError("06_external_test.md 必须说明判定写入 external_review.md")
    if "只看" not in text and "看不到" not in text:
        raise AssertionError("06_external_test.md 必须约束独立 agent 只看 spec+产物、看不到实现过程")
    if "fail-open" not in text.lower() and "不阻塞" not in text:
        raise AssertionError("06_external_test.md 必须声明验收工具不可用时 fail-open 不阻塞")
