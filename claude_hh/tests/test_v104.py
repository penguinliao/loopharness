# mypy: ignore-errors
# flake8: noqa
"""Tests for v1.0.4 -- auto-start protocol via .claude/CLAUDE.md"""
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path


def test_init_writes_claude_md() -> None:
    """harness init creates .claude/CLAUDE.md with auto-start guide"""
    from claude_hh import pipeline as pl
    tmp = Path(tempfile.mkdtemp(prefix="v104_init_"))
    try:
        import argparse
        args = argparse.Namespace(project=str(tmp))
        pl.cmd_init(args)
        md = tmp / ".claude" / "CLAUDE.md"
        if not md.exists():
            raise AssertionError(".claude/CLAUDE.md was not created")
        content = md.read_text()
        if "claude-hh:auto-start-guide" not in content:
            raise AssertionError("guide marker missing")
        if "harness start" not in content:
            raise AssertionError("start instruction missing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_init_idempotent_on_existing_guide() -> None:
    """Re-running init does not duplicate the H-H guide section"""
    from claude_hh import pipeline as pl
    tmp = Path(tempfile.mkdtemp(prefix="v104_idempo_"))
    try:
        import argparse
        args = argparse.Namespace(project=str(tmp))
        pl.cmd_init(args)
        first = (tmp / ".claude" / "CLAUDE.md").read_text()
        pl.cmd_init(args)
        second = (tmp / ".claude" / "CLAUDE.md").read_text()
        if first != second:
            raise AssertionError("re-running init changed content (not idempotent)")
        # Count only the opening tag (closing tag also contains the substring)
        opening_count = second.count("<!-- claude-hh:auto-start-guide v")
        if opening_count != 1:
            raise AssertionError(f"opening guide tag appeared {opening_count} times, expected 1")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_init_preserves_existing_user_claude_md() -> None:
    """If .claude/CLAUDE.md already exists with user content, append (do not overwrite)"""
    from claude_hh import pipeline as pl
    tmp = Path(tempfile.mkdtemp(prefix="v104_preserve_"))
    try:
        (tmp / ".claude").mkdir()
        original = "# My project" + chr(10) + chr(10) + "This is my own CLAUDE.md content." + chr(10)
        (tmp / ".claude" / "CLAUDE.md").write_text(original)
        import argparse
        args = argparse.Namespace(project=str(tmp))
        pl.cmd_init(args)
        result = (tmp / ".claude" / "CLAUDE.md").read_text()
        if "My project" not in result:
            raise AssertionError("existing user content was lost")
        if "claude-hh:auto-start-guide" not in result:
            raise AssertionError("guide was not appended")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
