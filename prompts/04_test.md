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

浊龙报告的三种结果（pipeline 自动处理，你只要照着继续）：

- **PASS** → done ✅
- **FAIL 且回炉预算还有**（retreat_count < 3）→ 自动 retreat 回 IMPLEMENT。
  失败原因已写进 `.harness/retreat_log.md`（错题本），回去先读它再修。
- **FAIL 且预算耗尽**（retreat_count >= 3）→ **带病交付**：pipeline 照样标记 done，
  但生成 `.harness/delivery_report.md` 诚实列出遗留问题。你必须把这份报告的内容
  告诉 PM——上不上线是 PM 的决定，不是你的。**绝不允许**只说"做完了"而不提遗留问题。

If no `zhuolong_brief.md` exists (most backend / API projects), skip this — pipeline goes directly to done after pytest passes.

## Retreat budget

You have **3 retreats**. After 3 retreats from IMPLEMENT → REVIEW → TEST → fail, the pipeline stops and waits for the PM. This prevents runaway loops.

例外：黑盒（浊龙）失败耗尽预算时不进 stuck，而是带病交付（见上）——因为自动测试
已全过，交付物本身可用，只是有黑盒遗留项要 PM 拍板。自家 AC 测试不过的代码永远
不会带病交付。

If you're at retreat 3 and still failing:
- Write `.harness/stuck_report.md` explaining why you can't make the test pass
- Stop. The PM will look at the report and decide whether to:
  - Update the spec (if the AC turns out to be wrong)
  - Accept failure for this iteration
  - Give you a different approach

## Why you can't change the tests

The tests were written in SPEC stage from the user's needs, not from your implementation. If they fail, your implementation is wrong, not the tests. Changing tests to fit broken code defeats the whole purpose of this pipeline.

If a test is genuinely buggy, write it in `.harness/test_bug_report.md` for PM review. Do NOT silently change the test.
