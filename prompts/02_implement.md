# IMPLEMENT stage

You are now in the **IMPLEMENT** stage. The spec is locked. Your job is to write code that makes every test in `.harness/test_*.py` pass and every AC in `.harness/spec.md` true.

无论当前 agent 是 Claude、Codex、Kimi 还是 GLM，都只使用 Delivery Contract
授权的最小上下文。缺失信息要明确暴露，禁止为了继续执行而读取秘密文件、项目外
资料或扩大权限。实现完成不等于证据成立；只有真实 artifact 才能登记 receipt。

## Hard rules (hook-enforced)

- ❌ You CANNOT modify `.harness/spec.md` (locked from SPEC)
- ❌ You CANNOT modify `.harness/test_*.py` (locked from SPEC)
- ✅ You CAN edit any `.py` / `.ts` / `.tsx` / `.js` / `.vue` etc. in your project's affected files

If you discover the spec is wrong (truly impossible to satisfy, or self-contradictory), do NOT try to work around it. Stop and write a one-line note to `.harness/change_request.md` explaining what you'd need to change. The PM will look. You don't get to soften your own goal.

## 怎么干这一轮（fresh-context 派工，治"单长会话越跑越贵"）

实测：把开发塞进一条不断变长的主会话里自我监工，会让同一个任务多花 2.4× 成本
（27 轮 vs 6 轮、cache_read 5.8×），因为每轮都重读全部历史（re-read 税）。
所以本轮开发/返工**派一个 fresh 子 agent 来做**，而不是在主会话里一路堆下去：

- 派出去的子 agent **只喂三样**：`spec.md` + `retreat_log.md`（错题本）+ 本轮真正相关的文件。
  不要把整段对话历史、无关文件塞给它——上下文是 RAM 不是硬盘，进度已经落在 `.harness/` 文件里。
- 子 agent 干完**把代码写到磁盘 + 回一段 ≤2k token 的小结就退出**，不在主会话累积。
- 返工时同理：开**一个全新的**子 agent（不是接着上一轮那个），它开工第一步读错题本，
  针对上次失败原因改，绝不重复已经失败过的改法。
- 主 Agent 自己是**薄调度员**：读 `pipeline.json` 状态 → 派对应阶段的工人 → 收小结 → advance，
  自己不囤工作记忆。

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
