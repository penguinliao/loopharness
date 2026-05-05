# Changelog

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
