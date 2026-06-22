"""Claude H-H v1.0 — spec-first pipeline CLI."""
from __future__ import annotations
import argparse, glob, json, os, re, subprocess, sys, textwrap
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from claude_hh.antagonist import SIMILARITY_THRESHOLD

# 连续 N 次失败原因相似 → 判定「原地打转」提前 stuck（loop engineering 护栏③：无进展检测，
# 原文即"两轮无变化即退出"）。复用 antagonist 的 SIMILARITY_THRESHOLD，不另造阈值数字。
SAME_REASON_LIMIT = 2

# loop engineering 护栏②（成本预算）最小版：累计本条 pipeline 的 LLM 审查调用次数，超此软上限
# 只「提醒」PM 不熔断（先观察真实花费数据再决定要不要硬卡）。正常 standard 任务约 2-8 次。
SOFT_REVIEW_BUDGET = 12

CLAUDE_MD_GUIDE = """\
<!-- claude-hh:auto-start-guide v1.0.6 -->

# Claude H-H v1.0.x — Project Protocol (HIGH PRIORITY)

This project uses **Claude H-H v1.0.x** (simplified 4-stage spec-first pipeline).

## ⚠️ Priority Override — ignore older v0.3.x instructions

If your **global / user-level CLAUDE.md** contains references to:

- `python3 -m harness.pipeline` (old long form)
- `~/Desktop/harness-engineering/` paths
- Multi-Agent roleplay (小明 / 小艺 / 小后 / 小测 / 浊龙 / 小测)
- `--route=standard|micro|full|standard-deploy` flags
- "派 Sonnet 子 Agent" / "派 Explore" patterns
- `pipeline.json 不可直接修改` blanket rules
- `--project=...` flag forms

**those refer to the deprecated v0.3.x system**. For THIS project, follow
v1.0.x rules below instead:

- Use the `harness` shell command (e.g. `harness start "..."`, NOT
  `python3 -m harness.pipeline start ...`)
- Do **NOT** spawn sub-agents — this is a single-PM tool. You handle the
  whole pipeline yourself, you do not delegate to 小明/小艺/小后/小测.
- `.harness/pipeline.json` can be **read freely** — it's just JSON state.
  Reading it (cat / Read tool) is not "tampering". Only writes/edits are
  controlled (use `harness advance` / `retreat` / `reset` for state changes).
- There is **no `--route=` flag** in v1.0.x. There is exactly one flow:
  SPEC → IMPLEMENT → REVIEW → TEST.
- There is **no `--project=` flag** — `harness` resolves the project from
  the current working directory.

## Auto-start protocol

Follow this on every session start, **before responding to the user**:

### Step 1: Read pipeline state

Run `cat .harness/pipeline.json 2>/dev/null` (or use the Read tool):

- **File missing or empty** → no pipeline yet. Go to Step 2.
- **File exists** → read the `description` field — that IS the user's current
  task. Read `current_stage`, then act:
  - `spec` → write `.harness/spec.md` (≥3 P0 ACs) + `.harness/test_*.py`. Run `harness advance`.
  - `implement` → edit code files to satisfy spec. When tests pass: `harness advance`.
  - `review` → write `.harness/review_report.md` ending with `PROCEED` or `FAIL`. Then `harness advance`.
  - `test` → run `harness advance` (pipeline auto-runs tests).
  - `done` / `stuck` → tell user the result; ask before reset.

### Step 2: User gives a new task

When the user describes a task and `pipeline.json` does NOT exist:

1. Optionally give a short plan in the chat for the user to confirm
   (this is fine — PM-friendly UX).
2. Once confirmed (or if the request is unambiguous), **YOU run** (don't ask user to run):
   ```
   harness start "<concise description, ≤80 chars, user's language>"
   ```
3. Then write `.harness/spec.md` from your plan + `.harness/test_*.py`.
4. Continue from Step 1.

### Step 3: Hermes consultation

In SPEC stage, also run `harness hermes-show` to see merged
implicit-expectations (builtin + user + project). Apply relevant items as
P0 ACs in spec.md.

## Critical rules

- **The user is non-technical.** Never ask them to type shell commands.
  You run all `harness` commands yourself.
- **Don't reset pipeline** without explicit permission. If unclear, ask.
- **If a stop hook says "pipeline incomplete"** — run `harness advance` (or
  fix the failing check). Don't try to bypass with `--no-verify`-style flags
  (none exist in v1.0.x anyway).

<!-- /claude-hh:auto-start-guide -->
"""

def _ensure_claude_md(root: Path) -> None:
    """Idempotent: write H-H auto-start guide to <root>/CLAUDE.md.

    Behavior:
    - File missing -> create with current guide
    - File exists, contains current version marker -> no change
    - File exists, contains older version marker -> replace marked block
    - File exists, no marker -> append guide
    """
    md = root / "CLAUDE.md"
    current_marker = "<!-- claude-hh:auto-start-guide v1.0.6 -->"
    if not md.exists():
        md.write_text(CLAUDE_MD_GUIDE)
        return
    existing = md.read_text()
    if current_marker in existing:
        return  # current version already installed
    # Replace any older marked block (v1.0.4, v1.0.5, ...)
    older_block_re = re.compile(
        r"<!-- claude-hh:auto-start-guide[^>]*-->.*?<!-- /claude-hh:auto-start-guide -->",
        re.DOTALL,
    )
    if older_block_re.search(existing):
        replaced = older_block_re.sub(CLAUDE_MD_GUIDE.strip(), existing)
        md.write_text(replaced)
        return
    # No marker -> append
    md.write_text(existing.rstrip() + chr(10) + chr(10) + CLAUDE_MD_GUIDE)

