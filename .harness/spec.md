# 改进③：REVIEW 门禁放宽到 (N-1) 共识 + 完美主义熔断

> 来源：本次 dogfood 实证 + memory `feedback_consensus_threshold_for_perfectionism`。
> harness REVIEW 门禁 `_check_review` 要求二审(Claude 干净上下文)+三審(DeepSeek)**全数通过**，
> 违反用户"≥(N-1) 共识即 PASS"原则——改进②时三審在 AC2 上**移动球门**连续反对，陷死循环。

## 设计：完美主义熔断（不是"1 票放行"）

保持**默认严格**（两审查都过才放行），只熔断"移动球门"死循环：
- 首次出现的反对（新问题）**仍然回炉修** → 保住质量，不放水
- 但某一审查**连续 2 轮反对同一个问题**（`_reason_similar` 判定相似）而另一审查已通过
  → 判定为完美主义/移动球门 → **接受放行 + 把该反对记为 advisory**（不阻断）

为什么不用"≥1 票就放行"：只有 2 个审查器时，那等于"1 个通过就盖过 1 个反对"，会放真 bug 过。
熔断只针对**重复同一反对**的死循环，首次新反对照常拦。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | 两个审查都 PROCEED → `_check_review` 放行（行为不变） | P0 |
| AC2 | 恰好一个审查反对，且与该审查**上一轮反对不相似/无上一轮**（首次新问题）→ 仍 FAIL 回炉（保质量，不放水） | P0 |
| AC3 | 恰好一个审查**连续 2 轮反对同一问题**（`_reason_similar` 相似）+ 另一审查通过 → 放行，且把该反对写入 `.harness/review_advisory.md`（不阻断） | P0 |
| AC4 | 两个审查都反对 → **始终 FAIL** 回炉（永不放行） | P1 |
| AC5 | advisory 记录中文可读、不泄露内部异常栈（无 `Traceback`） | P1 |

## Affected files

| File | Change |
|------|--------|
| `claude_hh/pipeline.py` | `_check_review` 改为：两过→放行；都反对→回炉；恰一反对→查 `_reason_similar(本轮, 上轮该审查反对)`，相似则熔断放行+记 advisory，否则记下本轮反对并回炉。新增 helper `_record_review_advisory(root, who, msg)` 写 `.harness/review_advisory.md`；state 增 `last_review_dissent={"fresh":..,"cross":..}`，全过时清空 |

## Out of scope（明确不做）

- 不改二审 `_fresh_context_review` / 三審 `_cross_family_review` **各自**的判定逻辑
- 不动 G4 antagonist（它另有 SAME_ISSUE_LIMIT 机制）
- 不引入第三个审查器（保持 2 审查 + 熔断，不加模型依赖）
- 不改 ①错题本/原地打转、②成本遥测的逻辑

## 测试策略 / 黑盒测试决策

**不需要浊龙黑盒**。纯内部判定逻辑、无 UI。
测试 monkeypatch `_fresh_context_review`/`_cross_family_review`/`_ruff_mypy` 返回受控值 + 造 review_report.md(PROCEED)，
直接调 `_check_review(root)` 断言四种组合（两过/首次单反对/连续相似单反对/都反对）的放行与 advisory 落盘。

## Open questions for PM（非阻断，已采用安全默认）

- "连续几轮相似反对算移动球门"默认 **2**（与①原地打转同口径，loop engineering 护栏③"两轮无变化即退出"）。
