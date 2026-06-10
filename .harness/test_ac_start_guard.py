# mypy: ignore-errors
# flake8: noqa
"""AC6 + AC7: start 时独立审查未启用提醒 + 清掉上个任务残留的错题本/交付报告."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).absolute().parent.parent


def _run_start(root: Path, with_key: bool) -> str:
    env = dict(os.environ)
    env.pop("DEEPSEEK_API_KEY", None)
    if with_key:
        env["DEEPSEEK_API_KEY"] = "sk-test-dummy"
    env["PYTHONPATH"] = str(REPO)
    # 密闭性：load_env 还会读全局 ~/.harness/.env，把 HOME 指到空临时目录隔离掉
    fake_home = tempfile.mkdtemp(prefix="test_startguard_home_")
    env["HOME"] = fake_home
    r = subprocess.run(
        [sys.executable, "-m", "claude_hh.pipeline", "--project", str(root), "start", "新任务"],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(root),
    )
    if r.returncode != 0:
        raise AssertionError(f"harness start 退出码非 0：{r.returncode}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def test_ac6_start_warns_when_no_deepseek_key() -> None:
    """AC6: 未配置 DEEPSEEK_API_KEY 时 start 打印'独立审查未启用'类提醒."""
    root = Path(tempfile.mkdtemp(prefix="test_startguard_"))
    try:
        out = _run_start(root, with_key=False)
        if "独立审查" not in out:
            raise AssertionError(f"未配置 key 时 start 应提醒独立审查未启用，实际输出：\n{out}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac6_start_silent_when_key_present() -> None:
    """AC6 反向: 配置了 key 就不打印未启用提醒."""
    root = Path(tempfile.mkdtemp(prefix="test_startguard_"))
    try:
        out = _run_start(root, with_key=True)
        if "未启用" in out:
            raise AssertionError(f"已配置 key 仍提示未启用：\n{out}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ac7_start_clears_previous_task_residue() -> None:
    """AC7: 新任务 start 时清掉上个任务的 retreat_log.md 和 delivery_report.md."""
    root = Path(tempfile.mkdtemp(prefix="test_startguard_"))
    try:
        h = root / ".harness"
        h.mkdir()
        (h / "pipeline.json").write_text(json.dumps({"current_stage": "done", "description": "旧任务"}))
        (h / "retreat_log.md").write_text("# 旧任务的错题本\n- 旧原因\n")
        (h / "delivery_report.md").write_text("# 旧任务的交付报告\n遗留问题：xxx\n")
        _run_start(root, with_key=True)
        if (h / "retreat_log.md").exists():
            raise AssertionError("新任务开始后上个任务的 retreat_log.md 仍残留（会污染新任务）")
        if (h / "delivery_report.md").exists():
            raise AssertionError("新任务开始后上个任务的 delivery_report.md 仍残留")
    finally:
        shutil.rmtree(root, ignore_errors=True)