STAGE_LABELS = {"spec":"在写规格","implement":"在写代码","review":"在自审","test":"在跑测试","done":"做完了","stuck":"卡住了"}
PROMPTS = {s: Path(__file__).parent.parent/"prompts"/f"0{i+1}_{s}.md" for i,s in enumerate(["spec","implement","review","test"])}
NEXT_STEPS = {
    "spec": "写清楚什么算做完（规格 + 测试用例）",
    "implement": "写代码满足规格",
    "review": "AI 自审 + 独立审查",
    "test": "跑测试验证",
    "done": "这次开发已完成",
    "stuck": "需要你看一下要不要换方向",
}

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _hdir(root: Path) -> Path: d = root/".harness"; d.mkdir(exist_ok=True); return d
def _pj(root: Path) -> Path: return root/".harness"/"pipeline.json"
def _load(root: Path) -> dict: return json.loads(_pj(root).read_text())
def _save(root: Path, s: dict) -> None:
    # Atomic write: tempfile + os.replace (P0 安全审计 — 防并发腐烂状态)
    import tempfile
    target = _pj(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    # 保护单调计数器：_bump_review_calls 直接写盘，而 advance/retreat 持有的 state 可能更旧，
    # 若直接覆盖会丢计数。取磁盘与内存的较大值（仅此键，不影响其他状态）。
    try:
        disk_calls = int(json.loads(target.read_text()).get("llm_review_calls", 0))
        if disk_calls > int(s.get("llm_review_calls", 0)):
            s = {**s, "llm_review_calls": disk_calls}
    except Exception:
        pass
    fd, tmp = tempfile.mkstemp(prefix=".pipeline.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(target))
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

def _find_root(start: "Path|None" = None) -> "Path|None":
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        if _pj(parent).exists(): return parent
    return None

def _prompt(stage: str) -> None:
    f = PROMPTS.get(stage)
    if f and f.exists(): print("-"*60 + f.read_text() + "-"*60)

def _ruff_mypy(root: Path) -> bool:
    ok = True
    r = subprocess.run(["ruff","check",str(root)], capture_output=True, text=True)
    if r.returncode != 0: print("ruff FAIL: " + r.stdout[:600]); ok = False
    else: print("ruff OK")
    try:
        r2 = subprocess.run(["mypy",str(root),"--ignore-missing-imports"], capture_output=True, text=True, timeout=30)
        if r2.returncode != 0: print("mypy FAIL: " + r2.stdout[:600]); ok = False
        else: print("mypy OK")
    except FileNotFoundError: print("mypy not installed, skipping")
    return ok

def _check_spec(root: Path) -> "tuple[bool,str]":
    spec = root/".harness"/"spec.md"
    if not spec.exists(): return False, "spec.md 不存在，请先创建 .harness/spec.md"
    if spec.read_text().count("P0") < 3: return False, "spec.md P0 不足 3 条。"
    if not glob.glob(str(root/".harness"/"test_*.py")): return False, "需要至少 1 个 .harness/test_*.py。"
    return True, ""

def _impl_diff_size(root: Path) -> "tuple[int,int] | None":
    """Return (added_lines, deleted_lines) for .py changes vs HEAD, or None if git unavailable."""
    try:
        r = subprocess.run(
            ["git", "diff", "--shortstat", "HEAD"],
            cwd=str(root), capture_output=True, text=True, timeout=10, check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    ins_m = re.search(r"(\d+) insertion", r.stdout)
    del_m = re.search(r"(\d+) deletion", r.stdout)
    return (int(ins_m.group(1)) if ins_m else 0, int(del_m.group(1)) if del_m else 0)


_CODE_SUFFIXES = (".py", ".js", ".ts", ".tsx", ".vue", ".go", ".rs", ".java", ".rb", ".php")


def _format_new_file_as_diff(root: Path, rel_path: str) -> str:
    """把新增的 untracked 文件格式化成 unified diff 片段（让 reviewer 看得见）."""
    p = root / rel_path
    if not p.exists() or p.is_dir():
        return ""
    if p.suffix not in _CODE_SUFFIXES:
        return ""
    try:
        content = p.read_text(errors="replace")
    except OSError:
        return ""
    # 大文件截断（防超 token）
    lines = content.splitlines()[:500]
    body = "\n".join("+" + ln for ln in lines)
    return f"diff --git a/{rel_path} b/{rel_path}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel_path}\n{body}\n"


def _impl_period_diff(root: Path) -> str:
    """获取本期改动的 diff（给 cross-family reviewer 用）.

    包含：
    1. tracked 文件的 working tree diff (vs HEAD)
    2. untracked 新文件的内容（格式化为 +line 片段）
    3. 如以上都空，回退到 stage 期间 commit 的 -p log
    """
    parts: list[str] = []
    try:
        # 1. tracked file diff
        r = subprocess.run(
            ["git", "diff", "HEAD"], cwd=str(root),
            capture_output=True, text=True, timeout=30, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            parts.append(r.stdout)
        # 2. untracked new code files (git diff HEAD 不显示未 add 的新文件)
        r2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(root), capture_output=True, text=True, timeout=10, check=False,
        )
        if r2.returncode == 0:
            for rel in r2.stdout.splitlines():
                if rel.startswith(".harness/"):
                    continue  # 跳过 pipeline 自己的产物
                frag = _format_new_file_as_diff(root, rel)
                if frag:
                    parts.append(frag)
        if parts:
            return "\n".join(parts)
        # 3. fall back to commits made during impl stage
        state_file = root / ".harness" / "pipeline.json"
        if not state_file.exists():
            return ""
        state = json.loads(state_file.read_text())
        impl_entry = None
        for e in state.get("stage_history", []):
            if e.get("stage") == "implement":
                impl_entry = e.get("entered_at")
        if not impl_entry:
            return ""
        r3 = subprocess.run(
            ["git", "log", "-p", f"--since={impl_entry}", "--"],
            cwd=str(root), capture_output=True, text=True, timeout=30, check=False,
        )
        if r3.returncode == 0 and r3.stdout.strip():
            return r3.stdout
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return ""


def _has_commits_since(root: Path, since_iso: str) -> bool:
    """Returns True if git log shows any commits since `since_iso`."""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"--since={since_iso}"],
            cwd=str(root), capture_output=True, text=True, timeout=10, check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    if r.returncode != 0:
        return False
    return bool(r.stdout.strip())


def _check_impl(root: Path, state: dict) -> "tuple[bool,str]":
    """Implement check + empty-shell detection (防 feedback_sonnet_empty_delivery):
    - 至少 1 个 .py 文件 mtime 比 stage 进入时间新（基础检查）
    - 如果在 git 仓库内：working tree diff == 0 且本 stage 期间也没有 commit → 空壳
    """
    hist = state.get("stage_history", [])
    stage_entry_iso = hist[-1]["entered_at"] if hist else None
    ts = datetime.fromisoformat(stage_entry_iso).timestamp() if stage_entry_iso else 0
    modified = False
    for py in root.rglob("*.py"):
        if ".harness" not in py.parts and py.stat().st_mtime > ts:
            modified = True
            break
    if not modified:
        return False, "AI 还没改任何代码"
    diff_size = _impl_diff_size(root)
    if diff_size is not None:
        added, deleted = diff_size
        committed = _has_commits_since(root, stage_entry_iso) if stage_entry_iso else False
        if added + deleted == 0 and not committed:
            return False, "文件被碰了但内容没真改（看起来是空壳）。让 AI 真写代码再继续"
        if 0 < added + deleted < 3 and not state.get("retreat_count"):
            print(f"  ⚠️  改动量很小（共 {added + deleted} 行）。如果这就是预期就继续。")
    return True, ""

CROSS_FAMILY_REVIEW_PROMPT = """你是独立代码评审员。审查下方"本期改动"是否有 P0 阻断级问题。

【严格 scope - 必须遵守】
- 只评审 diff 里的改动，不评审 diff 外的历史代码
- 看不到完整上下文时说"无法判断 X"，**不能编造** diff 外代码长什么样
- 不报"未来某种情况可能出现的 P0" - 只报本期 diff 引入的真实回归
- 不报命名、注释、风格、文档类小问题

【输出格式】
最后一行必须是这两种之一：
- PROCEED
- FAIL: <一句话原因>

【本期规格】
{spec}

【本期改动 (git diff HEAD)】
{diff}

【主 Agent 自审结论】
{review}
"""


def _bump_review_calls(root: Path) -> int:
    """累计本条 pipeline 的 LLM 审查调用次数（成本可见性，最小版只观察不熔断）。返回累计值。"""
    pj = _pj(root)
    try:
        state = json.loads(pj.read_text())
    except Exception:
        return 0
    n = int(state.get("llm_review_calls", 0)) + 1
    state["llm_review_calls"] = n
    _save(root, state)
    return n


def _review_budget_warning(count: int) -> str:
    """软上限提醒：超过 SOFT_REVIEW_BUDGET 返回中文提醒，否则空串。软提醒，不熔断主流程。"""
    if count > SOFT_REVIEW_BUDGET:
        return (f"⚠️ 这条任务已调用 {count} 次 LLM 审查（软上限 {SOFT_REVIEW_BUDGET}），花费偏高——"
                "多半是反复回炉没收敛。建议看看是不是需求不清或方向要调整（仅提醒，不影响放行）。")
    return ""


def _cross_family_review(root: Path) -> "tuple[bool, str]":
    """Single-round lightweight cross-family review (替代 G4 的真正价值).

    设计原则（针对 G4 失败的 3 个根因）:
    - 一轮就出结果，不要 cp=3 折腾
    - 只送 git diff，不送完整文件（防 scope creep）
    - prompt 硬规定"看不到的不要编"（防 hallucination）
    - API 失败 / 未配置 / 输出无法解析 → 静默放行（不阻塞主流程）
    """
    try:
        from claude_hh.antagonist import load_env
        load_env(str(root))
    except Exception:
        pass
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return True, ""

    spec_path = root / ".harness" / "spec.md"
    review_path = root / ".harness" / "review_report.md"
    spec_text = spec_path.read_text()[:5000] if spec_path.exists() else "(无)"
    review_text = review_path.read_text()[:3000] if review_path.exists() else "(无)"

    diff_text = _impl_period_diff(root)
    if not diff_text.strip():
        return True, ""

    if len(diff_text) > 20000:
        diff_text = diff_text[:20000] + "\n[diff 已截断]"

    prompt = CROSS_FAMILY_REVIEW_PROMPT.format(
        spec=spec_text, diff=diff_text, review=review_text,
    )

    import urllib.request
    import urllib.error
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    print("  独立审查中...")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError, TimeoutError) as e:
        print(f"  (独立审查跳过：API 不可用 - {type(e).__name__})")
        return True, ""

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print("  (独立审查跳过：API 返回格式异常)")
        return True, ""

    last_lines = [ln.strip() for ln in (content or "").strip().splitlines() if ln.strip()]
    if not last_lines:
        return True, ""
    _w = _review_budget_warning(_bump_review_calls(root))  # 确认 DeepSeek 给出有效响应后才计数
    if _w: print("  " + _w)
    last = last_lines[-1].upper()
    if last == "PROCEED" or last.endswith("PROCEED"):
        print("  ✓ 独立审查通过")
        return True, ""
    if last.startswith("FAIL"):
        reason = last_lines[-1].split(":", 1)[-1].split("：", 1)[-1].strip()
        # "判定不通过"是 cmd_advance 自动回炉的触发关键词，措辞不能改
        return False, f"独立审查判定不通过：{reason or '未给出原因'}"
    # 无法解析 → 不阻塞
    print("  (独立审查结果无法解析，按通过处理)")
    return True, ""


def _fresh_context_review(root: Path) -> "tuple[bool, str]":
    """Claude 干净上下文二审（自动化的"双重验证"）.

    同家族但全新上下文（claude -p 单次调用）——审查者不知道代码是怎么写出来的，
    没有"我写的肯定对"的自我说服。约束照搬跨家族审查（G4 0/38 教训）：
    一轮出结果、只看 diff、看不到的不许编、fail-open 不阻塞主流程。
    """
    diff_text = _impl_period_diff(root)
    if not diff_text.strip():
        return True, ""  # 没东西可审，不烧额度
    if len(diff_text) > 20000:
        diff_text = diff_text[:20000] + "\n[diff 已截断]"
    spec_path = root / ".harness" / "spec.md"
    review_path = root / ".harness" / "review_report.md"
    spec_text = spec_path.read_text()[:5000] if spec_path.exists() else "(无)"
    review_text = review_path.read_text()[:3000] if review_path.exists() else "(无)"
    prompt = CROSS_FAMILY_REVIEW_PROMPT.format(spec=spec_text, diff=diff_text, review=review_text)

    print("  二审中（Claude 干净上下文）...")
    try:
        # cwd 必须是中立目录：(1) 防止二审进程加载被审项目自己的 hooks
        # （stop_check 会拦它收工导致 180s 超时）；(2) 物理隔离——审查者
        # 只能看 prompt 里的 diff，读不到仓库，"看不到的不许编"从软规则变硬约束
        import tempfile
        r = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=180, cwd=tempfile.gettempdir(),
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        print("  (二审跳过：claude CLI 不可用)")
        return True, ""
    if r.returncode != 0:
        print("  (二审跳过：claude CLI 返回错误)")
        return True, ""
    last_lines = [ln.strip() for ln in (r.stdout or "").strip().splitlines() if ln.strip()]
    if not last_lines:
        return True, ""
    _w = _review_budget_warning(_bump_review_calls(root))  # 确认 claude 给出有效响应后才计数
    if _w: print("  " + _w)
    last = last_lines[-1].upper()
    if last == "PROCEED" or last.endswith("PROCEED"):
        print("  ✓ 二审通过")
        return True, ""
    if last.startswith("FAIL"):
        reason = last_lines[-1].split(":", 1)[-1].split("：", 1)[-1].strip()
        return False, f"二审判定不通过：{reason or '未给出原因'}"
    print("  (二审结果无法解析，按通过处理)")
    return True, ""


def _last_review_dissent(root: Path, who: str) -> str:
    """读某审查器(fresh/cross)上一轮的反对文本（用于检测连续相似反对/移动球门）。"""
    try:
        return (_load(root).get("last_review_dissent") or {}).get(who) or ""
    except Exception:
        return ""


def _update_review_dissent(root: Path, fresh_ok: bool, fresh_msg: str,
                           cross_ok: bool, cross_msg: str) -> None:
    """记录本轮各审查器的反对：通过→清空(重置 streak)，反对→存文本，供下一轮比对。"""
    try:
        st = _load(root)
    except Exception:
        return
    d = st.get("last_review_dissent") or {}
    d["fresh"] = "" if fresh_ok else (fresh_msg or "")
    d["cross"] = "" if cross_ok else (cross_msg or "")
    st["last_review_dissent"] = d
    _save(root, st)


def _record_review_advisory(root: Path, who: str, msg: str) -> None:
    """完美主义熔断：把落单审查器连续相似的反对记为 advisory（建议，不阻断放行）。"""
    label = {"fresh": "二审", "cross": "三審"}.get(who, who)
    f = _hdir(root) / "review_advisory.md"
    if not f.exists():
        f.write_text("# 审查 advisory\n\n落单审查者连续相似反对、已熔断放行的记录；PM 可酌情参考，不阻断交付。\n\n")
    with f.open("a") as fp:
        fp.write(f"## {label} 连续反对（{_now()[:19]}）\n\n{msg}\n\n")


def _check_review(root: Path) -> "tuple[bool,str]":
    """Strict verdict match (P0 安全审计 — 防注释里 PROCEED 绕过):
    - verdict 必须在文件末段 30 行内（避免 prose 里散落的 PROCEED/FAIL 被当判决）
    - 屏蔽 ``` 代码块
    - 用 \\b PROCEED \\b / \\b FAIL \\b 词边界匹配
    - 末段同时出现两者 → 取最后一个为准
    + 跨家族独立审查（DeepSeek，配置 DEEPSEEK_API_KEY 启用，未配置静默跳过）
    """
    rp = root/".harness"/"review_report.md"
    if not rp.exists():
        return False, "AI 还没写自审报告（.harness/review_report.md 缺失）"
    t = rp.read_text()
    tail = "\n".join(t.splitlines()[-30:])
    tail_clean = re.sub(r"```.*?```", "", tail, flags=re.DOTALL)
    last_proceed = -1
    last_fail = -1
    for m in re.finditer(r"\bPROCEED\b", tail_clean):
        last_proceed = m.start()
    for m in re.finditer(r"\bFAIL\b", tail_clean):
        last_fail = m.start()
    if last_fail == -1 and last_proceed == -1:
        return False, "自审报告末段没看到 PROCEED 或 FAIL 判定"
    if last_fail > last_proceed:
        return False, "自审判定不通过，回去修"
    if not _ruff_mypy(root):
        return False, "代码风格 / 类型检查没过"
    # 二审：Claude 干净上下文。FAIL 直接回炉——同源清净审查的反对是强信号，照旧短路三审省额度。
    fr_ok, fr_msg = _fresh_context_review(root)
    if not fr_ok:
        _update_review_dissent(root, False, fr_msg, True, "")
        return False, fr_msg
    # 三审：跨家族 DeepSeek。二审已过，三审反对时检测"移动球门"完美主义死循环（治 (N-1) 共识缺失）。
    cf_ok, cf_msg = _cross_family_review(root)
    if cf_ok:
        _update_review_dissent(root, True, "", True, "")   # 全过 → 重置 streak
        return True, ""
    prev = _last_review_dissent(root, "cross")
    if prev and _reason_similar(prev, cf_msg):
        # 完美主义熔断：二审已通过 + 三审连续相似反对（移动球门）→ 接受 + 记 advisory（不阻断）
        _record_review_advisory(root, "cross", cf_msg)
        _update_review_dissent(root, True, "", True, "")   # 熔断放行后重置 streak
        return True, ""
    # 三审首次新反对 → 记下供下轮比对，回炉修（保质量，不放水）
    _update_review_dissent(root, True, "", False, cf_msg)
    return False, cf_msg

def _check_g4(root: Path) -> "tuple[bool,str]":
    """Gate 4: cross-family antagonist audit. Pass = consecutive_pass >= 3.

    Skipped when DEEPSEEK_API_KEY 未配置（G4 需要至少 2 家 LLM，DeepSeek 是第二家）。
    """
    state_file = root/".harness"/"antagonist_state.json"
    # 先加载 ~/.harness/.env + 项目 .env，再判断 KEY 是否配置（advance 链路漏调过）
    from claude_hh.antagonist import load_env
    load_env(str(root))
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return True, "(G4 跳过: DEEPSEEK_API_KEY 未配置；建议配置后启用跨家族审查)"
    if not state_file.exists():
        return False, "G4 终审尚未跑。运行 `harness antagonist run` 启动跨家族审查（cp 需达 3）。"
    try:
        s = json.loads(state_file.read_text())
        cp = s.get("consecutive_pass", 0)
        if cp >= 3:
            return True, ""
        return False, f"G4 终审 cp={cp}/3。继续运行 `harness antagonist run` 直到 cp=3。"
    except Exception as e:
        return False, f"G4 状态文件读取失败：{e}"

def _run_tests(root: Path) -> "tuple[bool,str]":
    """Strict test PASS (P0 安全审计 — 堵 skip-only / pytest 缺失 空壳):
    - 解析 'N passed' 计数，必须 ≥1
    - exit code 5 (no tests collected) 显式失败
    - pytest 缺失抛错，不静默放行
    """
    import re
    tests = glob.glob(str(root/".harness"/"test_*.py"))
    if not tests:
        return False, "没找到测试文件（.harness/test_*.py 缺失）"
    total_passed = 0
    for tf in tests:
        name = Path(tf).name
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", tf, "-v", "--tb=short"],
                capture_output=True, text=True, timeout=120, cwd=str(root),
            )
        except FileNotFoundError as e:
            return False, f"找不到 pytest，没法跑测试：{e}"
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 5:
            return False, f"测试文件没有任何用例可跑（可能全是 skip 或空文件）：{name}"
        if r.returncode != 0:
            fails = [ln for ln in out.splitlines() if "FAILED" in ln or "ERROR" in ln][:3]
            tail = "\n".join(fails) if fails else out[-300:]
            return False, f"测试不通过 {name}:\n{tail}"
        m = re.search(r"(\d+) passed", out)
        if not m:
            return False, f"测试 exit 0 但没找到 'N passed' 计数（pytest 输出异常）：{name}"
        passed = int(m.group(1))
        if passed == 0:
            return False, f"测试没真跑任何用例（可能全是 skip）：{name}"
        total_passed += passed
    return True, f"{total_passed} 个测试用例全过"

