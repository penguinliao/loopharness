# mypy: ignore-errors
# flake8: noqa
"""AC8 + AC9: SPEC prompt 黑盒强制决策 + README 无人值守模式与 Hermes 晨报文档."""
import sys
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(REPO))


def test_ac8_spec_prompt_requires_blackbox_decision() -> None:
    """AC8: prompts/01_spec.md 要求 spec 必须显式决策黑盒测试（启用或写明不需要的理由）."""
    text = (REPO / "prompts" / "01_spec.md").read_text()
    if "黑盒" not in text:
        raise AssertionError("prompts/01_spec.md 没有黑盒测试决策要求")
    if "zhuolong_brief" not in text:
        raise AssertionError("prompts/01_spec.md 没有提到 zhuolong_brief.md（启用黑盒的具体动作）")


def test_ac9_readme_unattended_mode_section() -> None:
    """AC9: README 有无人值守模式章节，含 /loop 和三种结局说明."""
    text = (REPO / "README.md").read_text()
    if "无人值守" not in text:
        raise AssertionError("README.md 缺少'无人值守'模式章节")
    if "/loop" not in text:
        raise AssertionError("README.md 无人值守章节没提 /loop")
    if "delivery_report" not in text and "带病交付" not in text:
        raise AssertionError("README.md 没说明带病交付这种结局（PM 必须知道有这种可能）")


def test_ac9_readme_hermes_morning_report() -> None:
    """AC9: README 有 Hermes 晨报（定时消化 inbox）模板."""
    text = (REPO / "README.md").read_text()
    if "晨报" not in text:
        raise AssertionError("README.md 缺少 Hermes 晨报章节")
