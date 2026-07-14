"""LoopHarness 的跨模型可靠交付层。

持久事实保存在项目内的合同、证据回执和可审计记忆中；模型只读取合同
明确授权的最小 Markdown 上下文。模块只依赖 Python 标准库。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Union


PathLike = Union[str, os.PathLike[str]]
AGENTS = {"claude", "codex", "kimi", "glm"}
RISKS = {"low", "medium", "high"}
LEARNING_BASKETS = {"adopt", "confirm", "receipt_only"}
EVIDENCE_VERIFICATIONS = {"declared", "verified"}
EVIDENCE_KINDS = {
    "functional",
    "preview",
    "security",
    "rollback",
    "deployment",
    "production_health",
}
PASSING_OUTCOMES = {"passed", "pass", "ok", "verified"}
MAX_TEXT_CHARS = 20_000
MAX_CONTEXT_FILE_BYTES = 256_000
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024

_SENSITIVE_PARTS = {
    ".aws",
    ".git",
    ".gnupg",
    ".ssh",
    "secrets",
    "secret",
    "credentials",
    "credential",
    "production-data",
    "production_data",
    "prod-data",
    "prod_data",
    "real-user-data",
    "real_user_data",
}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
_SENSITIVE_NAMES = {"id_dsa", "id_ecdsa", "id_ed25519", "id_rsa"}
_SENSITIVE_NAME_FRAGMENTS = (
    "password",
    "passwd",
    "api_key",
    "apikey",
    "secret",
    "token",
    "credential",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root(root: PathLike) -> Path:
    value = Path(root).expanduser().resolve()
    if not value.exists() or not value.is_dir():
        raise ValueError("项目目录不存在或不是目录")
    return value


def _memory_dir(root: Path) -> Path:
    return root / ".agent-memory"


def _delivery_dir(root: Path) -> Path:
    return root / ".delivery"


def _assert_internal_storage_safe(root: Path) -> None:
    """拒绝内部存储树中的任意 symlink，避免读写被重定向。"""

    def reject_symlink(_path: Path, relative: str) -> None:
        """只拒绝不修改：symlink 可能是用户文件，检查器无权删除。"""
        raise ValueError(f"内部存储不能包含 symlink: {relative}")

    for name in (".delivery", ".agent-memory"):
        path = root / name
        if path.is_symlink():
            reject_symlink(path, name)
        if not path.exists():
            continue
        try:
            pending = [path]
            while pending:
                directory = pending.pop()
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_symlink():
                            relative = Path(entry.path).relative_to(root).as_posix()
                            reject_symlink(Path(entry.path), relative)
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(f"内部存储目录无法安全检查: {name}") from exc


def _clean_text(value: str, label: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > max_chars:
        raise ValueError(f"{label}超过长度上限")
    return text


def _relative_path(root: Path, value: PathLike) -> tuple[Path, str]:
    raw = Path(value).expanduser()
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        relative = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("路径必须位于项目目录内") from exc
    return candidate, relative


def _is_sensitive(relative: str) -> bool:
    path = Path(relative)
    lowered_parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _SENSITIVE_NAMES:
        return True
    if path.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    if any(part in _SENSITIVE_PARTS for part in lowered_parts):
        return True
    return any(fragment in name for fragment in _SENSITIVE_NAME_FRAGMENTS)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    _atomic_write_text(path, existing + line)


def _audit(root: Path, event: str, metadata: Optional[dict[str, Any]] = None) -> None:
    _append_jsonl(
        _memory_dir(root) / "audit.jsonl",
        {
            "id": uuid.uuid4().hex,
            "at": _now(),
            "event": event,
            "metadata": dict(metadata or {}),
        },
    )


def init_memory(root: PathLike) -> dict[str, Any]:
    """幂等创建 Claude/Codex/Kimi/GLM 共用的项目内记忆目录。"""
    project = _project_root(root)
    _assert_internal_storage_safe(project)
    memory = _memory_dir(project)
    for directory in (memory, memory / "projects", memory / "decisions", memory / "receipts"):
        directory.mkdir(parents=True, exist_ok=True)
    defaults = {
        memory / "profile.md": "# 开发者画像\n\n在这里记录用户明确表达的沟通、风险和工作偏好。\n",
        memory / "inbox.md": "# 待确认的学习候选\n",
        memory / "audit.jsonl": "",
    }
    created: list[str] = []
    for path, content in defaults.items():
        if not path.exists():
            _atomic_write_text(path, content)
            created.append(path.relative_to(project).as_posix())
    _delivery_dir(project).mkdir(parents=True, exist_ok=True)
    _audit(project, "memory_initialized", {"created": created})
    return {"root": str(memory.resolve()), "created": created}


def create_contract(
    root: PathLike,
    goal: str,
    acceptance_criteria: Iterable[str],
    risk: str = "medium",
    allowed_context: Optional[Iterable[PathLike]] = None,
) -> dict[str, Any]:
    """保存只授权项目内非敏感路径的 Delivery Contract。"""
    project = _project_root(root)
    init_memory(project)
    clean_goal = _clean_text(goal, "目标", 4_000)
    criteria = [_clean_text(item, "验收标准", 2_000) for item in acceptance_criteria]
    if not criteria:
        raise ValueError("至少需要一条验收标准")
    if len(criteria) > 100:
        raise ValueError("验收标准数量超过上限")
    clean_risk = str(risk or "").strip().lower()
    if clean_risk not in RISKS:
        raise ValueError("风险等级只能是 low、medium 或 high")

    grants: list[str] = []
    for value in allowed_context or []:
        _path, relative = _relative_path(project, value)
        if _is_sensitive(relative):
            raise ValueError(f"敏感路径不能进入合同授权: {relative}")
        if relative not in grants:
            grants.append(relative)
    contract = {
        "schema_version": 1,
        "id": uuid.uuid4().hex,
        "created_at": _now(),
        "goal": clean_goal,
        "acceptance_criteria": criteria,
        "risk": clean_risk,
        "allowed_context": grants,
    }
    _atomic_write_json(_delivery_dir(project) / "contract.json", contract)
    _audit(
        project,
        "contract_created",
        {"contract_id": contract["id"], "risk": clean_risk, "grants": grants},
    )
    return contract


def _load_contract(root: Path) -> dict[str, Any]:
    path = _delivery_dir(root) / "contract.json"
    if not path.exists():
        raise ValueError("还没有 Delivery Contract")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Delivery Contract 无法读取") from exc
    if not isinstance(value, dict):
        raise ValueError("Delivery Contract 格式无效")
    return value


def _contract_markdown(contract: dict[str, Any]) -> str:
    criteria = "\n".join(f"- {item}" for item in contract.get("acceptance_criteria", []))
    return (
        "## Delivery Contract\n\n"
        f"目标：{contract.get('goal', '')}\n\n"
        f"风险：{contract.get('risk', '')}\n\n"
        "验收标准：\n"
        f"{criteria}\n"
    )


def compile_context(
    root: PathLike,
    task: str,
    agent: str,
    context_paths: Optional[Iterable[PathLike]] = None,
) -> dict[str, Any]:
    """只从合同明确授权的文件生成最小上下文。"""
    project = _project_root(root)
    init_memory(project)
    clean_task = _clean_text(task, "任务", 4_000)
    clean_agent = str(agent or "").strip().lower()
    if clean_agent not in AGENTS:
        raise ValueError("agent 只能是 claude、codex、kimi 或 glm")
    contract = _load_contract(project)
    allowed = {str(item) for item in contract.get("allowed_context", [])}
    included: list[str] = []
    denied: list[str] = []
    sections: list[str] = []

    for value in context_paths or []:
        try:
            path, relative = _relative_path(project, value)
        except ValueError:
            denied.append("项目外路径")
            continue
        if _is_sensitive(relative) or relative not in allowed:
            denied.append(relative)
            continue
        try:
            if not path.is_file() or path.stat().st_size > MAX_CONTEXT_FILE_BYTES:
                denied.append(relative)
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            denied.append(relative)
            continue
        included.append(relative)
        sections.append(f"## Context: {relative}\n\n{content.rstrip()}\n")

    body = "\n".join(
        [
            f"Agent adapter: {clean_agent}",
            "# Task-scoped Context Bundle",
            f"## 当前任务\n\n{clean_task}\n",
            _contract_markdown(contract),
            *sections,
        ]
    ).rstrip() + "\n"
    output = _delivery_dir(project) / "context_bundle.md"
    _atomic_write_text(output, body)
    _audit(
        project,
        "context_compiled",
        {"agent": clean_agent, "included_paths": included, "denied_paths": denied},
    )
    return {
        "agent": clean_agent,
        "content": body,
        "path": str(output),
        "included_paths": included,
        "denied_paths": denied,
    }


def _read_evidence(root: Path) -> list[dict[str, Any]]:
    path = _delivery_dir(root) / "evidence.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def add_evidence(
    root: PathLike,
    kind: str,
    artifact: PathLike,
    outcome: str = "passed",
    verification: str = "declared",
) -> dict[str, Any]:
    """记录 artifact 身份。

    默认 ``declared`` 只证明登记时的路径、大小和 hash；只有受信宿主完成独立
    验证后，才应通过 library API 显式传入 ``verification="verified"``。
    """
    project = _project_root(root)
    init_memory(project)
    clean_kind = str(kind or "").strip().lower()
    if clean_kind not in EVIDENCE_KINDS:
        raise ValueError("不支持的 evidence 类型")
    path, relative = _relative_path(project, artifact)
    if _is_sensitive(relative):
        raise ValueError(f"敏感文件不能登记为 evidence: {relative}")
    try:
        if not path.is_file():
            raise ValueError("evidence artifact 不存在或不是文件")
        size = path.stat().st_size
        if size > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence artifact 超过大小上限")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("evidence artifact 无法读取") from exc
    clean_outcome = _clean_text(outcome, "evidence outcome", 100).lower()
    clean_verification = str(verification or "").strip().lower()
    if clean_verification not in EVIDENCE_VERIFICATIONS:
        raise ValueError("evidence verification 只能是 declared 或 verified")
    receipt = {
        "schema_version": 1,
        "id": uuid.uuid4().hex,
        "created_at": _now(),
        "kind": clean_kind,
        "outcome": clean_outcome,
        "verification": clean_verification,
        "artifact": relative,
        "sha256": digest,
        "size": size,
    }
    _append_jsonl(_delivery_dir(project) / "evidence.jsonl", receipt)
    _atomic_write_json(_memory_dir(project) / "receipts" / f"{receipt['id']}.json", receipt)
    _audit(
        project,
        "evidence_added",
        {
            "evidence_id": receipt["id"],
            "kind": clean_kind,
            "outcome": clean_outcome,
            "verification": clean_verification,
            "artifact": relative,
        },
    )
    return receipt


def _latest_receipts(root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for receipt in _read_evidence(root):
        kind = str(receipt.get("kind", ""))
        if kind in EVIDENCE_KINDS:
            latest[kind] = receipt
    return latest


def _receipt_is_current(root: Path, receipt: dict[str, Any]) -> bool:
    """实时核对 receipt 指向的当前 artifact，任何异常都 fail closed。"""
    if str(receipt.get("outcome", "")).lower() not in PASSING_OUTCOMES:
        return False
    relative = str(receipt.get("artifact", ""))
    if not relative or _is_sensitive(relative):
        return False
    try:
        artifact, canonical = _relative_path(root, relative)
        if canonical != relative or not artifact.is_file():
            return False
        content = artifact.read_bytes()
    except (OSError, ValueError):
        return False
    expected_size = receipt.get("size")
    if not isinstance(expected_size, int) or len(content) != expected_size:
        return False
    digest = hashlib.sha256(content).hexdigest()
    return digest == str(receipt.get("sha256", ""))


def evaluate_readiness(root: PathLike) -> dict[str, Any]:
    """分开展示当前声明与受信宿主验证，只用后者计算就绪度。"""
    project = _project_root(root)
    _assert_internal_storage_safe(project)
    _load_contract(project)
    latest = _latest_receipts(project)
    current = {
        kind for kind, receipt in latest.items() if _receipt_is_current(project, receipt)
    }
    declared = {
        kind
        for kind in current
        if str(latest[kind].get("verification", "declared")).lower() == "declared"
    }
    verified = {
        kind
        for kind in current
        if str(latest[kind].get("verification", "declared")).lower() == "verified"
    }
    levels = [
        (
            "Observed-healthy",
            {"functional", "preview", "security", "rollback", "deployment", "production_health"},
        ),
        ("Production-ready", {"functional", "preview", "security", "rollback", "deployment"}),
        ("Pilot-ready", {"functional", "preview", "security"}),
        ("Preview-ready", {"functional", "preview"}),
    ]
    level = "Contract-only"
    for name, required in levels:
        if required.issubset(verified):
            level = name
            break
    all_required = levels[0][1]
    readiness = {
        "schema_version": 1,
        "evaluated_at": _now(),
        "level": level,
        "declared_evidence": sorted(declared),
        "verified_evidence": sorted(verified),
        "missing_for_observed_healthy": sorted(all_required - verified),
    }
    _atomic_write_json(_delivery_dir(project) / "readiness.json", readiness)
    _audit(
        project,
        "readiness_evaluated",
        {
            "level": level,
            "declared_evidence": sorted(declared),
            "verified_evidence": sorted(verified),
        },
    )
    return readiness


def _valid_evidence_id(root: Path, evidence_id: str) -> bool:
    latest = _latest_receipts(root)
    return any(
        str(receipt.get("id")) == evidence_id
        and str(receipt.get("verification", "declared")).lower() == "verified"
        and _receipt_is_current(root, receipt)
        for receipt in latest.values()
    )


def record_learning(
    root: PathLike,
    text: str,
    requested_basket: str,
    source_type: str,
    evidence_id: str = "",
) -> dict[str, Any]:
    """把学习候选放入三篮子，禁止模型反思自行升级为 adopt。

    ``source_type="user_explicit"`` 只供已验证用户身份的受信宿主事件调用；
    agent CLI 不暴露这一来源。
    """
    project = _project_root(root)
    init_memory(project)
    clean_learning = _clean_text(text, "学习内容", 4_000)
    requested = str(requested_basket or "").strip().lower()
    if requested not in LEARNING_BASKETS:
        raise ValueError("学习篮子只能是 adopt、confirm 或 receipt_only")
    source = _clean_text(source_type, "学习来源", 100).lower()
    clean_evidence_id = str(evidence_id or "").strip()
    basket = requested
    if requested == "adopt":
        supported = source == "user_explicit" or (
            source == "evidence_receipt"
            and bool(clean_evidence_id)
            and _valid_evidence_id(project, clean_evidence_id)
        )
        if not supported:
            basket = "confirm"

    item = {
        "schema_version": 1,
        "id": uuid.uuid4().hex,
        "created_at": _now(),
        "text": clean_learning,
        "basket": basket,
        "requested_basket": requested,
        "source_type": source,
        "evidence_id": clean_evidence_id,
    }
    if basket == "confirm":
        inbox = _memory_dir(project) / "inbox.md"
        existing = inbox.read_text(encoding="utf-8") if inbox.exists() else "# 待确认的学习候选\n"
        _atomic_write_text(inbox, existing.rstrip() + f"\n\n- [{item['id']}] {clean_learning}\n")
    elif basket == "adopt":
        learned = _memory_dir(project) / "decisions" / "learned.md"
        existing = learned.read_text(encoding="utf-8") if learned.exists() else "# 已采纳的交付经验\n"
        source_note = f"source={source}"
        if clean_evidence_id:
            source_note += f", evidence={clean_evidence_id}"
        _atomic_write_text(learned, existing.rstrip() + f"\n\n- {clean_learning} ({source_note})\n")
    else:
        _atomic_write_json(_memory_dir(project) / "receipts" / f"learning-{item['id']}.json", item)
    _audit(
        project,
        "learning_recorded",
        {
            "learning_id": item["id"],
            "basket": basket,
            "requested_basket": requested,
            "source_type": source,
        },
    )
    return item