def _append_retreat_log(root: Path, n: int, reason: str) -> None:
    """错题本：每次 retreat 的原因落盘，下一轮（哪怕是干净上下文）先读再修."""
    log = _hdir(root) / "retreat_log.md"
    if not log.exists():
        log.write_text("# 错题本\n\n每轮没通过的原因。修之前先读，针对原因修，不要盲改。\n\n")
    with log.open("a") as f:
        f.write(f"## 第 {n} 次没过 — {_now()[:19]}\n\n{reason}\n\n")


def _reason_similar(a: str, b: str) -> bool:
    """两次 retreat 失败原因是否「同一个问题」—— 复用 antagonist 的 SequenceMatcher + 阈值。

    与 antagonist._issues_similar 同核（difflib.SequenceMatcher + SIMILARITY_THRESHOLD），
    但 retreat 原因没有「文件」维度，故只比文本。除对称 ratio 外，再加一道容差：
    一次失败的原因常是上一次的「核心 + 追加说明」，用最长公共连续块占较短原因的比例兜底，
    避免「同一问题多写两句」被字符级 ratio 因长度差拉低而漏判。两道都用 0.85 同一阈值。
    """
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    sm = SequenceMatcher(None, a, b)
    if sm.ratio() > SIMILARITY_THRESHOLD:
        return True
    short_len = min(len(a), len(b))
    block = sm.find_longest_match(0, len(a), 0, len(b)).size
    return short_len > 0 and block / short_len > SIMILARITY_THRESHOLD


