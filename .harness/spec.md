# Loop 护栏强化②：LLM 审查调用成本遥测 + 软上限提醒（最小版）

> 来源：loop engineering 四护栏之②「Token/成本预算」——v1.3.0 唯一全缺的一条。
> PM 拍板「最小版」：先加**可见性 + 软提醒**，观察真实花费数据再决定要不要硬熔断
> （遵循「没数据前不写代码 / 便宜对照组先于贵重改造」原则）。**本版绝不硬熔断**。

## 背景

- 单条 pipeline 已有硬边界（retreat≤3、G4 ROUND_LIMIT=20），但**对累计 LLM 审查花费零可见性**。
- 二审（`_fresh_context_review`，claude -p）+ 三审（`_cross_family_review`，DeepSeek）每次 advance 各烧一次；
  retreat 反复时累加，PM 现在完全看不到「这条任务到底调了多少次 LLM 审查」。
- 最小版只解决「看得见」+「超了软提醒」，不动 pipeline 放行逻辑。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | `pipeline._bump_review_calls(root)` 把 pipeline.json 的 `llm_review_calls` 累计 +1 并持久化；连调 2 次 → 计数为 2 | P0 |
| AC2 | 二审/三审**实际调用 LLM 后**才计数；短路跳过（无 diff / claude CLI 不可用）时**不计数** | P0 |
| AC3 | `pipeline._review_budget_warning(count)`：count > `SOFT_REVIEW_BUDGET` 返回非空中文提醒，否则返回空串；该提醒是**软提醒**，**不改变** `_check_review` 的放行结果（不熔断） | P0 |
| AC4 | `harness status` 输出里能看到累计 LLM 审查调用次数（可见性） | P1 |
| AC5 | 提醒/计数文案为中文、对 PM 可读，不泄露内部异常栈或密钥 | P1 |

## Affected files

| File | Change |
|------|--------|
| `claude_hh/pipeline.py` | 新增常量 `SOFT_REVIEW_BUDGET` + helper `_bump_review_calls(root)` / `_review_budget_warning(count)`；`_fresh_context_review` 与 `_cross_family_review` 在**实际 LLM 调用返回后**各 bump 一次并打软提醒；`cmd_status` 增显累计审查调用次数 |

## Out of scope（明确不做）

- **硬熔断**：超额自动转 stuck/degraded —— 本版只观察，等真实数据再议
- G4 antagonist 轮次单独计数 —— G4 已有 ROUND_LIMIT=20 兜底，不重复
- token 数 / 美元成本换算 —— 无真实单价数据，只计「调用次数」不估钱
- 不动 retreat 上限、不动 ① 的错题本/原地打转逻辑

## 测试策略 / 黑盒测试决策

**不需要浊龙黑盒**。纯内部 CLI/状态机计数逻辑，无 UI。
用户可见行为由测试直接覆盖：(1) 单元调 `_bump_review_calls`/`_review_budget_warning` 断言计数与提醒；
(2) monkeypatch `subprocess.run`+`_impl_period_diff` 验「实际调用计数、跳过不计」；
(3) subprocess 调 `harness status` 断言输出含计数。

## Open questions for PM（非阻断，已采用安全默认）

- `SOFT_REVIEW_BUDGET` 默认 **12**（正常一条 standard 任务约 2-8 次审查调用，12 次意味着反复回炉，
  值得提醒 PM 看看是不是需求不清）。这是个常量，事后调一行即可。
