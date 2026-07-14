"""Regression tests for document/config-only IMPLEMENT stages."""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from claude_hh import pipeline
from claude_hh.pipeline import _check_impl, _impl_period_diff


ROOT = Path(__file__).absolute().parents[2]


def _state(entered_at: datetime) -> dict[str, object]:
    return {
        "stage_history": [{"stage": "implement", "entered_at": entered_at.isoformat()}],
        "retreat_count": 0,
    }


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


def _write_pipeline_state(root: Path, entered_at: datetime) -> None:
    harness_dir = root / ".harness"
    harness_dir.mkdir(exist_ok=True)
    state = {
        "current_stage": "review",
        "stage_history": [{"stage": "implement", "entered_at": entered_at.isoformat()}],
    }
    (harness_dir / "pipeline.json").write_text(json.dumps(state), encoding="utf-8")


def test_untracked_readme_is_a_real_implementation() -> None:
    root = _git_root("loopharness_untracked_docs_")
    try:
        (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        _commit_all(root)
        entered = datetime.now(timezone.utc) + timedelta(seconds=1)
        readme = root / "README.md"
        readme.write_text("# New product\n", encoding="utf-8")
        recent = (entered + timedelta(seconds=2)).timestamp()
        os.utime(readme, (recent, recent))
        ok, reason = _check_impl(root, _state(entered))
        if not ok:
            raise AssertionError(f"纯新增 README 被误判为空壳: {reason}")
    finally:
        shutil.rmtree(root)


def test_old_diff_plus_htmlcov_does_not_fake_current_implementation() -> None:
    root = _git_root("loopharness_htmlcov_noise_")
    try:
        tracked = root / "tracked.md"
        tracked.write_text("baseline\n", encoding="utf-8")
        _commit_all(root)

        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        tracked.write_text("old uncommitted change\n", encoding="utf-8")
        stale = (entered - timedelta(seconds=10)).timestamp()
        os.utime(tracked, (stale, stale))

        generated = root / "htmlcov" / "index.html"
        generated.parent.mkdir()
        generated.write_text("generated coverage\n", encoding="utf-8")

        ok, _reason = _check_impl(root, _state(entered))
        if ok:
            raise AssertionError("阶段前旧 diff + htmlcov 生成物错误冒充了本轮实现")
    finally:
        shutil.rmtree(root)


def test_review_diff_includes_untracked_documents_and_config() -> None:
    root = _git_root("loopharness_review_docs_")
    try:
        files = {
            "README.md": "# Public product\n",
            "assets/hero.svg": "<svg/>\n",
            ".github/workflows/ci.yml": "name: CI\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        review_diff = _impl_period_diff(root)
        missing = [
            relative
            for relative in files
            if f"diff --git a/{relative} b/{relative}" not in review_diff
        ]
        if missing:
            raise AssertionError(f"自动审查 diff 看不到新增公开文件: {missing}")
    finally:
        shutil.rmtree(root)


def test_hn_demo_creates_every_input_before_using_it() -> None:
    draft = (ROOT / "HN_POST_DRAFT.md").read_text(encoding="utf-8")
    required = ["mkdir -p docs", "docs/brief.md", "functional.txt"]
    missing = [item for item in required if item not in draft]
    if missing:
        raise AssertionError(f"HN 最短 Demo 缺少可执行输入创建步骤: {missing}")


def test_review_diff_filters_tracked_sensitive_and_internal_files() -> None:
    root = _git_root("loopharness_public_review_filter_")
    try:
        files = {
            ".env": "PUBLIC_ENV_SENTINEL=old\n",
            "task_plan.md": "PUBLIC_PLAN_SENTINEL old\n",
            ".harness/internal.md": "PUBLIC_HARNESS_SENTINEL old\n",
            "README.md": "# old\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        _commit_all(root)
        for relative in files:
            (root / relative).write_text(files[relative].replace("old", "new"), encoding="utf-8")

        review_diff = _impl_period_diff(root)
        leaked = [
            marker
            for marker in ("PUBLIC_ENV_SENTINEL", "PUBLIC_PLAN_SENTINEL", "PUBLIC_HARNESS_SENTINEL")
            if marker in review_diff
        ]
        if leaked:
            raise AssertionError(f"tracked 私密/内部内容泄露给 reviewer: {leaked}")
        if "# new" not in review_diff:
            raise AssertionError("安全的 tracked README 改动被错误过滤")
    finally:
        shutil.rmtree(root)


def test_review_diff_rejects_untracked_symlink() -> None:
    root = _git_root("loopharness_public_review_symlink_")
    outside_dir = Path(tempfile.mkdtemp(prefix="loopharness_public_outside_"))
    try:
        outside = outside_dir / "outside.md"
        outside.write_text("PUBLIC_OUTSIDE_SENTINEL\n", encoding="utf-8")
        os.symlink(outside, root / "linked-notes.md")
        review_diff = _impl_period_diff(root)
        if "PUBLIC_OUTSIDE_SENTINEL" in review_diff:
            raise AssertionError("untracked symlink 泄露了仓库外内容")
    finally:
        shutil.rmtree(root)
        shutil.rmtree(outside_dir)


def test_oversized_review_fails_closed_before_external_calls() -> None:
    root = Path(tempfile.mkdtemp(prefix="loopharness_public_review_limit_"))
    oversized = "x" * 80_001
    try:
        with patch.object(pipeline, "_impl_period_diff", return_value=oversized):
            with patch.object(pipeline.subprocess, "run", side_effect=AssertionError("不应调用 Claude")):
                fresh_ok, fresh_reason = pipeline._fresh_context_review(root)
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "dummy"}, clear=False):
            with patch.object(pipeline, "_impl_period_diff", return_value=oversized):
                with patch("urllib.request.urlopen", side_effect=AssertionError("不应调用 API")):
                    cross_ok, cross_reason = pipeline._cross_family_review(root)
        if fresh_ok or "80,000" not in fresh_reason:
            raise AssertionError(f"Claude 超限审查未 fail-closed: {fresh_ok}, {fresh_reason}")
        if cross_ok or "80,000" not in cross_reason:
            raise AssertionError(f"跨家族超限审查未 fail-closed: {cross_ok}, {cross_reason}")
    finally:
        shutil.rmtree(root)


def test_review_diff_combines_stage_commits_and_worktree_changes() -> None:
    root = _git_root("loopharness_mixed_stage_review_")
    try:
        (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        _commit_all(root)
        entered = datetime.now(timezone.utc) - timedelta(seconds=2)
        _write_pipeline_state(root, entered)

        (root / "README.md").write_text("COMMITTED_SAFE_SENTINEL\n", encoding="utf-8")
        _commit_all(root)
        (root / "CHANGELOG.md").write_text("WORKTREE_SAFE_SENTINEL\n", encoding="utf-8")

        review_diff = _impl_period_diff(root)
        missing = [
            marker
            for marker in ("COMMITTED_SAFE_SENTINEL", "WORKTREE_SAFE_SENTINEL")
            if marker not in review_diff
        ]
        if missing:
            raise AssertionError(f"stage commit 与 worktree 未完整合并送审: {missing}")
    finally:
        shutil.rmtree(root)


def test_sensitive_rename_is_filtered_in_worktree_and_commits() -> None:
    for committed in (False, True):
        root = _git_root(f"loopharness_sensitive_rename_{committed}_")
        try:
            (root / ".env").write_text("RENAMED_ENV_SECRET_SENTINEL=abcd\n", encoding="utf-8")
            _commit_all(root)
            entered = datetime.now(timezone.utc) - timedelta(seconds=2)
            _write_pipeline_state(root, entered)
            _git(root, "mv", ".env", "README.md")
            if committed:
                _commit_all(root)

            review_diff = _impl_period_diff(root)
            if "RENAMED_ENV_SECRET_SENTINEL" in review_diff:
                mode = "commit" if committed else "worktree"
                raise AssertionError(f"敏感 rename 在 {mode} 路径泄露给 reviewer")
        finally:
            shutil.rmtree(root)