def _retreat_briefing(root: Path, n: int = 3) -> str:
    """错题本提要：返回最近 n 次 retreat 失败原因，供物理注入（回炉输出 / pre_edit 提醒）。

    直接读已落盘的 retreat_log.md，取最后 n 个「## 第 X 次」小节。
    无 log / 无记录 → 返回空串（调用方据此决定不打印）。
    """
    log = _hdir(root) / "retreat_log.md"
    if not log.exists():
        return ""
    sections = re.split(r"(?=^## 第 )", log.read_text(), flags=re.M)
    entries = [s.strip() for s in sections if s.strip().startswith("## 第 ")]
    if not entries:
        return ""
    recent = entries[-n:]
    body = "\n\n".join(recent)
    return f"📕 错题本（最近 {len(recent)} 次没过的原因，先看再改，别重复踩）：\n\n{body}"


def _retreat(root: Path, state: dict, reason: str) -> None:
    state["retreat_count"] = n = state.get("retreat_count", 0) + 1
    _append_retreat_log(root, n, reason)

    # 原地打转检测：连续 SAME_REASON_LIMIT 次失败原因相似 → 提前 stuck，不耗满 3 次。
    prev = state.get("last_retreat_reason")
    state["last_retreat_reason"] = reason
    streak = state.get("same_reason_streak", 1) + 1 if (prev and _reason_similar(prev, reason)) else 1
    state["same_reason_streak"] = streak
    spinning = streak >= SAME_REASON_LIMIT

    # 错题本物理注入：把最近失败摘要直接打进回炉输出，不依赖 AI 自觉去读 log。
    briefing = _retreat_briefing(root)

    if spinning or n > 3:
        state["current_stage"] = "stuck"
        if spinning:
            notice = (
                f"# 卡住了（原地打转）\n\n连续 {streak} 次都卡在同一个问题上"
                f"（失败原因高度相似），再回炉大概率还是同样结果。最后一次原因：\n\n{reason}\n\n"
                "「重复同一个失败」通常是方向不对或需求描述不清，需要你介入，不该再自动重试。\n"
            )
        else:
            notice = (
                f"# 卡住了\n\n这次开发回头修了 {n} 次都没过。最后一次没过的原因：\n\n{reason}\n\n"
                "可能是需求描述不够清楚，或者方向需要调整。\n"
            )
        (_hdir(root)/"stuck_notice.md").write_text(notice)
        _save(root, state)
        if spinning:
            print(f"连续 {streak} 次卡在同一个问题上（原地打转），我先停下不瞎试了。原因：{reason}")
        else:
            print(f"修了 {n} 次都没过，我卡住了。最后一次原因：{reason}")
        print("可能是要换个方向，或者需求描述需要补充。要不要告诉我哪里不对？")
        return

    state["current_stage"] = "implement"
    state.setdefault("stage_history",[]).append({"stage":"implement","entered_at":_now(),"reason":f"retreat #{n}"})
    _save(root, state)
    print(f"这次没通过，回头再修一次（第 {n}/3 次）。原因：{reason}")
    if briefing:
        print()
        print(briefing)
    if n >= 2:
        print('💬 卡了多次了？说一句你觉得哪里不对：harness feedback "..."')

