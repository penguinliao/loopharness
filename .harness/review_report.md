# Review report — Loop 护栏强化②（成本遥测最小版）

## AC coverage

| AC | Where in code | Covered? | Notes |
|----|---------------|----------|-------|
| AC1 累计计数持久化 | `pipeline.py` `_bump_review_calls` + `_save` 钳位 | ✅ | 读 pipeline.json → `llm_review_calls`+1 → `_save`；连调 2 次 = 2。**修了真 bug**：retreat 用旧 state `_save` 会把计数清零，`_save` 加单调钳位（取磁盘/内存较大值）保住计数，已专项验证 retreat 后计数仍为 2 |
| AC2 实际调用才计数 | 二审/三审计数点 | ✅ | **采纳三审意见收紧**：计数点从"网络调用返回后"后移到"确认拿到有效响应后"（claude returncode≠0 / DeepSeek 返回结构异常都不计数），更严格符合 AC2"实际调用 LLM 后才计数"。无 diff / CLI 不可用 / 无 API key 短路均不计数 |
| AC3 软提醒不熔断 | `pipeline.py:352` `_review_budget_warning` | ✅ | >12 返回中文提醒，≤12 返回 ""；调用处只 `print`，不改 `_check_review` 的 (ok,msg) 返回 → 不影响放行 |
| AC4 status 可见 | `pipeline.py:900-902` `cmd_status` | ✅ | calls>0 时打印「已调用 LLM 审查：N 次」+ 超额提醒 |
| AC5 中文/不泄露 | 提醒/计数全中文 | ✅ | 只回显次数，无异常栈/密钥；测试断言无 `Traceback` |

## Implicit-expectation review (Hermes)

纯内部计数逻辑。相关命中：**用户可见文案中文**✅（提醒/status 全中文）；**不泄露内部**✅（只显次数）；
**资源关闭**：`_bump_review_calls` 用 `json.loads(pj.read_text())` + `_save`，无句柄泄漏。

## Self-critique

1. **最丑的一处？**
   计数粒度是「审查调用次数」而非真实 token/美元——因为没有稳定单价数据（DeepSeek/claude CLI 价目会变）。
   这是有意识的最小版选择（PM 明确要"先可见、观察数据再决定硬卡"），不是偷懒。次数对"反复回炉烧钱"
   这个主要场景已是足够的代理指标。

2. **真实生产最可能的失败模式？**
   原本 retreat 用旧 state `_save` 会把 `_bump` 写盘的计数覆盖清零（dogfood 时实测命中：retreat 后计数变
   None），多次回炉场景下计数反复归零、正好废掉"追踪反复烧钱"的核心用途。已用 `_save` 单调钳位修复
   （取磁盘/内存较大值，仅此键）。残余风险：真并发 advance 仍可能丢一次，但 harness 单 PM 顺序模型无并发，
   可接受。

3. **scope creep？**
   无。只改了 spec 列的 1 个文件（pipeline.py），只加计数+提醒+status 显示。**没做硬熔断**
   （明确 out of scope）、没碰 G4 轮次、没估美元成本、没动 ① 的逻辑。

## Verdict

3 个 P0（AC1/AC2/AC3）全覆盖，29/29 测试绿，ruff 全过，软提醒确认不改放行结果（不熔断）。

PROCEED
