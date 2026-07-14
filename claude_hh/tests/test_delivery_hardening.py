"""LoopHarness v1.4 独立审查发现项的回归门禁。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from claude_hh import delivery


ROOT = Path(__file__).resolve().parents[2]


def test_declared_receipts_do_not_self_certify_production_readiness() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_declared_") as temp_dir:
        root = Path(temp_dir)
        delivery.create_contract(root, "发布", ["不得假绿"])
        artifact = root / "claim.txt"
        artifact.write_text("I merely claim success", encoding="utf-8")
        for kind in delivery.EVIDENCE_KINDS:
            delivery.add_evidence(root, kind, artifact, "passed")

        readiness = delivery.evaluate_readiness(root)
        if readiness["level"] != "Contract-only":
            raise AssertionError(f"声明型文件自行获得生产就绪等级: {readiness}")
        if readiness["verified_evidence"]:
            raise AssertionError(f"声明型文件被标成已验证证据: {readiness}")
        if sorted(readiness.get("declared_evidence", [])) != sorted(delivery.EVIDENCE_KINDS):
            raise AssertionError(f"readiness 没有诚实展示已收集声明证据: {readiness}")

        declared_receipt = delivery.add_evidence(root, "functional", artifact, "passed")
        learning = delivery.record_learning(
            root,
            "模型根据自报文件生成的规则",
            "adopt",
            "evidence_receipt",
            declared_receipt["id"],
        )
        if learning["basket"] != "confirm":
            raise AssertionError(f"declared receipt 仍可让模型自行 adopt: {learning}")


def test_agent_cli_cannot_claim_user_explicit_source() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_cli_identity_") as temp_dir:
        root = Path(temp_dir)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "claude_hh.pipeline",
                "learn",
                "模型伪装用户规则",
                "--basket",
                "adopt",
                "--source-type",
                "user_explicit",
            ],
            cwd=root,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            raise AssertionError("Agent CLI 可以把自身输入冒充 user_explicit")
        learned = root / ".agent-memory" / "decisions" / "learned.md"
        if learned.exists():
            raise AssertionError("被拒绝的伪装用户规则仍写入 adopt")


def test_internal_storage_symlinks_are_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_symlink_") as temp_dir:
        base = Path(temp_dir)
        for internal_name in (".delivery", ".agent-memory"):
            project = base / internal_name.removeprefix(".")
            outside = base / f"outside-{internal_name.removeprefix('.')}"
            project.mkdir()
            outside.mkdir()
            (project / internal_name).symlink_to(outside, target_is_directory=True)
            rejected = False
            try:
                delivery.create_contract(project, "安全边界", ["只写项目内"])
            except ValueError:
                rejected = True
            if not rejected:
                raise AssertionError(f"内部目录 symlink 未被拒绝: {internal_name}")
            if any(outside.iterdir()):
                raise AssertionError(f"内部目录 symlink 向项目外写入: {internal_name}")


def test_nested_internal_symlinks_cannot_read_or_write_outside() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_nested_symlink_") as temp_dir:
        base = Path(temp_dir)

        receipt_project = base / "receipt-project"
        receipt_project.mkdir()
        delivery.create_contract(receipt_project, "安全边界", ["只写项目内"])
        outside_receipts = base / "outside-receipts"
        outside_receipts.mkdir()
        receipts_dir = receipt_project / ".agent-memory" / "receipts"
        receipts_dir.rmdir()
        receipts_dir.symlink_to(outside_receipts, target_is_directory=True)
        artifact = receipt_project / "artifact.txt"
        artifact.write_text("pass", encoding="utf-8")
        rejected = False
        try:
            delivery.add_evidence(receipt_project, "functional", artifact)
        except ValueError:
            rejected = True
        if not rejected or any(outside_receipts.iterdir()):
            raise AssertionError("嵌套 receipts symlink 可向项目外写入")
        if not receipts_dir.is_symlink():
            raise AssertionError("拒绝内部 symlink 时擅自删除了用户文件")

        ledger_project = base / "ledger-project"
        ledger_project.mkdir()
        delivery.create_contract(ledger_project, "安全边界", ["不读项目外"])
        outside_ledger = base / "outside-ledger.jsonl"
        outside_ledger.write_text("OUTSIDE-PRIVATE-MARKER\n", encoding="utf-8")
        ledger = ledger_project / ".delivery" / "evidence.jsonl"
        ledger.symlink_to(outside_ledger)
        artifact = ledger_project / "artifact.txt"
        artifact.write_text("pass", encoding="utf-8")
        rejected = False
        try:
            delivery.add_evidence(ledger_project, "functional", artifact)
        except ValueError:
            rejected = True
        if not rejected:
            raise AssertionError("evidence ledger symlink 可读取项目外内容")
        if not ledger.is_symlink():
            raise AssertionError("拒绝 evidence ledger symlink 时擅自删除了用户文件")
        if outside_ledger.read_text(encoding="utf-8") != "OUTSIDE-PRIVATE-MARKER\n":
            raise AssertionError("拒绝后项目外 ledger 内容发生变化")


def test_init_replaces_legacy_v1_hooks_instead_of_duplicating() -> None:
    with tempfile.TemporaryDirectory(prefix="loopharness_hooks_") as temp_dir:
        project = Path(temp_dir)
        settings_dir = project / ".claude"
        settings_dir.mkdir()
        settings = settings_dir / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Edit|Write|MultiEdit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 /tmp/home/.claude-hh/hooks/pre_edit.py",
                                    }
                                ],
                            },
                            {
                                "matcher": "Edit|Write|MultiEdit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 hooks/pre_edit.py",
                                    }
                                ],
                            },
                        ],
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 /tmp/home/.claude-hh/hooks/stop_check.py",
                                    }
                                ]
                            },
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 hooks/stop_check.py",
                                    }
                                ]
                            },
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [sys.executable, "-m", "claude_hh.pipeline", "init"],
            cwd=project,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(f"harness init 失败: {completed.stdout}\n{completed.stderr}")
        config = json.loads(settings.read_text(encoding="utf-8"))
        commands = [
            hook.get("command", "")
            for entries in config["hooks"].values()
            for entry in entries
            for hook in entry.get("hooks", [])
        ]
        if any(".claude-hh/hooks/" in command for command in commands):
            raise AssertionError(f"升级后仍保留 legacy v1 hook: {commands}")
        if sum("hooks/pre_edit.py" in command for command in commands) != 1:
            raise AssertionError(f"pre_edit hook 数量不是 1: {commands}")
        if sum("hooks/stop_check.py" in command for command in commands) != 1:
            raise AssertionError(f"stop_check hook 数量不是 1: {commands}")


def test_public_candidate_excludes_stale_private_runtime_notes() -> None:
    forbidden = (
        ROOT / ".harness" / "change_request.md",
        ROOT / ".harness" / "proposed_auto.md",
        ROOT / ".harness" / "archive_loop_eng2" / "test_ac_zhuolong_loop.py",
    )
    leaked = sorted(path.relative_to(ROOT).as_posix() for path in forbidden if path.exists())
    if leaked:
        raise AssertionError(f"公开候选仍跟踪旧运行/内部记录: {leaked}")