def _require_root(args: argparse.Namespace) -> Path:
    root = _find_root(Path(args.project) if args.project else None)
    if root is None: print("还没有进行中的开发任务。先说一句要做什么再开始。"); sys.exit(1)
    return root

# CLI commands

def cmd_init(args: argparse.Namespace) -> None:
    root = Path(args.project) if args.project else Path.cwd()
    sd = root/".claude"; sd.mkdir(exist_ok=True); sf = sd/"settings.json"
    cfg = json.loads(sf.read_text()) if sf.exists() else {}
    hh = Path(__file__).parent.parent
    h = cfg.setdefault("hooks", {})

    pre_edit_cmd = f"python3 {hh}/hooks/pre_edit.py"
    stop_check_cmd = f"python3 {hh}/hooks/stop_check.py"

    def _is_v03(cmd: str) -> bool:
        return "harness-engineering" in cmd or "/install_v2.py" in cmd
    def _is_v1(cmd: str) -> bool:
        return ".claude-hh/hooks/" in cmd or cmd in (pre_edit_cmd, stop_check_cmd)

    cleaned_v03, kept_v1 = 0, 0
    for stage in list(h.keys()):
        new_entries = []
        for entry in h.get(stage, []):
            new_hooks = []
            for hk in entry.get("hooks", []):
                cmd = hk.get("command", "")
                if _is_v03(cmd):
                    cleaned_v03 += 1; continue
                if _is_v1(cmd):
                    kept_v1 += 1
                new_hooks.append(hk)
            if new_hooks:
                e = dict(entry); e["hooks"] = new_hooks; new_entries.append(e)
        h[stage] = new_entries

    has_pre_edit = any(any(hk.get("command")==pre_edit_cmd for hk in e.get("hooks",[])) for e in h.get("PreToolUse",[]))
    has_stop_check = any(any(hk.get("command")==stop_check_cmd for hk in e.get("hooks",[])) for e in h.get("Stop",[]))

    added = []
    if not has_pre_edit:
        h.setdefault("PreToolUse",[]).append({"matcher":"Edit|Write|MultiEdit","hooks":[{"type":"command","command":pre_edit_cmd}]})
        added.append("pre_edit")
    if not has_stop_check:
        h.setdefault("Stop",[]).append({"hooks":[{"type":"command","command":stop_check_cmd}]})
        added.append("stop_check")

    sf.write_text(json.dumps(cfg, indent=2)); _hdir(root)
    _ensure_claude_md(root)

    parts = []
    if cleaned_v03: parts.append(f"清理 {cleaned_v03} 个 v0.3.x 老 hook")
    if added: parts.append(f"装 {len(added)} 个 v1 hook ({'+'.join(added)})")
    if not parts: parts.append("hooks 已就绪（幂等，无变化）")
    print(f"Claude H-H 初始化在 {root}")
    print(f"  · {'; '.join(parts)}")
    print("  · 运行 `harness start \"<任务描述>\"` 开始。")

