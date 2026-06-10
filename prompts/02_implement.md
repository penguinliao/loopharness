# IMPLEMENT stage

You are now in the **IMPLEMENT** stage. The spec is locked. Your job is to write code that makes every test in `.harness/test_*.py` pass and every AC in `.harness/spec.md` true.

## Hard rules (hook-enforced)

- ❌ You CANNOT modify `.harness/spec.md` (locked from SPEC)
- ❌ You CANNOT modify `.harness/test_*.py` (locked from SPEC)
- ✅ You CAN edit any `.py` / `.ts` / `.tsx` / `.js` / `.vue` etc. in your project's affected files

If you discover the spec is wrong (truly impossible to satisfy, or self-contradictory), do NOT try to work around it. Stop and write a one-line note to `.harness/change_request.md` explaining what you'd need to change. The PM will look. You don't get to soften your own goal.

## What to do

0. **If `.harness/retreat_log.md` exists, read it FIRST.** 这是错题本——上几轮没通过的
   原因都记在里面（你可能是干净上下文，对之前的失败毫无记忆）。针对原因修，不要盲改，
   不要重复上一轮已经失败过的改法。
1. Re-read `.harness/spec.md` once. Note each P0 AC.
2. Open `.harness/test_*.py` and skim what's tested. Run them once now to see them fail (they should — you haven't implemented anything yet):
   ```
   python3 -m pytest .harness/ -x
   ```
3. Implement. Hit each P0 AC. Don't add features the spec doesn't ask for.
4. Run tests after each significant change. Stop the moment all P0 tests pass.
5. Run `ruff check` and `mypy` on your changes; fix obvious issues. (REVIEW stage will scan again.)

## What "done" looks like in this stage

- All `.harness/test_*.py` exit 0 when run with pytest
- Code compiles + imports cleanly (no syntax errors, no undefined names)
- ruff check has no errors (warnings OK)

## When you think you're done

Run:
```
python3 -m claude_hh.pipeline advance
```

This will move you to REVIEW. If something's wrong (tests failing, syntax errors), advance will refuse and tell you what's wrong.
