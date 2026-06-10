# loop 化升级：retreat 错题本 + 浊龙回炉带病交付 + 无人值守模式

## 背景

对照 2026 loop 理念（官方 /loop 自驱异步 agent + Ralph Wiggum "进度沉淀在文件不在上下文"）：
v1.1.4 的 pipeline 已具备文件化状态机和 integrity gates，但有三个缺口：

1. retreat 原因只 print 到屏幕，不落盘 → 干净上下文的下一轮看不到上次失败教训（盲改）
2. 浊龙黑盒报 FAIL 只打印提示、原地干等 → 无人值守 loop 下死等到天亮
3. 黑盒默认静默跳过、独立审查未配置时无感 → PM 以为有质检实际没有

PM 拍板的设计：浊龙 FAIL 自动回炉修（≤3 轮）；修不过不挂起，**带病交付**（done +
诚实的交付报告），上不上线由 PM 看报告决定。永不卡死，最终必有交付物。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | `_retreat` 每次触发时，把（UTC 时间戳 + 第 N 次 + 完整原因）**追加**写入 `.harness/retreat_log.md`；连续 2 次 retreat 后两条原因都在文件里（append-only，不覆盖） | P0 |
| AC2 | `prompts/02_implement.md` 明确指示：IMPLEMENT 开始前先读 `.harness/retreat_log.md`（如存在），针对上几轮失败原因修，不要盲改 | P0 |
| AC3 | TEST 阶段浊龙报 FAIL 且 retreat_count < 3 时，`_finish_test` 自动调用 `_retreat` 回 IMPLEMENT（stage 变 implement、retreat_count +1），不再原地干等 | P0 |
| AC4 | 浊龙报 FAIL 且 retreat_count >= 3 时：**带病交付** — stage 置 `done`，写 `.harness/delivery_report.md`（必须含"遗留问题"字样 + 浊龙失败原因），打印诚实提示；不进 stuck、不挂起 | P0 |
| AC5 | 浊龙报 PASS（或无 brief 跳过）时：正常 done，**不**产生 delivery_report.md | P0 |
| AC6 | `harness start` 时若 DEEPSEEK_API_KEY 未配置（环境变量和项目 .env 都没有），打印一行提醒"跨家族独立审查未启用"；已配置则不打印 | P0 |
| AC7 | `harness start` 启动新任务时，清掉上个任务残留的 `retreat_log.md` 和 `delivery_report.md`（防止上个任务的错题本污染新任务） | P0 |
| AC8 | `prompts/01_spec.md` 新增黑盒测试强制决策：spec.md 必须写"黑盒测试"段落——要么启用（SPEC 阶段写 zhuolong_brief.md），要么写明"不需要 + 理由"；不允许静默跳过 | P1 |
| AC9 | README.md 新增"无人值守模式"章节（教 PM 用 /loop 一句话驱动 pipeline 到交付，含 done/stuck/带病交付三种结局说明）+ "Hermes 晨报"定时消化 inbox 的模板 | P1 |

## Affected files

| File | Change |
|------|--------|
| claude_hh/pipeline.py | `_retreat` 写 retreat_log.md；`_finish_test` 浊龙 FAIL 分支接回炉/带病交付；`cmd_start` 加 key 提醒 + 清残留文件 |
| prompts/02_implement.md | 加"先读错题本"指示 |
| prompts/01_spec.md | 加黑盒测试强制决策要求 |
| prompts/04_test.md | 更新浊龙 FAIL 的处理说明（自动回炉/带病交付） |
| README.md | 无人值守模式 + Hermes 晨报章节 |

## Out of scope

- 不自己写 scheduler/daemon/watch 进程（用 Claude Code 原生 /loop 和 cron）
- 不改 retreat 3 次上限（防 AI 无限瞎折腾的刹车保留）
- 测试脚本（test_*.py）失败 3 次仍进 stuck 不带病交付——自家 AC 测试不过的代码不能交付；带病交付仅限黑盒（浊龙）失败
- 不复活 G4 状态机
- _check_spec 不对黑盒段落做硬拦截（prompt 层约束，避免破坏存量项目兼容）

## 测试策略

- 全部白盒单元/集成测试（tempfile 隔离的假项目 + 直调 pipeline 函数 + subprocess 跑真 CLI）
- 本任务是 CLI 工具自身改造，无 UI，黑盒浊龙不适用。理由：被测对象就是 pipeline 状态机本身，
  测试脚本直接驱动真实 CLI 入口（subprocess python -m claude_hh.pipeline）已覆盖用户可见行为
