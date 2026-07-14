# mypy: ignore-errors
# flake8: noqa
"""Growth Batch A 的公开产品页最终行为门禁。"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).absolute().parents[1]


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"缺少公开交付文件: {relative}")
    return path.read_text(encoding="utf-8")


def test_ac1_english_first_readme_has_clear_outcome_and_chinese_link() -> None:
    readme = _read("README.md")
    first_screen = readme[:1800].lower()
    required = [
        "[中文](readme.zh-cn.md)",
        "switch coding agents",
        "project memory",
        "done",
        "evidence",
    ]
    missing = [item for item in required if item not in first_screen]
    if missing:
        raise AssertionError(f"英文首屏缺少用户结果或中文入口: {missing}")


def test_ac2_chinese_readme_preserves_honest_cross_agent_boundary() -> None:
    readme = _read("README.zh-CN.md")
    required = ["切换", "项目记忆", "证据", "不会导入", "完整聊天记录", "原生 hook"]
    missing = [item for item in required if item not in readme]
    if missing:
        raise AssertionError(f"中文版缺少能力或边界说明: {missing}")


def test_ac3_accessible_demo_svg_shows_only_real_states() -> None:
    readme = _read("README.md")
    svg = _read("assets/loopharness-demo.svg")
    if "assets/loopharness-demo.svg" not in readme:
        raise AssertionError("英文 README 没有引用真实视觉 Demo")
    required = ["<title>", 'role="img"', "DELIVERY CONTRACT", "CONTEXT BUNDLE", "DECLARED EVIDENCE", "CONTRACT-ONLY", "INVALIDATED"]
    missing = [item for item in required if item not in svg]
    if missing:
        raise AssertionError(f"SVG 缺少可访问性或真实流程状态: {missing}")
    forbidden = ["<script", "Production-ready", "100%", "guaranteed"]
    found = [item for item in forbidden if item.lower() in svg.lower()]
    if found:
        raise AssertionError(f"SVG 含未实现或危险承诺: {found}")


def test_ac4_readme_closes_the_four_agent_handoff_loop() -> None:
    readme = _read("README.md").lower()
    required = [
        "--agent claude",
        "--agent codex",
        "--agent kimi",
        "--agent glm",
        ".delivery/context_bundle.md",
        "harness evidence",
        "harness readiness",
        "does not log in",
    ]
    missing = [item for item in required if item not in readme]
    if missing:
        raise AssertionError(f"四模型交接旅程没有闭环: {missing}")


def test_ac5_real_ci_matrix_and_badge_are_present() -> None:
    readme = _read("README.md")
    workflow = _read(".github/workflows/ci.yml")
    if "actions/workflows/ci.yml/badge.svg" not in readme:
        raise AssertionError("README 仍未展示真实 CI 状态")
    required = ["3.9", "3.13", "pytest", "ruff check", "compileall", "actions/checkout", "actions/setup-python"]
    missing = [item for item in required if item not in workflow]
    if missing:
        raise AssertionError(f"CI 未覆盖承诺的真实门禁: {missing}")


def test_ac6_pyproject_has_official_urls_without_identity_regression() -> None:
    pyproject = _read("pyproject.toml")
    required = [
        'name = "claude-hh"',
        'requires-python = ">=3.9"',
        "[project.urls]",
        'Homepage = "https://github.com/penguinliao/loopharness"',
        'Issues = "https://github.com/penguinliao/loopharness/issues"',
        'Changelog = "https://github.com/penguinliao/loopharness/blob/main/CHANGELOG.md"',
    ]
    missing = [item for item in required if item not in pyproject]
    if missing:
        raise AssertionError(f"Python 项目身份或官方入口不完整: {missing}")


def test_ac7_hn_draft_describes_current_product_without_old_metrics() -> None:
    post = _read("HN_POST_DRAFT.md")
    required = ["LoopHarness", "https://github.com/penguinliao/loopharness", "Claude", "Codex", "Kimi", "GLM", "declared"]
    missing = [item for item in required if item not in post]
    if missing:
        raise AssertionError(f"HN 发布稿没有覆盖当前产品和诚实边界: {missing}")
    forbidden = ["v1.0 ships only", "50% accuracy", "80%+", "Claude H-H"]
    found = [item for item in forbidden if item.lower() in post.lower()]
    if found:
        raise AssertionError(f"HN 发布稿仍含旧版或未证实叙事: {found}")


def test_ac8_readme_has_real_scenario_output_and_no_fake_proof() -> None:
    readme = _read("README.md")
    required = ["Before LoopHarness", "After LoopHarness", "Current delivery level:", "Contract-only", "declared", "verified"]
    missing = [item for item in required if item not in readme]
    if missing:
        raise AssertionError(f"README 缺少真实前后对比或预期输出: {missing}")
    forbidden_patterns = [
        r"guarantee(?:s|d)? production",
        r"automatically migrates? (?:all|your full) chat history",
        r"all four agents have the same native hooks",
        r"turns? .*accuracy.*(?:80|100)%",
    ]
    found = [pattern for pattern in forbidden_patterns if re.search(pattern, readme, re.IGNORECASE)]
    if found:
        raise AssertionError(f"README 含不可证实承诺: {found}")
