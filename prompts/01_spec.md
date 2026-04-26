# SPEC stage

You are now in the **SPEC** stage of Claude H-H v1.0.

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
