# mypy: ignore-errors
# flake8: noqa
"""Tests for v1.0.3 features (Hermes 三层 + feedback + propose 拆两段)."""
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------- Test 1: 三层合并 - 只有 L0 时退化等价 v1.0 ----------
def test_load_layers_only_builtin_equals_v1() -> None:
    from claude_hh.hermes_loader import load_layers, L0_BUILTIN
    if not L0_BUILTIN.exists():
        pytest.skip("builtin not installed")
    out = load_layers(None)
    if not out:
        pytest.skip("builtin empty")
    if "Hermes implicit expectations" not in out:
        raise AssertionError("merged output should have header")


# ---------- Test 2: 三层合并 - L2 同名 bullet 覆盖 L0 ----------
def test_load_layers_l2_overrides_l0() -> None:
    from claude_hh.hermes_loader import project_l2, load_layers
    tmpdir = Path(tempfile.mkdtemp(prefix="hermes_l2_"))
    try:
        l2 = project_l2(tmpdir)
        l2.parent.mkdir(parents=True, exist_ok=True)
        l2_content = "## Search / list / detail endpoints" + chr(10) + chr(10) + "- **Partial match** — exact match required for this project (admin tool)." + chr(10)
        l2.write_text(l2_content)
        out = load_layers(tmpdir)
        if "exact match required for this project" not in out:
            raise AssertionError("L2 override not applied")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------- Test 3: v1.0 老用户升级 - L1 旧路径仍加载 ----------
def test_l1_legacy_path_still_loads() -> None:
    from claude_hh.hermes_loader import L1_USER
    if L1_USER.name != "implicit_expectations.md":
        raise AssertionError(f"L1 path should preserve v1.0 filename, got {L1_USER.name}")


# ---------- Test 4: feedback 写入 inbox（不调 LLM）----------
def test_feedback_writes_inbox() -> None:
    from claude_hh import pipeline as pl
    import argparse, json
    tmpdir = Path(tempfile.mkdtemp(prefix="fb_"))
    try:
        (tmpdir / ".harness").mkdir(parents=True, exist_ok=True)
        state = {"current_stage": "done", "retreat_count": 0, "description": "x",
                 "started_at": "x", "updated_at": "x", "stage_history": []}
        (tmpdir / ".harness" / "pipeline.json").write_text(json.dumps(state))
        args = argparse.Namespace(project=str(tmpdir), text=["搜索应能搜到自己"])
        pl.cmd_feedback(args)
        inbox = tmpdir / ".harness" / "inbox.md"
        if not inbox.exists():
            raise AssertionError("inbox.md not created")
        content = inbox.read_text()
        if "搜索应能搜到自己" not in content:
            raise AssertionError(f"feedback content missing: {content}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------- Test 5: inbox 消化后被归档 ----------
def test_inbox_archived_after_propose() -> None:
    from claude_hh import hermes_propose
    tmpdir = Path(tempfile.mkdtemp(prefix="inbox_arch_"))
    try:
        (tmpdir / ".harness").mkdir(parents=True, exist_ok=True)
        inbox = tmpdir / ".harness" / "inbox.md"
        inbox.write_text("- [2026-04-26] PM 说搜索不能搜到自己" + chr(10))
        with patch.object(
            hermes_propose,
            "_claude_p",
            return_value="- **search-include-self** — Search/list should not exclude current user.",
        ):
            n = hermes_propose.propose_from_inbox(tmpdir)
        if inbox.exists():
            raise AssertionError("inbox.md should be archived (moved away)")
        archives = list((tmpdir / ".harness").glob("inbox.archive.*.md"))
        if not archives:
            raise AssertionError("inbox should be archived with timestamp")
        if n < 1:
            raise AssertionError(f"expected proposals from inbox, got n={n}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------- Test 6: review 读两个 proposed 文件并标来源 ----------
def test_review_reads_both_proposed_with_source() -> None:
    from claude_hh.hermes_propose import _read_proposals
    tmpdir = Path(tempfile.mkdtemp(prefix="review_"))
    try:
        h = tmpdir / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "proposed_auto.md").write_text("# auto" + chr(10) + chr(10) + "- **rule-from-auto** — desc" + chr(10))
        (h / "proposed_feedback.md").write_text("# fb" + chr(10) + chr(10) + "- **rule-from-fb** — desc" + chr(10))
        items = _read_proposals(tmpdir)
        sources = sorted({src for src, _ in items})
        if sources != ["auto", "feedback"]:
            raise AssertionError(f"expected both sources tagged, got {sources}")
        if len(items) != 2:
            raise AssertionError(f"expected 2 items, got {len(items)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
