# TEST stage

You are now in the **TEST** stage. The pipeline is about to run `.harness/test_*.py` automatically. Your job is just to wait for the result.

## Hard rules

- ❌ You CANNOT modify any file in this stage
- ❌ You CANNOT modify `.harness/test_*.py` (still locked from SPEC)
- This is a non-negotiable judgment by automated tests

## What happens

Run:
```
python3 -m claude_hh.pipeline advance
```

The pipeline will:

1. Discover all `.harness/test_*.py` files
2. Run each with pytest, separately, with a 120-second timeout each
3. Collect exit codes

Result:

- **All exit 0** → pipeline complete. You can stop. ✅
- **Any test fails** → automatic retreat to IMPLEMENT. The retreat counter increments. You'll go back to IMPLEMENT to fix the code (NOT the tests).

## Black-box test (浊龙) — opt-in

If `.harness/zhuolong_brief.md` exists (you wrote it in SPEC because the task involves UI / user journey), the pipeline will require `.harness/zhuolong_report.md` before advancing to `done`.

**Before running advance**, dispatch the 浊龙 agent using the Agent tool:
- subagent_type: `zhuolong`
- model: `opus`
- prompt: include the full contents of `zhuolong_brief.md` + paths to any test accounts / URLs

When 浊龙 finishes, it writes `.harness/zhuolong_report.md`. Then run advance.

If no `zhuolong_brief.md` exists (most backend / API projects), skip this — pipeline goes directly to done after pytest passes.

## Retreat budget

You have **3 retreats**. After 3 retreats from IMPLEMENT → REVIEW → TEST → fail, the pipeline stops and waits for the PM. This prevents runaway loops.

If you're at retreat 3 and still failing:
- Write `.harness/stuck_report.md` explaining why you can't make the test pass
- Stop. The PM will look at the report and decide whether to:
  - Update the spec (if the AC turns out to be wrong)
  - Accept failure for this iteration
  - Give you a different approach

## Why you can't change the tests

The tests were written in SPEC stage from the user's needs, not from your implementation. If they fail, your implementation is wrong, not the tests. Changing tests to fit broken code defeats the whole purpose of this pipeline.

If a test is genuinely buggy, write it in `.harness/test_bug_report.md` for PM review. Do NOT silently change the test.
