"""LoopHarness 交付层正式回归测试。"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from claude_hh import delivery


def test_memory_initialization_is_idempotent() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_memory_") as temp_dir:
        root = Path(temp_dir)
        first = delivery.init_memory(root)
        profile = root / ".agent-memory" / "profile.md"
        profile.write_text("用户明确偏好", encoding="utf-8")
        second = delivery.init_memory(root)
        if not first["created"]:
            raise AssertionError("首次初始化必须创建记忆文件")
        if second["created"]:
            raise AssertionError(f"重复初始化不应覆盖或重建文件: {second}")
        if profile.read_text(encoding="utf-8") != "用户明确偏好":
            raise AssertionError("重复初始化覆盖了已有记忆")


def test_context_reads_only_contract_grants() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_context_") as temp_dir:
        root = Path(temp_dir) / "project"
        root.mkdir()
        allowed = root / "brief.md"
        allowed.write_text("公开需求", encoding="utf-8")
        secret = root / ".env"
        secret.write_text("不应出现", encoding="utf-8")
        outside = root.parent / "outside.md"
        outside.write_text("项目外资料", encoding="utf-8")
        delivery.create_contract(root, "可靠交付", ["有真实证据"], allowed_context=[allowed])

        result = delivery.compile_context(
            root,
            "实现功能",
            "codex",
            context_paths=[allowed, secret, outside],
        )
        if result["included_paths"] != ["brief.md"]:
            raise AssertionError(f"授权范围不正确: {result}")
        if "公开需求" not in result["content"]:
            raise AssertionError("缺少已授权内容")
        if "不应出现" in result["content"] or "项目外资料" in result["content"]:
            raise AssertionError("上下文包含未授权内容")


def test_contract_rejects_common_private_key_names() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_private_key_") as temp_dir:
        root = Path(temp_dir)
        private_key = root / "id_rsa"
        private_key.write_text("private material", encoding="utf-8")
        rejected = False
        try:
            delivery.create_contract(root, "安全交付", ["不读私钥"], allowed_context=[private_key])
        except ValueError:
            rejected = True
        if not rejected:
            raise AssertionError("常见私钥文件名 id_rsa 不得进入合同授权")


def test_evidence_receipt_contains_current_artifact_identity() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_receipt_") as temp_dir:
        root = Path(temp_dir)
        delivery.create_contract(root, "发布", ["功能通过"])
        artifact = root / "functional.txt"
        artifact.write_bytes(b"verified")
        receipt = delivery.add_evidence(root, "functional", artifact)
        if receipt["artifact"] != "functional.txt":
            raise AssertionError(f"receipt 未保存相对路径: {receipt}")
        if receipt["size"] != len(b"verified"):
            raise AssertionError(f"receipt 大小错误: {receipt}")
        if receipt["sha256"] != hashlib.sha256(b"verified").hexdigest():
            raise AssertionError(f"receipt SHA-256 错误: {receipt}")


def test_readiness_uses_latest_receipt_and_rechecks_hash() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_readiness_") as temp_dir:
        root = Path(temp_dir)
        delivery.create_contract(root, "发布", ["功能通过"])
        artifact = root / "functional.txt"
        artifact.write_text("v1", encoding="utf-8")
        delivery.add_evidence(root, "functional", artifact, "passed")
        artifact.write_text("changed", encoding="utf-8")
        changed = delivery.evaluate_readiness(root)
        if "functional" in changed["verified_evidence"]:
            raise AssertionError(f"artifact 变化后仍被验证: {changed}")

        delivery.add_evidence(root, "functional", artifact, "passed")
        delivery.add_evidence(root, "functional", artifact, "failed")
        latest_failed = delivery.evaluate_readiness(root)
        if "functional" in latest_failed["verified_evidence"]:
            raise AssertionError(f"同类最新失败 receipt 被旧成功覆盖: {latest_failed}")


def test_learning_adoption_requires_user_or_current_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_learning_") as temp_dir:
        root = Path(temp_dir)
        model_item = delivery.record_learning(root, "模型反思", "adopt", "model_reflection")
        if model_item["basket"] != "confirm":
            raise AssertionError(f"模型反思自行 adopt: {model_item}")
        user_item = delivery.record_learning(root, "用户明确要求", "adopt", "user_explicit")
        if user_item["basket"] != "adopt":
            raise AssertionError(f"用户明确指令未 adopt: {user_item}")

        delivery.create_contract(root, "学习", ["证据有效"])
        artifact = root / "evidence.txt"
        artifact.write_text("pass", encoding="utf-8")
        receipt = delivery.add_evidence(root, "functional", artifact, "passed")
        artifact.write_text("stale", encoding="utf-8")
        stale_item = delivery.record_learning(
            root,
            "旧证据经验",
            "adopt",
            "evidence_receipt",
            receipt["id"],
        )
        if stale_item["basket"] != "confirm":
            raise AssertionError(f"失效 evidence receipt 仍可 adopt: {stale_item}")


def test_installer_retires_legacy_harness_alias_without_touching_other_aliases() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    installer = repo_root / "install.sh"
    with tempfile.TemporaryDirectory(prefix="loopharness_upgrade_") as temp_dir:
        home = Path(temp_dir) / "home"
        install_dir = home / ".loopharness"
        bin_dir = home / ".local" / "bin"
        home.mkdir()
        zshrc = home / ".zshrc"
        zshrc.write_text(
            "alias harness=\"PYTHONPATH=$HOME/.claude-hh python3 -m claude_hh.pipeline\"\n"
            "alias ll='ls -la'\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "CLAUDE_HH_DIR": str(install_dir),
                "HARNESS_BIN_DIR": str(bin_dir),
            }
        )

        for _ in range(2):
            subprocess.run(
                ["bash", str(installer)],
                cwd=repo_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        rc_content = zshrc.read_text(encoding="utf-8")
        if "claude_hh.pipeline" in rc_content or "alias harness=" in rc_content:
            raise AssertionError(f"旧 harness alias 仍会遮蔽新版命令: {rc_content}")
        if "alias ll='ls -la'" not in rc_content:
            raise AssertionError("安装器误删了无关 alias")
        if rc_content.count("# LoopHarness PATH") != 1:
            raise AssertionError(f"重复安装写入了多份 PATH 配置: {rc_content}")
        completed = subprocess.run(
            [str(bin_dir / "harness"), "-h"],
            cwd=home,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        if "1.4.0" not in completed.stdout:
            raise AssertionError(f"新版命令未生效: {completed.stdout}")