def cmd_start(args: argparse.Namespace) -> None:
    root = Path(args.project) if args.project else Path.cwd()
    _hdir(root)  # 确保 .harness/ 存在
    pj = _pj(root)
    if pj.exists():
        # 已 done/stuck → 自动 reset 启新任务（PM 体验：开工不用敲两行）
        # 进行中 (spec/implement/review/test, 或 v0.3.x int 1..5) → 拒绝，保护未完成任务
        try:
            stage = json.loads(pj.read_text()).get("current_stage")
        except Exception:
            stage = None
        is_finished = (stage in ("done","stuck")) or (isinstance(stage,int) and stage >= 6)
        if is_finished:
            pj.unlink()
            print(f"上次任务已 {STAGE_LABELS.get(stage, stage)}，自动清掉。")
        else:
            label = STAGE_LABELS.get(stage, str(stage))
            print(f"已经有任务在做（{label}）。先做完它，或者告诉我'清掉重来'。")
            sys.exit(1)
    # 清掉上个任务的残留（错题本/交付报告属于上个任务，留着会污染新任务）
    for residue in ("retreat_log.md", "delivery_report.md"):
        (root / ".harness" / residue).unlink(missing_ok=True)
    desc = " ".join(args.desc) if args.desc else "未命名任务"
    _save(root,{"current_stage":"spec","retreat_count":0,"description":desc,"started_at":_now(),"updated_at":_now(),"stage_history":[{"stage":"spec","entered_at":_now()}]})
    print(f'开始做："{desc}"')
    # 独立审查可用性提示（只提醒不阻塞——PM 该知道质检员到底在不在岗）
    try:
        from claude_hh.antagonist import load_env
        load_env(str(root))
    except Exception:  # noqa: BLE001 — 提示性检查，加载失败不阻塞开工
        pass
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("ℹ️  跨家族独立审查未启用（没配 DEEPSEEK_API_KEY）。审查将只有 AI 自审 + 静态检查。")
    _prompt("spec"); print("第一步：写清楚什么算做完（规格 + 测试用例）。")

def cmd_advance(args: argparse.Namespace) -> None:
    root = _require_root(args); state = _load(root); stage = state["current_stage"]
    if stage == "done": print("这次开发已经做完了 ✓"); return
    if stage == "stuck":
        print("这次开发卡住了，需要换个方向或者重新开始。要清掉重来吗？"); return
    if isinstance(stage, int):
        print(f"这是上次没收尾留下的旧记录（旧版格式 stage={stage}）。要清掉重新开始吗？")
        return
    checks = {
        "spec":(_check_spec,"implement","规格写好了 ✓ 开始写代码。"),
        "implement":(_check_impl,"review","代码写完 ✓ 进入自审。"),
        "review":(_check_review,"test","审查通过 ✓ 跑测试。"),
    }
    if stage in checks:
        fn, nxt, msg = checks[stage]
        ok, err = fn(root, state) if stage=="implement" else fn(root)
        if not ok:
            print(f"还没法继续：{err}")
            if stage=="review" and any(kw in err for kw in ("FAIL","ruff","mypy","判定不通过","风格","类型")): _retreat(root,state,err)
            return
        state["current_stage"]=nxt; state["stage_history"].append({"stage":nxt,"entered_at":_now()})
        _save(root,state); print(msg); _prompt(nxt)
        if nxt=="test": _finish_test(root)
    elif stage=="test": _finish_test(root)

