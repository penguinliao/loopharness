# Claude H-H v1.0

> 300 lines that fix the one thing Claude Code gets wrong on ambiguous PM briefs.

## Why

We ran a 60-task A/B experiment across 3 projects. The results were blunt:

- **Spec-first pipeline: +20pp average coverage** on PM-perspective tasks
- 8-dimension scoring engine, 6 hooks, micro/standard/full routing: **0pp lift** over baseline

Claude H-H v1.0 is the distilled version. We kept what worked. We removed everything else.

> This is v1.0 distilled from v0.3.4 (8600 lines). 95% of the old code was static analysis
> that didn't catch what Sonnet actually misses. We removed it.

Full experiment data: [claude-hh-experiments](https://github.com/penguinliao/claude-hh-experiments)

## Install

```bash
git clone https://github.com/penguinliao/claude-hh
cd claude-hh
bash install.sh
```

## Workflow

```
SPEC → IMPLEMENT → REVIEW → TEST → DONE
              ↑_________↓  (auto-retreat on failure, max 3x)
```

| Stage | You do | Gate to advance |
|-------|--------|-----------------|
| SPEC | Write `.harness/spec.md` (≥3 P0 ACs) + `.harness/test_*.py` | spec.md + P0s + tests present |
| IMPLEMENT | Edit code files | any .py modified after stage start |
| REVIEW | AI writes `.harness/review_report.md` | report has PROCEED + ruff/mypy pass |
| TEST | harness runs test_*.py | all exit 0 |

## Usage (PM perspective)

```bash
cd my-project
harness init                          # one-time: installs hooks into .claude/settings.json
harness start "Add user auth"         # → prints SPEC prompt
# write .harness/spec.md + .harness/test_auth.py

harness advance                       # → IMPLEMENT (AI edits code)
harness advance                       # → REVIEW (AI writes review_report.md)
harness advance                       # → TEST → DONE 🎉

harness status                        # check current stage at any time
harness hermes-review                 # review AI-proposed implicit expectations
```

## Hermes

After every completed pipeline, Claude H-H prompts the AI:
*"What implicit expectations did the PM not state, but you had to consider?"*

You approve or reject each suggestion. Approved items accumulate in
`~/.claude-hh/hermes/implicit_expectations.md` — a growing list that
gets injected into every future SPEC prompt. The tool gets smarter with use.

## What's not in v1.0

- Multiple pipeline routes (micro/standard/full) — one flow, zero confusion
- 8-dimension quality scoring — just ruff + mypy
- Skill extractor, telemetry, mutation tests — scope creep removed
- Cooldown timers and pipeline expiry — trust the gates, not the clocks

## License

MIT — [penguinliao](https://github.com/penguinliao)
