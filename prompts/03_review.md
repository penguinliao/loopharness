# REVIEW stage

You are now in the **REVIEW** stage. Code is written. Now check it against the spec, line by line.

跨模型审查必须遵守同一份 Delivery Contract，不因 agent 是 Claude、Codex、Kimi
或 GLM 而改变验收口径。模型自述、推测和历史成功 receipt 都不能替代当前 artifact；
发现证据文件已变化或同类最新结果失败时，必须按失败处理。

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

The advance check runs four gates in order (any failure stops the chain — later gates don't run):

1. **Your verdict** — report must end with a real PROCEED
2. **ruff + mypy** — static checks
3. **二审（Claude 干净上下文）** — the pipeline calls `claude -p` with the spec + this period's
   diff. The reviewer is a fresh context that has NO idea how the code was written — no
   self-confirmation bias. It follows the same strict rules as the cross-family review
   (diff-only, no inventing, one round). FAIL → automatic retreat to IMPLEMENT, reason goes
   into `.harness/retreat_log.md`（错题本）. CLI unavailable / timeout → silently skipped.
4. **三审（DeepSeek 跨家族）** — only if `DEEPSEEK_API_KEY` is configured

If your verdict is **FAIL**, you also run advance — and the system will retreat you to IMPLEMENT to fix what you found. This is by design: REVIEW catches your own mistakes before TEST does.

二审/三审报 FAIL 时同样自动回炉——你回到 IMPLEMENT 后先读错题本里它们给出的原因，
针对修。不要试图说服自己"审查者错了"然后原样重交：同样的 diff 会得到同样的 FAIL。

## Why REVIEW exists

In experiments, the AI's own self-review catches more issues than ruff/mypy alone. The act of writing the report forces you to actually look at your code, not just hope it's right. **Don't write the report on autopilot.** A 30-second review report is worse than no review at all.