def _check_zhuolong(root: Path) -> "tuple[str, str]":
    """黑盒测试关卡（opt-in，仅当 SPEC 阶段写了 zhuolong_brief.md 才触发）.

    返回 (status, msg)，status 三态：
    - "pass" → 没 brief（跳过）或报告判定通过
    - "wait" → 有 brief 但报告缺失/没判定 → 留在 TEST 阶段等报告
    - "fail" → 报告判定 FAIL → 自动回炉（或预算耗尽时带病交付）
    """
    brief = root/".harness"/"zhuolong_brief.md"
    if not brief.exists():
        return "pass", ""  # opt-out by default
    report = root/".harness"/"zhuolong_report.md"
    if not report.exists():
        return "wait", (
            "这次有 UI/黑盒测试需求（.harness/zhuolong_brief.md 已写），"
            "但还没跑过浊龙。让主 Agent 派浊龙跑一遍再继续"
        )
    text = report.read_text()
    tail = "\n".join(text.splitlines()[-50:]).upper()
    tail_clean = re.sub(r"```.*?```", "", tail, flags=re.DOTALL)
    has_fail = bool(re.search(r"\b(FAIL|BLOCKED|不通过)\b", tail_clean))
    has_pass = bool(re.search(r"\b(PASS|通过|可上线)\b", tail_clean))
    if has_fail and not has_pass:
        return "fail", "浊龙黑盒测试报 FAIL，回去修"
    if not has_pass:
        return "wait", "浊龙报告末段没看到 PASS/FAIL 判定"
    return "pass", ""


def _check_external_review(root: Path) -> "tuple[str, str]":
    """外测独立验收门禁。**只读 external_review.md，绝不读浊龙报告**。

    外测 = 独立 agent（干净上下文，只看 spec + 产物）对照 AC 的验收判定。
    浊龙黑盒可靠性低（实测埋雷发现率 ~20%），仅作旁证，不作放行依据，
    故本函数物理上不碰 zhuolong_report —— 浊龙取任何值都改变不了这里的判定。

    fail-closed 判定（与 _check_review 同核）：末段同时出现 PASS/FAIL 词时**取最后一个为准**，
    不让正文里散落的"通过/PASS"压过末尾的 FAIL 判定（否则一份判定 FAIL 但正文写了"大部分通过"
    的报告会被误判放行，击穿安全门禁）。

    返回 (status, msg)：
    - "pass" → external_review.md 末段最后一个判定是 PASS
    - "fail" → 末段最后一个判定是 FAIL（回炉/带病交付）
    - "wait" → external_review.md 缺失或末段无任何判定（等独立 agent，不烧 retreat 预算）
    """
    er = root / ".harness" / "external_review.md"
    if not er.exists():
        return "wait", "外测：独立验收 agent 还没产出 external_review.md，等它跑完再继续"
    tail = "\n".join(er.read_text().splitlines()[-50:]).upper()
    tail_clean = re.sub(r"```.*?```", "", tail, flags=re.DOTALL)
    last_pass = last_fail = -1
    for m in re.finditer(r"\b(PASS|通过|可上线)\b", tail_clean):
        last_pass = m.start()
    for m in re.finditer(r"\b(FAIL|BLOCKED|不通过)\b", tail_clean):
        last_fail = m.start()
    if last_fail > last_pass:
        return "fail", "外测独立验收报 FAIL，回去修"
    if last_pass == -1:
        return "wait", "external_review.md 末段没看到 PASS/FAIL 判定"
    return "pass", ""


def _external_gate(root: Path, state: dict) -> "tuple[str, str]":
    """外测关卡动作决策。放行/回炉只由独立验收 verdict 决定，浊龙永不改判。

    返回 (action, msg)：
    - "wait"     → 等独立验收（external_review 缺失/无判定）
    - "retreat"  → 验收 FAIL 且预算未耗尽 → 回炉
    - "degraded" → 验收 FAIL 且 retreat_count ≥ 3 → 带病交付，永不挂起
    - "pass"     → 验收 PASS → 放行
    """
    status, msg = _check_external_review(root)
    if status == "wait":
        return "wait", msg
    if status == "fail":
        if state.get("retreat_count", 0) >= 3:
            return "degraded", msg
        return "retreat", msg
    return "pass", msg


def _invalidate_external_review(root: Path) -> None:
    """返工前作废上一轮外测验收：删掉 stale 的 external_review.md。

    否则外测 FAIL → 回炉 → 返工后 _external_gate 读到**上一轮**残留的 FAIL，
    不等独立 agent 重新验收就立刻又回炉 → 空烧 retreat 预算 → 过早 degraded。
    删掉后下一轮变 "wait"，强制独立 agent 对**本轮**产物重新验收。
    """
    (root / ".harness" / "external_review.md").unlink(missing_ok=True)


def _degraded_delivery(root: Path, state: dict, reason: str) -> None:
    """带病交付：自动测试全过但黑盒修满预算仍没过 → 照样交付 + 诚实的交付报告.

    PM 决策（2026-06-10）：永不挂起，最终必有交付物；上不上线由 PM 看报告决定。
    """
    log = _hdir(root) / "retreat_log.md"
    history = log.read_text() if log.exists() else "（无记录）"
    rc = state.get("retreat_count", 0)
    (_hdir(root) / "delivery_report.md").write_text(
        "# 交付报告：已交付，有遗留问题 ⚠️\n\n"
        f"内测（功能自动测试）全部通过，但外测（独立验收）修了 {rc} 轮仍没过。\n"
        "按约定不再挂起，照常交付，由你决定要不要上线。\n\n"
        f"## 遗留问题（上线前请你确认）\n\n{reason}\n\n"
        "独立验收报告：`.harness/external_review.md`\n"
        "（浊龙黑盒旁证若有：`.harness/zhuolong_report.md`）\n\n"
        f"## 修复尝试记录（错题本）\n\n{history}\n"
    )
    state["current_stage"] = "done"
    state["updated_at"] = _now()
    state.setdefault("stage_history", []).append(
        {"stage": "done", "entered_at": _now(), "reason": "degraded-delivery"}
    )
    _save(root, state)
    print("这次开发做完了，但有遗留问题 ⚠️")
    print(f"  黑盒测试修了 {rc} 轮还有没过的项。详情看 .harness/delivery_report.md，上线前请你确认。")
    from claude_hh import hermes_propose
    hermes_propose.propose(root)


