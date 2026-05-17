# Changelog

## v1.1.4 — 2026-05-17 (PM-first language + integrity gates)

**Major release driven by full-day first-principles audit of 9 real PM projects.**

### 回归初心：所有 PM 可见字符串改成自然语言

PM 是非技术用户，工程术语（`pipeline / stage-5 / advance / retreat / stuck`）每次撞到他们都是 UX 失败。这版把每条 PM 会看到的输出全部翻译成人话。

**Before**:
```
[claude-hh] ⚠️  pipeline 未完成（stage-5），请运行 `harness advance`
Pipeline 已停滞，请 `harness reset`
retreat 到 IMPLEMENT（第 2/3 次）。原因：X
检测到 v0.3.x 旧版状态文件 (int stage=5)...
```

**After**:
```
[claude-hh] 这次开发还没做完（在写代码）。继续做完还是先放一放？
这次开发卡住了，需要换个方向或者重新开始。要清掉重来吗？
这次没通过，回头再修一次（第 2/3 次）。原因：X
这是上次没收尾留下的旧记录。要清掉重新开始吗？
```

涉及文件：`claude_hh/pipeline.py` (全部 print/error 信息)、`hooks/stop_check.py`（schg-locked 文件，升级需 sudo chflags noschg）。

### `stop_check.py` 新增 4h/24h 闲置感知

不再光看 `current_stage`，还看 `pipeline.json` 的 mtime：

- < 4h：`继续做完还是先放一放？`
- 4-24h：`暂停了 N.N 小时。要继续做完吗？`
- > 24h：`已经放了 N 小时没动。可能是上次没收尾留下的，建议清掉重来。`

修复了今天早上撞上的真实痛点：13 天前没收尾的 pipeline 还在喊"请运行 harness advance"。

### G4 跨家族 antagonist 从主流程移除

3 个真实 PM 项目跑 G4 的客观数据：
- myai: 10 rounds, 27 issues, **0 fixed**
- 大鹏: 3 rounds, 5 issues, **0 fixed**
- personal-ai-os: 3 rounds, 6 issues, **0 fixed**

→ 16 rounds / 38 issues / **0/38 真实采纳率**。同时它的失败模式（scope creep + hallucination）反向消耗 inbox.md 这条 PM 反馈通道（7 条 inbox 全是抱怨 G4）。

`_finish_test` 不再调 `_check_g4`。G4 仍保留为可选子命令 `harness antagonist run` 供 power user 使用。

### G4 真正的价值用轻量方式重新接入：`_cross_family_review`

review 阶段，如配 `DEEPSEEK_API_KEY`，自动追派一个 DeepSeek 跨家族独立 reviewer。

关键差异（针对 G4 失败的 3 个根因）：
- **一轮就出结果**，不是 `cp=3` 状态机折腾
- **只送 git diff，不送完整文件**（防 scope creep）
- prompt 硬规定"看不到的不能编"（防 hallucination）
- API 失败 / 未配置 / 输出无法解析 → 静默放行（不阻塞主流程）

### 4 处底层完整性收紧（防 AI 撒谎）

针对今天早上安全审计发现的 P0 漏洞：

