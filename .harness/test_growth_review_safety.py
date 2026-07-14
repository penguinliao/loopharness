# mypy: ignore-errors
# flake8: noqa
"""Growth Batch A 的 reviewer 数据边界和完整性门禁。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from claude_hh import pipeline


ROOT = Path(__file__).absolute().parents[1]


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")


def _git_root(prefix: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=prefix))
    _git(root, "init", "-q")
    return root


def _commit_all(root: Path) -> None:
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=LoopHarness Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-q",
        "-m",
        "baseline",
    )


def test_ac11_tracked_sensitive_internal_and_planning_content_is_filtered() -> None:
    root = _git_root("loopharness_tracked_review_filter_")
    try:
        files = {
            ".env": "TRACKED_ENV_SENTINEL=old\n",
            "task_plan.md": "TRACKED_PLAN_SENTINEL old\n",
            ".harness/internal.md": "TRACKED_HARNESS_SENTINEL old\n",
            "README.md": "# old\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        _commit_all(root)

        (root / ".env").write_text("TRACKED_ENV_SENTINEL=new\n", encoding="utf-8")
        (root / "task_plan.md").write_text("TRACKED_PLAN_SENTINEL new\n", encoding="utf-8")
        (root / ".harness/internal.md").write_text("TRACKED_HARNESS_SENTINEL new\n", encoding="utf-8")
        (root / "README.md").write_text("# safe public change\n", encoding="utf-8")

        review_diff = pipeline._impl_period_diff(root)
        leaked = [
            marker
            for marker in ("TRACKED_ENV_SENTINEL", "TRACKED_PLAN_SENTINEL", "TRACKED_HARNESS_SENTINEL")
            if marker in review_diff
        ]
        if leaked:
            raise AssertionError(f"tracked 私密/内部内容泄露给 reviewer: {leaked}")
        if "safe public change" not in review_diff:
            raise AssertionError("安全的 tracked README 改动被错误过滤")
    finally:
        shutil.rmtree(root)


def test_ac11_untracked_symlink_cannot_read_outside_repository() -> None:
    root = _git_root("loopharness_review_symlink_")
    outside_dir = Path(tempfile.mkdtemp(prefix="loopharness_outside_review_"))
    try:
        outside = outside_dir / "outside.md"
        outside.write_text("OUTSIDE_REVIEW_SENTINEL\n", encoding="utf-8")
        os.symlink(outside, root / "linked-notes.md")
        review_diff = pipeline._impl_period_diff(root)
        if "OUTSIDE_REVIEW_SENTINEL" in review_diff:
            raise AssertionError("untracked symlink 读取并泄露了仓库外内容")
        if "diff --git a/linked-notes.md" in review_diff:
            raise AssertionError("untracked symlink 错误进入 reviewer diff")
    finally:
        shutil.rmtree(root)
        shutil.rmtree(outside_dir)


def test_ac11_current_public_documents_are_visible_to_reviewer() -> None:
    review_diff = pipeline._impl_period_diff(ROOT)
    required = [
        "diff --git a/README.zh-CN.md b/README.zh-CN.md",
        "diff --git a/assets/loopharness-demo.svg b/assets/loopharness-demo.svg",
        "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml",
    ]
    missing = [marker for marker in required if marker not in review_diff]
    if missing:
        raise AssertionError(f"本批新增公开文件未进入 reviewer diff: {missing}")


def test_ac12_oversized_fresh_review_fails_before_claude_call() -> None:
    root = Path(tempfile.mkdtemp(prefix="loopharness_review_limit_fresh_"))
    oversized = "x" * 80_001
    try:
        with patch.object(pipeline, "_impl_period_diff", return_value=oversized):
            with patch.object(pipeline.subprocess, "run", side_effect=AssertionError("不应调用 Claude")):
                ok, reason = pipeline._fresh_context_review(root)
        if ok or "80,000" not in reason:
            raise AssertionError(f"超限 diff 没有在 Claude 调用前 fail-closed: {ok}, {reason}")
    finally:
        shutil.rmtree(root)


def test_ac12_oversized_cross_family_review_fails_before_api_call() -> None:
    root = Path(tempfile.mkdtemp(prefix="loopharness_review_limit_cross_"))
    oversized = "x" * 80_001
    try:
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "dummy"}, clear=False):
            with patch.object(pipeline, "_impl_period_diff", return_value=oversized):
                with patch("urllib.request.urlopen", side_effect=AssertionError("不应调用 API")):
                    ok, reason = pipeline._cross_family_review(root)
        if ok or "80,000" not in reason:
            raise AssertionError(f"超限 diff 没有在 API 调用前 fail-closed: {ok}, {reason}")
    finally:
        shutil.rmtree(root)
