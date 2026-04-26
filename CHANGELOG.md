# Changelog

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
