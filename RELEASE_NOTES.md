# Claude H-H v1.0 — Release Notes

**Released**: 2026-04-26
**Lines of code**: 298 Python (down from 8600)
**Status**: Distilled from v0.3.4 based on A/B test data

---

## TL;DR

In v1.0 we deleted 96% of our own code.

A two-round A/B benchmark on 8 real coding tasks showed that **only one feature** in v0.3.4's 8600 lines produced measurable accuracy gains:

> **spec-first**: forcing the AI to write `acceptance criteria` before code. +20pp average coverage on PM-perspective tasks.

Everything else — the 8-dimension scoring engine, micro/standard/full routes, the skill extractor, ruff+mypy+bandit+radon scans, the cooldown timer, the boundary-check edge cases — was zero or negative incremental value.

So we kept spec-first, plus its supporting cast (4 stage gates, retreat budget, two hooks, a Hermes checklist), and deleted the rest.

---

## What changed from v0.3.4 → v1.0

### Removed (≈8000 lines deleted)

- **8-dimension quality scoring engine** — `reward.py` (746 lines). Replaced with `ruff check` + `mypy` (≈30 lines).
- **Three pipeline routes (micro / standard / full)** — confusion machine. v1.0 has one flow.
- **Six hooks → two hooks** — `pre_edit` and `stop_check` only. The other four were guarding against edge cases that don't fire in practice.
- **Skill extractor** — never produced a usable skill in real runs. Replaced with a hand-curated `hermes/implicit_expectations.md`.
- **Cooldown timers** — added in v0.3.1 to fix "blind retry," then patched four times because the granularity was wrong. v1.0 has no cooldowns; the retreat counter caps at 3.
- **Pipeline expiration** — same story.
- **Mutation testing module** — meta-circular validation that confused users.
- **Telemetry** — collected but never looked at.
- **Spec validator** with three-tier LLM fallback — over-engineered. v1.0 uses simple grep for "P0" + file existence.
- **Autofix loop** — only triggered on ruff lint, which Sonnet doesn't typically fail.

### Added

- **`hermes/implicit_expectations.md`** — hand-curated checklist of "things PMs forget to mention" (partial-match search, password hashing, token expiration, anti-enumeration, etc.). The SPEC stage prompt explicitly directs the AI to consult this before writing acceptance criteria. Each entry is grounded in a real failure from past pipelines.
- **`hermes-review` command** — after every completed pipeline, the AI proposes new implicit-expectation entries based on what it had to figure out. The PM reviews them y/n. Approved entries are appended to the global checklist. **The tool gets smarter with use, but a human always gates the accumulation.**

### Kept (the 4% that earned its keep)

- 4-stage state machine: SPEC → IMPLEMENT → REVIEW → TEST
- Hook-enforced cognitive isolation: tests written in SPEC are physically locked from IMPLEMENT
- Retreat-on-failure with budget cap (3 retreats, then stop and ask the human)

---

## A/B test data backing this rewrite

| Task type | v0.3.4 H-H lift | Verdict |
|-----------|----------------|---------|
| Tech-spec briefs (Round 1) | 0pp on every criterion | No value — full spec already implicit in brief |
| PM-style ambiguous briefs (Round 2) | +20pp avg, +40pp on hardest | Real value — comes from spec-first |
| Business-logic invariants (token single-use, etc.) | 0pp | Static analysis can't reach this — needs integration tests, not gates |
| Boilerplate (registration, JWT, CORS) | 0pp | Sonnet already gets these right |

So in v1.0:

- We optimize hard for the +20pp case (spec-first + Hermes checklist)
- We don't try to fight the 0pp cases with more layers of static analysis (we tried; we lost)
- We accept that some failure modes belong outside this tool (integration tests, code review, runtime monitoring)

Full data in `claude-hh-experiments/results/STORY_v2.md` and `STORY.md`.

---

## Migration from v0.3.x

**Short answer**: don't. Start fresh.

```bash
# Optional: archive old project state
mv ~/.harness ~/.harness.v0.3-backup

# Install v1.0
curl -sSL https://raw.githubusercontent.com/penguinliao/claude-hh/v1/install.sh | bash
```

v1.0 deliberately doesn't import old `.harness/` state. The state machines are different shapes; auto-migration would be more code than the entire project. If you have an in-progress v0.3.x pipeline, finish or reset it before installing v1.0.

---

## Honest caveats

1. **Sample size is still small** — 8 tasks total, 3 in PM-perspective format. We're confident about direction, less confident about magnitude.
2. **Tested only with Claude Sonnet.** Haiku-class models might benefit more (they make more avoidable mistakes); GPT/other backends are untested.
3. **Single-file tasks only.** Multi-file refactors might get more or less benefit from spec-first; we don't know.
4. **The Hermes checklist is hand-maintained.** Auto-extraction has been tried and didn't work; PM oversight is in the loop by design, but it's a real cost.
5. **REVIEW stage now does less.** v0.3.4's REVIEW ran scoring across 8 dimensions and the AI's own self-review. v1.0 keeps the self-review (which v2 data showed was the valuable part) and replaces the multi-dim scoring with a thin `ruff + mypy` gate. If you find a class of issue this misses that v0.3.4 caught, please file it.

---

## What this release means for the project

Claude H-H started as a "rails for AI coding" experiment in 2026-Q1 and grew to 8600 lines over six months. v1.0 is the result of being honest with the data: most of those lines were elaborate ways of solving problems Sonnet didn't have. The 4% that fixed real problems is what we're shipping.

If your only response to this release is *"that's it?"* — yes, that's it. The point of v1.0 is that there isn't more.

---

*This release was written by the same PM who built v0.3.4. The decision to delete 96% of his own code was supported by the A/B data, not by an outside reviewer.*
