# Review report — 改进③：REVIEW 门禁 (N-1) 共识 + 完美主义熔断

## AC coverage

| AC | Where in code | Covered? | Notes |
|----|---------------|----------|-------|
| AC1 两过放行 | `pipeline.py:563-565` | ✅ | 二审过 + 三审过 → 清 dissent、return True |
| AC2 首次单反对回炉 | `pipeline.py:571-573`（三审首次）/ `:559-561`（二审 FAIL 短路） | ✅ | 三审首次反对(无相似上轮)→记 dissent、return False；二审 FAIL 直接短路回炉 |
| AC3 连续相似反对熔断 | `pipeline.py:566-570` | ✅ | 二审过 + 三审 `_reason_similar(本轮,上轮)` → 记 `review_advisory.md`、放行 |
| AC4 两反对始终回炉 | `pipeline.py:559-561` | ✅ | 二审 FAIL 即短路 return False（永不放行）；测试 both-fail 经二审拦下 |
| AC5 advisory 中文不泄露 | `_record_review_advisory:520` | ✅ | 中文标签(二审/三審)+反对原文；测试断言无 `Traceback` |

## 设计说明（为什么不对称）

最终采用**不对称熔断**而非纯 (N-1)："二审(Claude 干净上下文) FAIL 仍短路回炉"（同源清净审查反对是强信号，照旧），
只对**三审(DeepSeek 跨家族)的连续相似反对**熔断——三审才是实测会"移动球门"的那个。
好处：(1) 保住质量(二审是硬门)；(2) 省额度(二审过才跑三审，不破坏旧 short-circuit 行为)；
(3) 不碰倒 legacy `test_ac_fresh_review.py::test_ac5`(它断言二审 FAIL 短路三审)；(4) 精准只治观察到的失败模式。

## Implicit-expectation review (Hermes)

纯内部判定逻辑。**用户可见文案中文**✅；**不泄露内部**✅(advisory 只记反对文本，无栈)；
**状态读写**✅(`_update_review_dissent` 用 `_load`/`_save`，`_save` 含 ② 的计数钳位不受影响)。

## Self-critique

1. **最丑的一处？** 不对称——二审无熔断、只有三审有。理论上若二审也开始移动球门会退化回死循环。
   但二审是同源清净 diff 审查，实测不是 goalpost-mover；且 retreat≤3 + stuck 是兜底。属有意识权衡。
2. **真实生产最可能失败模式？** `last_review_dissent` 存在 pipeline.json，`_update_review_dissent` 读改写，
   与 ② 的 `_save` 计数钳位共存——已确认钳位只动 `llm_review_calls` 键，不影响 `last_review_dissent`。
   全过/熔断后都 reset streak，避免跨任务残留误判（新任务 start 也会重建 state）。
3. **scope creep？** 无。只改 `_check_review` + 3 个 helper，没碰二审/三审各自判定、没碰 G4、没加第三个审查器。

## Verdict

3 个 P0(AC1/AC2/AC3)全覆盖，33/33 测试绿(含恢复的 legacy test_ac5)，ruff 全过。

PROCEED
