# mypy: ignore-errors
# flake8: noqa
"""LoopHarness v1.4 跨模型交付层与公开发布门禁。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).absolute().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_cli(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "claude_hh.pipeline", "--project", str(project), *args],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _delivery() -> Any:
    from claude_hh import delivery

    return delivery


def test_cli_exposes_cross_agent_delivery_commands() -> None:
    """AC1/9：旧 pipeline 不丢，新交付命令和四个 agent 可见。"""
    result = subprocess.run(
        [sys.executable, "-m", "claude_hh.pipeline", "-h"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(f"harness -h 失败: {result.stderr}")
    output = result.stdout.lower()
    for command in (
        "init",
        "start",
        "advance",
        "status",
        "memory-init",
        "contract",
        "context",
        "evidence",
        "readiness",
        "learn",
    ):
        if command not in output:
            raise AssertionError(f"CLI 缺少命令 {command}: {result.stdout}")
    pipeline_text = (ROOT / "claude_hh" / "pipeline.py").read_text(encoding="utf-8").lower()
    for agent in ("claude", "codex", "kimi", "glm"):
        if agent not in pipeline_text:
            raise AssertionError(f"CLI 未声明 agent={agent}")


def test_contract_and_context_are_explicitly_scoped() -> None:
    """AC2：只读取合同授权的项目内非敏感资料。"""
    delivery = _delivery()
    temp_dir = tempfile.mkdtemp(prefix="test_loopharness_context_")
    try:
        project = Path(temp_dir) / "project"
        project.mkdir()
        docs = project / "docs"
        docs.mkdir()
        allowed = docs / "context.md"
        allowed.write_text("PUBLIC-CONTEXT", encoding="utf-8")
        secret = project / ".env"
        secret.write_text("PRIVATE-MARKER", encoding="utf-8")
        outside = Path(temp_dir) / "outside.md"
        outside.write_text("OUTSIDE-MARKER", encoding="utf-8")

        blocked = False
        try:
            delivery.create_contract(
                project,
                "可靠交付",
                ["输出有证据"],
                allowed_context=[allowed, secret],
            )
        except ValueError:
            blocked = True
        if not blocked:
            raise AssertionError("Delivery Contract 必须拒绝 .env 授权")

        delivery.create_contract(
            project,
            "可靠交付",
            ["输出有证据"],
            allowed_context=[allowed],
        )
        for agent in ("claude", "codex", "kimi", "glm"):
            result = delivery.compile_context(
                project,
                "生成最小上下文",
                agent,
                context_paths=[allowed, secret, outside],
            )
            if result.get("included_paths") != ["docs/context.md"]:
                raise AssertionError(f"{agent} 授权资料错误: {result}")
            content = str(result.get("content") or "")
            if "PUBLIC-CONTEXT" not in content:
                raise AssertionError(f"{agent} 缺少授权内容")
            for forbidden in ("PRIVATE-MARKER", "OUTSIDE-MARKER"):
                if forbidden in content:
                    raise AssertionError(f"{agent} 泄露未授权内容 {forbidden}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_evidence_readiness_rechecks_current_artifact_and_latest_result() -> None:
    """AC3：文件变化或最新失败 receipt 不能继续虚报就绪。"""
    delivery = _delivery()
    temp_dir = tempfile.mkdtemp(prefix="test_loopharness_evidence_")
    try:
        project = Path(temp_dir)
        delivery.create_contract(project, "发布", ["测试通过"])
        artifact = project / "functional.txt"
        artifact.write_text("passed-v1", encoding="utf-8")
        receipt = delivery.add_evidence(project, "functional", artifact, "passed")
        expected_hash = hashlib.sha256(b"passed-v1").hexdigest()
        if receipt.get("sha256") != expected_hash:
            raise AssertionError(f"receipt hash 错误: {receipt}")

        artifact.write_text("changed-after-receipt", encoding="utf-8")
        readiness = delivery.evaluate_readiness(project)
        if "functional" in readiness.get("verified_evidence", []):
            raise AssertionError(f"artifact 被修改后仍被当作有效证据: {readiness}")

        artifact.write_text("passed-v2", encoding="utf-8")
        delivery.add_evidence(project, "functional", artifact, "passed")
        delivery.add_evidence(project, "functional", artifact, "failed")
        readiness = delivery.evaluate_readiness(project)
        if "functional" in readiness.get("verified_evidence", []):
            raise AssertionError(f"同类最新结果失败时仍被当作通过: {readiness}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_learning_cannot_self_promote_without_user_or_evidence() -> None:
    """AC4：模型反思不得自行进入 adopt。"""
    delivery = _delivery()
    temp_dir = tempfile.mkdtemp(prefix="test_loopharness_learning_")
    try:
        project = Path(temp_dir)
        delivery.init_memory(project)
        downgraded = delivery.record_learning(
            project,
            "模型觉得以后都该这样",
            requested_basket="adopt",
            source_type="model_reflection",
        )
        if downgraded.get("basket") != "confirm":
            raise AssertionError(f"无证据模型反思必须降为 confirm: {downgraded}")
        adopted = delivery.record_learning(
            project,
            "用户明确要求先写测试",
            requested_basket="adopt",
            source_type="user_explicit",
        )
        if adopted.get("basket") != "adopt":
            raise AssertionError(f"用户明确规则应可 adopt: {adopted}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_installer_is_idempotent_and_creates_portable_executable() -> None:
    """AC5：全新 HOME 可重复安装，并脱离源码运行。"""
    temp_dir = tempfile.mkdtemp(prefix="test_loopharness_install_")
    try:
        home = Path(temp_dir) / "home"
        home.mkdir()
        (home / ".zshrc").write_text("# existing\n", encoding="utf-8")
        install_dir = home / ".loopharness"
        bin_dir = home / ".local" / "bin"
        env = {
            **os.environ,
            "HOME": str(home),
            "CLAUDE_HH_DIR": str(install_dir),
            "HARNESS_BIN_DIR": str(bin_dir),
        }
        for _iteration in range(2):
            completed = subprocess.run(
                ["/bin/bash", str(ROOT / "install.sh")],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if completed.returncode != 0:
                raise AssertionError(f"install.sh 失败: {completed.stdout}\n{completed.stderr}")
        executable = bin_dir / "harness"
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise AssertionError("安装后缺少可执行 ~/.local/bin/harness")
        mode = stat.S_IMODE(executable.stat().st_mode)
        if mode & 0o111 == 0:
            raise AssertionError(f"harness 不可执行: mode={oct(mode)}")
        help_result = subprocess.run(
            [str(executable), "-h"],
            cwd=home,
            env={**env, "PYTHONPATH": ""},
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if help_result.returncode != 0 or "contract" not in help_result.stdout:
            raise AssertionError(f"脱离源码运行失败: {help_result.stdout}\n{help_result.stderr}")
        rc_text = (home / ".zshrc").read_text(encoding="utf-8")
        if rc_text.count(str(bin_dir)) > 1:
            raise AssertionError(f"重复安装污染 shell 配置: {rc_text}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_public_candidate_has_no_local_or_secret_artifacts() -> None:
    """AC6：公开候选无本机路径、高熵密钥、备份、日志或缓存。"""
    forbidden_files: list[str] = []
    leaked_text: list[str] = []
    excluded_dirs = {".git", "__pycache__"}
    excluded_names = {"task_plan.md", "progress.md", "findings.md"}
    secret_patterns = (
        re.compile(r"/Users/[A-Za-z0-9._-]+(?:/|\\b)"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    )
    candidate = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    candidate_paths = [item for item in candidate.stdout.split(b"\0") if item]
    forbidden_runtime_names = {
        ".harness/pipeline.json",
        ".harness/retreat_log.md",
        ".harness/review_report.md",
        ".harness/change_request.md",
        ".harness/proposed_auto.md",
        ".harness/stuck_notice.md",
    }
    for encoded_path in candidate_paths:
        relative = Path(os.fsdecode(encoded_path))
        if any(part in excluded_dirs for part in relative.parts):
            continue
        if relative.name in excluded_names:
            continue
        if relative.as_posix() in forbidden_runtime_names:
            forbidden_files.append(relative.as_posix())
            continue
        path = ROOT / relative
        if path.is_dir():
            continue
        if ".bak-" in path.name or path.suffix == ".log" or path.suffix == ".pyc":
            forbidden_files.append(relative.as_posix())
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if any(pattern.search(content) for pattern in secret_patterns):
            leaked_text.append(relative.as_posix())
    if forbidden_files:
        raise AssertionError(f"公开候选包含运行/备份文件: {forbidden_files}")
    if leaked_text:
        raise AssertionError(f"公开候选包含本机路径或疑似密钥: {leaked_text}")


def test_readme_and_versions_match_public_positioning() -> None:
    """AC7/8：首屏定位、3 分钟 Demo、证据和 1.4.0 版本一致。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "LoopHarness",
        "非技术",
        "超级个体",
        "Codex",
        "Claude",
        "Kimi",
        "GLM",
        "3 分钟",
        "Delivery Contract",
        "readiness",
    ):
        if required not in readme:
            raise AssertionError(f"README 缺少核心定位/旅程：{required}")
    for obsolete in ("仅支持 Claude Code", "Claude Code-required"):
        if obsolete in readme:
            raise AssertionError(f"README 保留过时单模型承诺：{obsolete}")

    init_text = (ROOT / "claude_hh" / "__init__.py").read_text(encoding="utf-8")
    project_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if '__version__ = "1.4.0"' not in init_text:
        raise AssertionError("claude_hh.__version__ 未更新到 1.4.0")
    if 'version = "1.4.0"' not in project_text:
        raise AssertionError("pyproject version 未更新到 1.4.0")