1. **测试 PASS 严格化** (`_run_tests`): 不再只看 pytest exit code，要求 `re.search("N passed", out)` 命中且 N ≥ 1。堵住 pytest exit 5（无测试可跑）和"全是 skip"的空壳。
2. **`PROCEED/FAIL` 严格匹配** (`_check_review`): 改用末段 30 行 + 词边界 `\bPROCEED\b` / `\bFAIL\b` 双匹配 + 屏蔽 ``` 代码块。堵住注释 / 文档里散落的 PROCEED 关键字绕过判定。
3. **空壳交付检测** (`_check_impl`): 新增 `_impl_diff_size` 跑 `git diff --shortstat HEAD`。如果 implement 阶段 .py 文件 mtime 比 stage entry 新但 `+/-` 行数总和为 0，判 false（"文件被碰了但内容没真改"）。改动 < 3 行 + 首次 review 时温和提示。
4. **`pipeline.json` 原子写** (`_save`): 改用 `tempfile.mkstemp` + `os.replace` 模式。防并发 advance / retreat 撞坏 JSON 状态。

### 浊龙黑盒测试 opt-in 嵌入主流程

`_check_zhuolong` 新函数：

- 默认跳过（绝大多数 backend/API 项目）
- 如果 SPEC 阶段写了 `.harness/zhuolong_brief.md`，TEST 阶段 advance 必须等到 `.harness/zhuolong_report.md` 末段含 PASS/通过/可上线 字样才放行
- 报 FAIL/BLOCKED/不通过 时阻塞，回头修
- `prompts/04_test.md` 更新：教主 Agent 在 advance 前派浊龙 subagent

### 数据驱动决策

这版所有改动的依据都来自客观使用数据：

- 9 个项目实际 `.harness/` 目录全盘扫描
- 13 个项目用 spec.md、25 个用 test_*.py、11 个用 review_report.md、7 个用 proposed_auto.md
- G4 用了 4 个、PM inbox 反馈用了 2 个（全是 G4 抱怨）
- 每个组件按"真起作用 vs 摆设"客观判决，不靠工程直觉

### Upgrade path

对已装用户：因为 `~/.claude-hh/hooks/stop_check.py` 是 `schg` 锁文件，升级需要：

```sh
sudo chflags noschg ~/.claude-hh/hooks/stop_check.py
cp ~/Desktop/claude-hh-v1/hooks/stop_check.py ~/.claude-hh/hooks/stop_check.py
sudo chflags schg ~/.claude-hh/hooks/stop_check.py
```

`pipeline.py` 不锁，直接 `cp` 即可。或者重新 `pip install -e .` 同步。

---

## v1.1.3 — 2026-05-06 (cross-version migration UX)

**Two PM-friendly improvements driven by real-PM dogfooding feedback.**

### `harness init` is now idempotent + auto-cleans v0.3.x residue

Before: each `harness init` blindly appended its 2 hooks to `.claude/settings.json`. Run it 3 times → 3 duplicates. Plus, projects that previously had v0.3.x's 6 hooks (pointing at `harness-engineering/hooks/...`) would end up with both v0.3.x hooks and v1 hooks active, fighting each other.

After:
- Detects v0.3.x hooks (any `harness-engineering/hooks/...` reference) and **removes them**
- Detects v1 hooks already present and **skips re-adding** (idempotent)
- Reports what it did: `清理 N 个 v0.3.x 老 hook; 装 M 个 v1 hook`

This means PMs can run `harness init` in any project (clean / v0.3.x legacy / already-v1) and end up in a known-good single-state.

### Pain-point capture prompts (passive, opt-in)

When pipeline reaches `done`:
```
💬 这次 H-H 哪里卡到你了？一句话：harness feedback "<痛点>"  （不写也行，下次再说）
```

When `retreat` count ≥ 2:
```
💬 retreat 多次撞到坑了？一句话：harness feedback "<什么卡住了>"  帮我下次改流程。
```

PMs don't have to write anything — they just see the prompt at the moments when frustration is freshest. 15-second feedback channel via the existing `harness feedback "..."` command.

### Why these are in v1.x

Both directly serve "let non-technical PMs ship production-grade products" without adding new pipeline stages or new commands. Just better defaults on existing surfaces.

### Upgrade

Drop-in replacement for v1.1.2.

---

## v1.1.2 — 2026-05-05 (same-day P0 fix + UX)

**Fixes a latent P0 in `cmd_start` that has been silent since v1.0, plus a PM-friendly UX upgrade.**

### P0 fix: `cmd_start` was never actually rejecting overwrites

```python
# v1.0..v1.1.1 (BROKEN)
if _pj(_hdir(root)).exists(): print("已有 pipeline，请先 `harness reset`."); sys.exit(1)
```

`_hdir(root)` returns `root/".harness"`. `_pj(some_path)` returns `some_path/".harness"/"pipeline.json"`. So `_pj(_hdir(root))` = `root/".harness"/".harness"/"pipeline.json"` — a path with double `.harness/` that **never exists**. The exists() check was always False; the rejection branch was dead code.

This means since v1.0, `harness start "<new>"` on a project with an in-progress pipeline (any of spec/implement/review/test) would **silently overwrite the existing pipeline.json**, destroying the work-in-progress task without warning. Latent P0 — not triggered in practice because PMs typically don't double-start, but the safety net was off.

### UX: `harness start` now auto-resets when previous pipeline is `done` / `stuck`

Before:
```
$ harness start "next task"
已有 pipeline，请先 `harness reset`.
$ harness reset
$ harness start "next task"
```

After:
```
$ harness start "next task"
上一个 pipeline 已 done，自动清理。
Pipeline 已启动：next task  当前阶段：SPEC
```

In-progress pipelines (spec/implement/review/test) are still protected — `start` rejects with a clear message. Only terminal states (`done`, `stuck`, or v0.3.x int `>= 6`) trigger auto-reset.

### Why this is in v1.x

- The P0 fix has to ship: silent overwrite of in-progress pipelines is a data-loss bug
- The UX change saves PM one redundant command per task, doesn't add complexity
- Both compatible with v1.0 manifesto

### Upgrade

Drop-in replacement for v1.1.1.

---

## v1.1.1 — 2026-05-05 (same-day hotfix)

**`harness status` now tolerates v0.3.x pipeline.json (int stage values).**

A PM in a real project (already had v0.3.x `pipeline.json` with `current_stage: 6` and `task_description: ...`) hit `AttributeError: 'int' object has no attribute 'upper'` when running `harness status` after upgrading to v1.1.0.

`stop_check` was already fixed for this in v1.0.7, but `cmd_status` wasn't.

### Fix

- `cmd_status` now handles both v0.3.x int stages (1..6) and v1.x string stages
- Also reads `task_description` (v0.3.x field name) as fallback for `description`
- v0.3.x `done` state shows the friendly suggestion to `harness reset` + `harness start` for the next task

No behavior change for v1.x-native pipelines.

---

## v1.1.0 — 2026-05-05

**Adds G4 — cross-family LLM consensus audit, ported from v0.3.4 self-bootstrap.**

v1.0 stripped 96% of v0.3.4 because A/B data showed the only feature that helped was spec-first. We held that line for v1.0.x.

But after v1.0 shipped, the v0.3.4 codebase (kept as a research archive) was used to develop one new mechanism that **does** produce measurable value: **cross-family LLM consensus review**. Three different model families (Claude Opus + Sonnet + DeepSeek V4 Pro) independently audit `git diff`. ≥2 must report `P0=0` for 3 consecutive rounds before DEPLOY is unlocked.

Self-bootstrap on the original codebase: 18 rounds of audit found 65 issues, distilled into 21 cross-project P0 categories. These categories are auto-injected as prior defense into every future antagonist run.

### Why this is in v1.x and not "v0.3.5"

The 21 P0 categories are real, repeatable, and worth keeping. Same-family review (Claude reviewing Claude) systematically misses them because the reviewer shares the writer's RLHF blind spots. Cross-family breaks that.

### Added

- `claude_hh/antagonist.py` — core state machine + 3-family parallel audit (~1100 lines)
- `claude_hh/antagonist_cli.py` — CLI subcommand (~370 lines)
- `prompts/antagonist.md` — system prompt template
- `knowledge/antagonist_issues.md` — 21 cross-project P0 categories (the self-bootstrap output, kept 1:1)
- `harness antagonist run` / `harness antagonist reset` — new subcommands
- Pipeline integration: `harness advance` from TEST to DONE now requires `consecutive_pass >= 3` if `DEEPSEEK_API_KEY` is set; G4 is gracefully skipped (with notice) if no key

### Configuration

```bash
# In your project's .env:
DEEPSEEK_API_KEY=sk-...     # second non-Claude family for consensus
ANTHROPIC_API_KEY=sk-ant-... # already required
```

If `DEEPSEEK_API_KEY` is not set, G4 is skipped with a friendly notice — v1.1 stays a strict superset of v1.0.x behavior.

### Upgrade

No breaking changes. Existing pipelines continue to work; G4 only kicks in between TEST and DONE when the key is configured.

---

## v1.0.7 — 2026-04-30 (undocumented at the time)

`stop_check` now tolerates v0.3.x integer stage values for cross-version pipeline state compatibility.

---

## v1.0.6 — 2026-04-26

**Same-day hotfix #2 for v1.0.4-1.0.5 partial-protocol problem.** v1.0.5 fixed
the file path so Claude Code does load the project CLAUDE.md, but real PM
session showed Claude still used v0.3.x patterns: `python3 -m harness.pipeline`
old long form, `~/Desktop/harness-engineering/` path, multi-Agent roleplay,
`--route=standard` flags. Reason: the user's global `~/.claude/CLAUDE.md`
contains heavy v0.3.x instructions accumulated during v0.3.x development; the
project-level guide was too soft to override the user-level prior.

### Fix

The auto-start guide now leads with an explicit **Priority Override** section
that names the v0.3.x patterns to ignore (specific paths, command forms,
sub-agent names, deprecated flags) and asserts the v1.0.x replacements.

This is a prompt-engineering fix, not a hard guarantee — Claude still
ultimately decides whether to follow the project-level guide. But explicit
"ignore X / use Y instead" instructions in the project CLAUDE.md are the
strongest mechanism Claude Code currently exposes for this.

### Migration

v1.0.5 users: re-run `harness init` to update each project's CLAUDE.md to
the v1.0.6 version. Old `<!-- claude-hh:auto-start-guide v1.0.5 -->` markers
will be **replaced**, not duplicated, by the new init code (see migration
fix below).

### Note on idempotency across versions

`_ensure_claude_md` previously matched `<!-- claude-hh:auto-start-guide` (any
version) and skipped if found, which would prevent v1.0.5 users from getting
the v1.0.6 guide on re-init. Fixed: if the existing marker version differs
from current, replace the marked block; same version, skip.


## v1.0.5 — 2026-04-26

**Same-day hotfix for v1.0.4 path bug.** v1.0.4 wrote the auto-start
guide to `<project>/.claude/CLAUDE.md`, but Claude Code's standard
project-level CLAUDE.md location is the **project root**
(`<project>/CLAUDE.md`). The file was correctly created but Claude
Code never loaded it, so v1.0.4 had no observable behavior change.

PM hit this immediately: ran `harness init` → `claude` → described
task → Claude started working without first running `harness start`.
Inspection showed `.claude/CLAUDE.md` did contain the guide, but it
wasn't picked up.

### Fix

- `_ensure_claude_md` now writes to `<project>/CLAUDE.md` (the location
  Claude Code actually loads on session start).
- Existing `<project>/.claude/CLAUDE.md` files from v1.0.4 are
  harmless leftovers (delete or leave; Claude Code ignores them).
- All idempotency / preserve-existing-content semantics from v1.0.4
  are unchanged — just the destination path is fixed.

### Migration from v1.0.4

Re-run `harness init` in any project where you ran v1.0.4's init:

```
cd your-project
harness init   # now writes the correct path
```

Optionally remove the stale file (does no harm if you don't):

```
rm -f .claude/CLAUDE.md
```

## v1.0.4 — 2026-04-26

UX critical fix. v1.0.3 required PM to manually run `harness start "..."`
in the shell — but a non-technical PM hits zsh quoting issues (`[...]`
triggers glob, missing quotes split the description into multiple words,
etc.). v1.0.4 closes that gap.

### What's new

- **`harness init`** now also writes `.claude/CLAUDE.md` containing the
  auto-start protocol. Claude Code reads this file on session start.
- **PM no longer types `harness start`**. Just open the project, run
  `claude`, describe the task in chat — Claude reads the protocol,
  extracts the description, and runs `harness start "..."` itself.
- Existing `.claude/CLAUDE.md` (user-written) is preserved; the guide
  is appended with a marker comment for idempotency.

### Why this earned a hotfix (vs the 5 issues left in KNOWN_ISSUES)

PM hit this in real first use within minutes of v1.0.3 install:
- Tried `harness start [给星阙做个官网...]` → zsh bad pattern error
- Re-tried with quotes, succeeded, but then `claude` couldn't see the
  task because the SPEC prompt didn't tell it to read pipeline.json's
  description field

The 5 KNOWN_ISSUES are theoretical; this one had a concrete user-pain
event with screenshots. Per v1.0 manifesto: real PM-impact triggers a
hotfix, theoretical concerns wait.

### Migration

Existing v1.0.3 users: re-run `harness init` in your project to get the
new `.claude/CLAUDE.md`. No other changes needed.

## v1.0.3 — 2026-04-26

**The "actually self-improving" release.** v1.0 had Hermes as a single
hand-curated checklist, hand-edited by humans only. v1.0.3 closes the
loop: PM feedback flows back into Hermes via `harness feedback`, and
each pipeline run produces both self-reflection and PM-feedback
proposals for human review.

### What's new

- **Three-layer Hermes** — implicit-expectation skills now resolve in
  this order, with later layers overriding earlier ones at the
  bullet-name level:
  - **L0 builtin** — `<install>/hermes/implicit_expectations.md`
    (general best practices we ship)
  - **L1 user** — `~/.claude-hh/hermes/implicit_expectations.md`
    (your cross-project preferences; v1.0 path preserved, no migration)
  - **L2 project** — `<project>/.claude-hh/hermes/project.md`
    (this project's specific rules; goes in your project's git)

- **`harness feedback "..."`** — One-line feedback from the PM after
  using the product. Writes to `.harness/inbox.md` instantly, no LLM
  call. Next pipeline-completion processes the inbox.

- **`harness hermes-show`** — Prints the merged L0+L1+L2 list. The
  SPEC-stage prompt now asks Claude to consult this single command
  instead of reading individual files.

- **Two-stage proposals** — `hermes_propose.py` now writes two
  separate files for clarity:
  - `proposed_auto.md` — self-reflection (what AI thinks PM didn't say)
  - `proposed_feedback.md` — distillation from PM's inbox feedback
  - `harness hermes-review` shows each entry tagged `[auto]` /
    `[feedback]` and lets you save to L1 (global) or L2 (project,
    default).

- **Inbox auto-archive** — After processing, `.harness/inbox.md` is
  renamed to `.harness/inbox.archive.<timestamp>.md`. Whether the LLM
  call succeeded or not, the inbox is rotated so subsequent runs don't
  reprocess the same feedback.

### What was deliberately NOT added

True to the v1.0 manifesto — every line of code must earn its keep on
A/B data. We considered and rejected:

- **Hit count / "popular" tags** — would be a revival of the failed
  `skill_extractor` mechanism. Same reason: it relies on AI-generated
  structured output (the AI declaring "I applied skill X"), which is
  exactly what v0.3 proved unreliable.
- **Synchronous LLM call inside `harness feedback`** — adds 5–10s
  latency, requires a fallback path for LLM failure, and makes the
  command less useful when the PM is offline. Direct inbox append is
  faster and simpler.
- **agentskills.io directory format** — opening the door to a 5–10×
  complexity increase for an audience (non-technical PMs) who don't
  publish or import skills. The single-markdown-file format works.
- **Auto-stale tagging** — false positive risk too high; the PM might
  legitimately not touch a category for months and the rule still
  applies on the next run.
- **Cross-user / team sync** — v1.x is for single-PM use. Teams who
  need shared rules can commit `<project>/.claude-hh/hermes/project.md`
  to git and let everyone pull (works automatically with L2).

### Why these specific changes (the data path)

- **Per-project Hermes** came directly from PM feedback: "every project
  is different — electronics rules don't apply to my SaaS." A global
  list pollutes context across projects.
- **PM feedback inbox** came from observing that PMs use the product
  after the pipeline finishes and notice things like "the search
  doesn't include the current user." Without a capture point, that
  observation evaporates.
- **Two-stage proposals** came from rejecting AI-generated source tags
  (the `[auto]` / `[feedback]` distinction must be 100% reliable, and
  letting the LLM emit the tag isn't reliable; using two files with
  one source each is).

### Migration from v1.0

Zero migration. v1.0 users:

- Existing global list at `~/.claude-hh/hermes/implicit_expectations.md`
  continues to work unchanged (it's now L1).
- New layers (L0 builtin + L2 project) are additive, not breaking.
- All v1.0 commands (`init`, `start`, `advance`, etc.) behave
  identically.
- New commands (`feedback`, `hermes-show`) are opt-in.

### Code metrics

| Metric | v1.0 | v1.0.3 |
|--------|-----:|-------:|
| Python lines (production code) | 298 | 474 |
| New files | — | `hermes_loader.py` (72) |
| Modified files | — | `hermes_propose.py` rewrite, `pipeline.py` +25, `01_spec.md` +5 |
| Unit tests | 0 | 6 (all pass) |
| Test code | — | 111 lines |
| % of v0.3.4 (8600 lines) | 3.5% | 5.5% |

The +176 lines (+59%) is paid for by:
- A genuinely new feedback channel (PM ↔ tool)
- Per-project rules (the most-requested PM feature since v1.0 launch)
- Reliable source tagging (no AI-emitted tags)

Each new line was justified pre-implementation; the design doc
(`MORNING_REPORT_V103.md` if exists, otherwise the v1.0.3 release notes)
records the decisions and the rejected alternatives.

---

## v1.0 — 2026-04-26 earlier

**The 96% deletion release.** Distilled from v0.3.4 (8600 lines) based
on a two-round A/B benchmark. Only the spec-first stage produced
measurable accuracy lift, so v1.0 ships only that feature plus a
hand-curated Hermes checklist.

See `RELEASE_NOTES.md` and `EXTENDED_DATA.md` for the data behind every
deletion.
