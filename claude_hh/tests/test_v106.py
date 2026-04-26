# mypy: ignore-errors
# flake8: noqa
"""Tests for v1.0.6 — priority override against legacy global CLAUDE.md"""
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path


def test_guide_contains_priority_override() -> None:
    """The guide must contain explicit override against v0.3.x patterns"""
    from claude_hh.pipeline import CLAUDE_MD_GUIDE
    must_have = [
        "Priority Override",
        "v0.3.x",
        "python3 -m harness.pipeline",
        "harness-engineering",
        "Do **NOT** spawn sub-agents",
        "read freely",
        "--route=",
        "--project=",
    ]
    missing = [m for m in must_have if m not in CLAUDE_MD_GUIDE]
    if missing:
        raise AssertionError(f"override section missing key phrases: {missing}")


def test_init_writes_v106_guide() -> None:
    """harness init in fresh project writes the v1.0.6 guide content"""
    from claude_hh import pipeline as pl
    tmp = Path(tempfile.mkdtemp(prefix="v106_init_"))
    try:
        import argparse
        args = argparse.Namespace(project=str(tmp))
        pl.cmd_init(args)
        md = tmp / "CLAUDE.md"
        if not md.exists():
            raise AssertionError("CLAUDE.md was not created")
        content = md.read_text()
        if "claude-hh:auto-start-guide v1.0.6" not in content:
            raise AssertionError("v1.0.6 marker missing")
        if "Priority Override" not in content:
            raise AssertionError("priority override section missing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_init_replaces_older_version_marker() -> None:
    """Re-running init from older v1.0.4/v1.0.5 should replace the block"""
    from claude_hh import pipeline as pl
    tmp = Path(tempfile.mkdtemp(prefix="v106_replace_"))
    try:
        # Simulate an existing v1.0.4 marker block
        old_block = (
            "<!-- claude-hh:auto-start-guide v1.0.4 -->\n\n"
            "## Old\n\n<!-- /claude-hh:auto-start-guide -->\n"
        )
        (tmp / "CLAUDE.md").write_text("# My project\n\n" + old_block)

        import argparse
        args = argparse.Namespace(project=str(tmp))
        pl.cmd_init(args)

        result = (tmp / "CLAUDE.md").read_text()
        # User content preserved
        if "# My project" not in result:
            raise AssertionError("user content lost after re-init")
        # Old version marker must be gone
        if "v1.0.4 -->" in result:
            raise AssertionError("old version marker not replaced")
        # New version marker must be present
        if "claude-hh:auto-start-guide v1.0.6" not in result:
            raise AssertionError("new version marker missing")
        # Must not have duplicate blocks
        count = result.count("<!-- claude-hh:auto-start-guide")
        if count != 1:
            raise AssertionError(f"expected 1 auto-start-guide block, found {count}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