def _finish_test(root: Path) -> None:
    """TEST → done. G4 已从主流程移除（3 个真实 PM 项目 0/38 转化率）。
    G4 仍可通过 `harness antagonist run` 子命令独立运行。
    浊龙黑盒测试 opt-in：写 zhuolong_brief.md 才启用。
    浊龙 FAIL → 自动回炉（≤3 轮）；预算耗尽 → 带病交付，永不挂起。"""
    state = _load(root)
    ok, msg = _run_tests(root)  # 内测：Claude 自己写的测试
    state = _load(root)
    if not ok: _retreat(root,state,msg); return
    print(f"内测全过 ✓ {msg}")
    # 浊龙黑盒：仅旁证，记录不门禁（可靠性低，不作放行依据）
    z_status, z_msg = _check_zhuolong(root)
    if z_status != "pass":
        print(f"  （浊龙旁证：{z_msg}；仅供参考，不影响放行）")
    # 外测：独立验收 agent 把关（opt-in，写了 external_brief.md 才启用）
    if (root/".harness"/"external_brief.md").exists():
        action, x_msg = _external_gate(root, state)
        if action == "wait":
            print(f"  {x_msg}")
            return  # 等独立验收 agent 产出 external_review.md
        if action == "degraded":
            _degraded_delivery(root, state, x_msg)
            return
        if action == "retreat":
            _invalidate_external_review(root)  # 清 stale 验收，强制返工后重新外测
            _retreat(root, state, x_msg)
            return
    state["current_stage"]="done"; state["updated_at"]=_now(); _save(root,state)
    print("这次开发做完了 ✓")
    print('💬 想说点什么改进的？一句话：harness feedback "..."  （不写也行）')
    from claude_hh import hermes_propose; hermes_propose.propose(root)

def cmd_retreat(args: argparse.Namespace) -> None:
    root = _require_root(args); _retreat(root, _load(root), "手动 retreat")

def cmd_status(args: argparse.Namespace) -> None:
    root = _find_root(Path(args.project) if args.project else None)
    if root is None: print("还没有进行中的开发任务。"); return
    s = _load(root); stage = s["current_stage"]
    desc = s.get("description") or s.get("task_description") or "-"
    rc = s.get("retreat_count", 0)
    st = (s.get("started_at") or "-")[:19]
    # Cross-version compat: v0.3.x writes int stages (1..6), v1.x writes strings.
    if isinstance(stage, int):
        # 旧版记录不复用新版 label（避免"在跑测试"等假状态误导 PM）
        print(f'有一份旧版记录（stage={stage}），新版工具看不懂。建议告诉我"清掉重来"。')
        return
    lbl = STAGE_LABELS.get(stage, stage)
    nxt = NEXT_STEPS.get(stage, "-")
    retreat_note = f"，回头修过 {rc} 次" if rc > 0 else ""
    print(f'正在做："{desc}"（{lbl}{retreat_note}，{st} 开始）')
    print(f"  接下来：{nxt}")
    calls = s.get("llm_review_calls", 0)
    if calls:
        warn = _review_budget_warning(calls)
        print(f"  已调用 LLM 审查：{calls} 次" + (f"\n  {warn}" if warn else ""))

def cmd_reset(args: argparse.Namespace) -> None:
    root = _require_root(args); _pj(root).unlink(missing_ok=True)
    print("清掉了。说一句要做什么就开始新任务。")

def cmd_hermes_review(args: argparse.Namespace) -> None:
    from claude_hh import hermes_propose; hermes_propose.interactive_review()

def cmd_feedback(args: argparse.Namespace) -> None:
    root = _require_root(args)
    text = " ".join(args.text) if args.text else ""
    if not text.strip():
        print('用法：harness feedback "你想说的话"'); return
    inbox = _hdir(root) / "inbox.md"
    entry = "- [" + _now()[:19] + "] " + text.strip() + chr(10)
    with inbox.open("a") as f:
        f.write(entry)
    print("✓ 记下了。下次干完活时会复盘。")


def cmd_hermes_show(args: argparse.Namespace) -> None:
    root = _find_root(Path(args.project) if args.project else None)
    from claude_hh.hermes_loader import load_layers
    result = load_layers(root)
    print(result if result else "(no hermes layers found)")


def cmd_antagonist(args: argparse.Namespace) -> None:
    """Run G4 cross-family audit. Delegates to claude_hh.antagonist_cli.main()."""
    from claude_hh import antagonist_cli
    project = args.project or str(_find_root(Path.cwd()) or Path.cwd())
    sub = args.antagonist_cmd or "run"
    sys.exit(antagonist_cli.main([sub, "--project", project]))


def main() -> None:
    ap = argparse.ArgumentParser(prog="harness", description="Claude H-H v1.0 — spec-first pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""  init            初始化项目\n  start [desc]    开始 pipeline\n  advance         推进阶段\n  retreat         手动回退\n  status          查看状态\n  reset           重置\n  hermes-review   审核提议
  feedback "..."  PM 反馈，下次 pipeline 时反思
  hermes-show     显示合并后的 implicit expectations 清单
  antagonist run  跑 G4 跨家族终审（≥2 家 P0=0 × 3 轮才放行 DEPLOY）
  antagonist reset  G4 修完代码后清掉 unfixed 标记"""))
    ap.add_argument("--project", default=None)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("init"); ps = sub.add_parser("start"); ps.add_argument("desc",nargs="*")
    for c in ("advance","retreat","status","reset","hermes-review"): sub.add_parser(c)
    pf = sub.add_parser("feedback"); pf.add_argument("text", nargs="*")
    sub.add_parser("hermes-show")
    pa = sub.add_parser("antagonist"); pa.add_argument("antagonist_cmd", nargs="?", choices=["run","reset"], default="run")
    args = ap.parse_args()
    {"init":cmd_init,"start":cmd_start,"advance":cmd_advance,"retreat":cmd_retreat,
     "status":cmd_status,"reset":cmd_reset,"hermes-review":cmd_hermes_review,"feedback":cmd_feedback,
     "hermes-show":cmd_hermes_show,"antagonist":cmd_antagonist}.get(args.cmd, lambda _: ap.print_help())(args)

if __name__ == "__main__": main()
