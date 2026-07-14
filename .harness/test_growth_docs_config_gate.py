# mypy: ignore-errors
# flake8: noqa
"""IMPLEMENT 门禁对真实文档/配置任务的根因回归。"""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claude_hh.pipeline import _check_impl


def _state(entered_at: datetime) -> dict[str, object]:
    return {
        "stage_history": [{"stage": "implement", "entered_at": entered_at.isoformat()}],
        "retreat_count": 0,
    }


def _temporary_root(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def test_ac10_recent_markdown_counts_as_real_implementation() -> None:
    root = _temporary_root("loopharness_docs_gate_md_")
    try:
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        (root / "README.md").write_text("# Product\n", encoding="utf-8")
        ok, reason = _check_impl(root, _state(entered))
        if not ok:
            raise AssertionError(f"近期 README 产品改动被错误拒绝: {reason}")
    finally:
        shutil.rmtree(root)


def test_ac10_recent_config_and_svg_count_as_real_implementation() -> None:
    root = _temporary_root("loopharness_docs_gate_config_")
    try:
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        workflow = root / ".github" / "workflows" / "ci.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: CI\n", encoding="utf-8")
        (root / "hero.svg").write_text("<svg/>\n", encoding="utf-8")
        ok, reason = _check_impl(root, _state(entered))
        if not ok:
            raise AssertionError(f"近期配置/视觉产品改动被错误拒绝: {reason}")
    finally:
        shutil.rmtree(root)


def test_ac10_harness_planning_and_cache_files_do_not_count() -> None:
    root = _temporary_root("loopharness_docs_gate_noise_")
    try:
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        harness_test = root / ".harness" / "test_noise.py"
        harness_test.parent.mkdir(parents=True)
        harness_test.write_text("print('noise')\n", encoding="utf-8")
        (root / "task_plan.md").write_text("noise\n", encoding="utf-8")
        cache_file = root / ".pytest_cache" / "state.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{}\n", encoding="utf-8")
        ok, _reason = _check_impl(root, _state(entered))
        if ok:
            raise AssertionError("Harness/planning/cache 运行物错误冒充了产品实现")
    finally:
        shutil.rmtree(root)


def test_ac10_stale_product_file_does_not_count_for_current_stage() -> None:
    root = _temporary_root("loopharness_docs_gate_stale_")
    try:
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        readme = root / "README.md"
        readme.write_text("# Old product\n", encoding="utf-8")
        stale = (entered - timedelta(seconds=10)).timestamp()
        os.utime(readme, (stale, stale))
        ok, _reason = _check_impl(root, _state(entered))
        if ok:
            raise AssertionError("早于 IMPLEMENT 阶段的旧文档错误冒充了本轮实现")
    finally:
        shutil.rmtree(root)


def test_ac10_recent_python_code_still_counts() -> None:
    root = _temporary_root("loopharness_docs_gate_python_")
    try:
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        ok, reason = _check_impl(root, _state(entered))
        if not ok:
            raise AssertionError(f"原有 Python 实现门禁发生回退: {reason}")
    finally:
        shutil.rmtree(root)
