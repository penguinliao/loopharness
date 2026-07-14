# Show HN: LoopHarness – carry project memory across coding agents and verify “done”

Repo: https://github.com/penguinliao/loopharness

I am a non-technical product manager who uses coding agents to build real products. My recurring problem was not code generation. It was losing project context when switching agents, then accepting “done” without knowing what had actually been checked.

LoopHarness is a local, standard-library Python CLI for that gap.

It keeps a small project-owned memory, locks a Delivery Contract, compiles the same minimal Markdown context for Claude, Codex, Kimi, or GLM, and records artifact receipts. A receipt created by the CLI is explicitly **declared**: it records the artifact path, hash, outcome, and whether the artifact is still current. It does not prove that the content is true and cannot promote itself to production-ready.

The shortest honest demo is:

```bash
harness memory-init
mkdir -p docs
printf '# Release brief\nKeep the cross-agent handoff reproducible.\n' > docs/brief.md
harness contract "Ship a reliable demo" --ac "Help runs" --allow docs/brief.md
harness context "Prepare release" --agent codex --include docs/brief.md
printf '1 passed\n' > functional.txt
harness evidence functional functional.txt --outcome passed
harness readiness
```

If `functional.txt` changes, the old receipt becomes stale. The readiness report stays `Contract-only` until a trusted host supplies independently verified evidence through the library API.

What it does not do:

- It does not log in to or control Claude, Codex, Kimi, or GLM.
- It does not import full chat histories or make four vendors share native hooks.
- It is not a security sandbox or a substitute for real production acceptance.

The older project was centered on one agent and a spec-first pipeline. The current LoopHarness keeps that pipeline but adds the portable memory, contract, context, and evidence layer. The implementation has no runtime dependencies; the repository CI covers Python 3.9 and 3.13.

I would especially value feedback on two questions:

1. Is “declared vs. verified” understandable, or is there a simpler mental model?
2. What is the smallest cross-agent handoff you would actually keep in a project?
