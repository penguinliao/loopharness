# REVIEW 新增 Claude 干净上下文二审（自动化双重验证）

## 背景

PM 一直手动做"双重验证"：开新 Claude Code 对话贴提示词独立审查交付代码。其独特价值 =
**最强工程审查能力（Claude）× 全新上下文（不知道代码怎么写出来的，无自我说服偏误）**。
本任务把它自动化进 REVIEW 阶段，loop 无人值守时也能享受这道质检。

设计红线（G4 的 0/38 采纳率教训，照搬 v1.1.4 救活跨家族审查的约束）：
一轮出结果、只看 diff、看不到的不许编、fail-open 不阻塞主流程。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | 新增 `_fresh_context_review(root)`：调 `claude -p`（干净上下文单次调用），prompt 含 spec + 本期 diff + 与跨家族审查相同的严格 scope 规则；输出末行 PROCEED → 返回通过 | P0 |
| AC2 | claude 输出末行 `FAIL: <原因>` → 返回 (False, msg)，msg 含"判定不通过"和原因文本（"判定不通过"是 cmd_advance 自动回炉的触发关键词，原因会进错题本） | P0 |
| AC3 | fail-open：claude CLI 不存在 / 超时 / 退出码非 0 / 输出无法解析或为空 → 一律放行 (True,"")，不阻塞 pipeline | P0 |
| AC4 | 本期 diff 为空 → 跳过二审且**不调用** claude（没东西可审，省额度） | P0 |
| AC5 | `_check_review` 检查顺序：自审判定 → ruff/mypy → 二审 → 跨家族三审。前面任何一道不过，后面的**不执行**（静态检查能拦的问题不烧 LLM 额度） | P0 |
| AC6 | 修存量 bug：`_cross_family_review` 的 FAIL 消息从"独立审查不通过"改为含"判定不通过"——否则 cmd_advance 关键词匹配不到，FAIL 后卡在 REVIEW 阶段无法自动回炉（REVIEW 阶段 hook 锁代码，卡住=死局） | P0 |
| AC7 | prompts/03_review.md 说明二审机制（advance 时自动发生、FAIL 自动回炉、错题本衔接） | P1 |
| AC8 | README 无人值守章节更新：三个互相不通气的审查者（自审之外：静态检查 + Claude 二审 + DeepSeek 三审） | P1 |

## Affected files

| File | Change |
|------|--------|
| claude_hh/pipeline.py | 新增 `_fresh_context_review`；`_check_review` 插入二审调用；`_cross_family_review` FAIL 消息措辞修复 |
| prompts/03_review.md | 二审机制说明 |
| README.md | 无人值守章节更新 |

## Out of scope

- 不做多轮二审状态机（G4 教训）
- 不给二审加独立配置开关（claude CLI 缺失即自然跳过；本工具本来就要求 Claude Code 环境）
- 不改 DeepSeek 跨家族审查的调用方式
- 二审用什么模型由用户的 claude CLI 默认配置决定，不硬编码 model 参数

## 测试策略

白盒单元/集成测试（monkeypatch subprocess 与内部函数，tempfile 隔离假项目）。
黑盒浊龙不适用：被测对象是 pipeline 内部审查链，无 UI；测试直接驱动真实函数已覆盖
用户可见行为（advance 输出与回炉行为）。
