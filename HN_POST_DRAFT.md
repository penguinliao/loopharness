# Show HN: Claude H-H v1.0 — I deleted 96% of my own code (after my own A/B test killed it)

Three months ago I built **Claude H-H**, a 5-stage pipeline + 8-dimension scoring engine + 6 hooks for Claude Code. ~8600 lines. The pitch was "turn 50% accuracy into 80%+."

This week I finally A/B-tested it. Two rounds, 8 tasks, real money (well, real Max-account quota). The first round said the tool was worthless. I redesigned the experiment to give it a fair shot. The second round said the tool was worth 1 specific feature out of ~30.

**v1.0 ships only that 1 feature.** 298 lines of Python. Same headline benefit on the cases where the benefit was real.

## What survived the cut

Spec-first stage gating: the AI must write `.harness/spec.md` (acceptance criteria) and `.harness/test_*.py` (tests) **before** it can edit code. Hooks physically lock spec/tests during IMPLEMENT and lock code during SPEC.

**Why this single feature is worth keeping**: in the experiment, vanilla Sonnet on a "make a search feature" task wrote `WHERE username = ?` (exact match) and shipped it. Same task with H-H, the SPEC stage forced the AI to enumerate "searching 'john' should match johnny + johnson" as an acceptance criterion *before* writing SQL. It then wrote `WHERE username LIKE ?`.

That's a +40pp coverage swing on one task. Across 3 PM-style tasks: +20pp average.

## What got deleted

- **8-dimension reward engine** (746 lines) — replaced with `ruff check` + `mypy` (~30 lines). The fancy scoring caught nothing the simple tools missed.
- **Three pipeline routes** (micro/standard/full) — confusion machine. v1.0 has one flow.
- **Skill auto-extractor** — wired to "learn from retreats." Never produced a usable skill in a real run.
- **Cooldown timers** — patched four times, still wrong.
- **Mutation testing harness** — meta-circular validation; users couldn't tell what it was for.
- **Telemetry** — collected but never read.
- **Spec validator with 3-tier LLM fallback** — over-engineered. Real check is `grep "P0" >= 3 + ls test_*.py`.
- 4 of 6 hooks — `post_edit`, `pre_commit`, `post_agent`, `stop_check` were guarding edge cases that don't fire in practice.

Total: ~8000 lines deleted.

## What we added

A hand-curated checklist of **"things PMs forget to mention"** (`hermes/implicit_expectations.md`). Categories like "Search/list endpoints" with bullets like "Default to partial match," "Exclude password_hash from response," "Result limit." Each entry footnoted to the real failed pipeline that motivated it.

The SPEC stage prompt explicitly directs the AI to consult this checklist. After every completed pipeline, the AI proposes new entries; the human approves or rejects them via `harness hermes-review`. **The tool gets smarter with use, but accumulation is gated on a human looking at the proposal.**

(We tried fully automated learning via `skill_extractor.py` in v0.3. It produced nothing usable. v1.0's compromise — AI proposes, human approves — is the lesson learned from that failure.)

## Honest caveats

- Sample size is 8 tasks. Direction is clear; magnitude is noisy.
- Tested only with Sonnet. Haiku might benefit more (or less); GPT untested.
- Single-file tasks only. Multi-file refactors not measured.
- One pass of v1.0 against task_07 reproduced the +40pp coverage. The full re-validation across 8 tasks is in progress.

## The one thing the data killed that I didn't want to admit

The 8-dimension scoring engine was the project's centerpiece. Six months of work. ruff S-rules + bandit + mypy + radon + custom regex + secret detection, weighted from a 367-bug analysis. **It contributed zero pp of accuracy in the experiment.** Sonnet doesn't make the mistakes that a static analyzer can catch. The mistakes Sonnet does make ("token should be single-use") aren't reachable by static analysis.

I had been telling people the scoring engine was the moat. The data said it was decoration. v1.0 deleted it.

## Reproduce

- Tool: https://github.com/penguinliao/claude-hh (v1.0 branch)
- Experiment: https://github.com/penguinliao/claude-hh-experiments
- Story: results/STORY.md (round 1) + results/STORY_v2.md (round 2)

Independent runs, especially with weaker models or multi-file tasks, would help calibrate the conclusions.

## Why post this

Posting a tool that just shipped its own deletion notice is awkward. But the alternative was to keep promoting "v0.3 with 8000 lines of features that don't help." That's worse. If the data ever changes, I'll do this again.
