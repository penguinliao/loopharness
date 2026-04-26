# REVIEW stage

You are now in the **REVIEW** stage. Code is written. Now check it against the spec, line by line.

## Hard rules (hook-enforced)

- ❌ You CANNOT modify any file in this stage (no spec, no tests, no code)
- This stage is read-only. It exists so you can think before TEST tries to validate.

## What to do

Open `.harness/spec.md` and `.harness/test_*.py`. Now open the code you wrote.

Write `.harness/review_report.md` answering each of these:

```markdown
# Review report

## AC coverage

| AC | Where in code | Covered? | Notes |
|----|---------------|----------|-------|
| AC1 | path/to/file.py:42 | ✅ / ❌ | If ❌, why |
| AC2 | ... | ... | ... |

## Implicit-expectation review (Hermes)

For each Hermes category that applied to your task (see SPEC stage):
- [Category]: covered? where? if not, was it intentional?

## Self-critique

Three honest questions, three honest answers:
1. **What's the single ugliest thing in my code?** (Don't say "nothing." There's always one.)
2. **What's the most likely failure mode under real production traffic?**
3. **Is there anything in my code that the spec doesn't justify?** (Scope creep check.)

## Verdict

- All P0 ACs covered + implementation is reasonable: PROCEED
- Something is off: FAIL — note exactly what
```

## After writing the report

If your verdict is **PROCEED**, run:
```
python3 -m claude_hh.pipeline advance
```

The advance check will run `ruff check` and `mypy` automatically. If those fail, advance refuses and you go back to IMPLEMENT (retreat).

If your verdict is **FAIL**, you also run advance — and the system will retreat you to IMPLEMENT to fix what you found. This is by design: REVIEW catches your own mistakes before TEST does.

## Why REVIEW exists

In experiments, the AI's own self-review catches more issues than ruff/mypy alone. The act of writing the report forces you to actually look at your code, not just hope it's right. **Don't write the report on autopilot.** A 30-second review report is worse than no review at all.
