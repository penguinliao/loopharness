# SPEC stage

You are now in the **SPEC** stage of LoopHarness.

LoopHarness v1.4 可由 Claude、Codex、Kimi 或 GLM 驱动。若项目已有
`.delivery/contract.json`，只把合同授权的文件编入任务上下文；不得读取 `.env`、
凭据、项目外路径或其他未授权资料。Delivery Contract 的目标和验收标准是本轮
规格的上游约束，不能被模型自行放宽。

## Your only job in this stage

Turn the PM's natural-language request into:

1. **`.harness/spec.md`** — explicit acceptance criteria + affected files
2. **`.harness/test_*.py`** — automated tests written from the spec, NOT from any code

You are not allowed to write code (`*.py` / `*.ts` / `*.tsx` / `*.js` / `*.vue` etc.) in this stage. The hook will physically block it.

## Step 1: Consult Hermes (multi-layer)

**Before writing the spec**, run:

```
harness hermes-show
```

This prints the **merged** Hermes implicit-expectations list:
- L0 builtin (general best practices we ship)
- L1 user-level (your cross-project preferences, if any)
- L2 project-level (this project's specific rules, if any)

Same `**bullet name**` in a more specific layer overrides the less specific one.

**Also check `.harness/inbox.md`** — if it exists, it contains PM feedback from previous pipeline runs that the AI should consider.

For each category that *could* apply to your task, ask: "Did the PM cover this? If not, do I need to assume the safe default?"

## Step 2: Write `.harness/spec.md`

Use this template:

```markdown
# {Task title}

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | When [user does X], then [Y happens] | P0 |
| AC2 | When [edge case A], then [graceful behavior B] | P0 |
| AC3 | When [edge case C], then [graceful behavior D] | P1 |
...

## Affected files

| File | Change |
|------|--------|
| path/to/file.py | What changes |

## Out of scope

- Things this task explicitly will NOT do
- Things the PM mentioned but should be a separate task

## Open questions for PM (only if blocking)

- Question 1 (with your best-guess default)
- Question 2 (with your best-guess default)
```

**Rules for AC**:
- Each AC should be checkable by an automated test or a one-line manual check.
- "Each P0 AC must have at least one corresponding test in test_*.py."
- Be specific. "Validate email" is bad. "Reject email without `@` with 400" is good.
- Cover both happy path and at least one edge/failure case.

## Step 3: Write tests

For each P0 AC, write a test in `.harness/test_*.py` (one file per logical group). Tests can be:

- **Behavioral / integration** (recommended): start the server, send real HTTP, assert response. Use `tempfile` for isolated state.
- **Unit-level**: import the function, call it directly, assert return value.
- **Black-box**: shell out, parse stdout.

Tests must:
- Pass `python3 -m pytest .harness/` once the implementation is correct
- Be independent (each test sets up and tears down its own state)
- Not depend on external services (mock OpenAI, Stripe, real email, etc.)
- Have meaningful failure messages (not just `assert x == y`)

You will not be allowed to modify these tests in IMPLEMENT stage. Write them carefully now.

## Step 3.5: 黑盒测试决策（必须二选一，不允许静默跳过）

spec.md 里必须有一个「测试策略」或「黑盒测试」小节，明确写下其中之一：

- **启用**：任务涉及 UI / 用户旅程 / 端到端体验 → 同时写 `.harness/zhuolong_brief.md`
  （场景要写到最终预期结果，如"用户搜 john → 列表出现 johnny 和 johnson"）。
  TEST 阶段会强制等浊龙黑盒报告，FAIL 自动回炉修。
- **不需要**：写明理由（如"纯后端 CLI/API，测试脚本已直接覆盖用户可见行为"）。

不写这个决策段落 = 你在替 PM 默默放弃一道质检，这不是你的权力。

## Step 4: Advance

Once spec.md and at least one test_*.py file exist, run:

```
python3 -m claude_hh.pipeline advance
```

The advance check verifies:
- spec.md exists with ≥3 P0 acceptance criteria
- At least one `.harness/test_*.py` exists
- Tests have meaningful asserts (not `assert True`)

If these pass, you advance to IMPLEMENT.

## What good looks like

- spec.md is short (1-2 pages), specific, and exhaustive on the things that matter
- Tests are written FROM the spec, not from imagining the code
- Open questions are listed only when the PM-stated brief left a critical ambiguity AND your safe default isn't satisfactory; otherwise just decide and document
- You spent 5-10 minutes here, not 30. SPEC stage is intentional but lightweight.
