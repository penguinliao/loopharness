# Review Report — loop 化升级（v1.2.0）

## 逐 AC 对照

- AC1 错题本落盘：`_append_retreat_log` 在 `_retreat` 计数后立即调用，**先于** n>3 分支，
  所以普通回炉和最终进 stuck 的那次都会落盘。append 模式不覆盖。✓
- AC2：prompts/02_implement.md 新增 step 0，明确"你可能是干净上下文"场景。✓
- AC3/AC4/AC5：`_check_zhuolong` 改三态（pass/wait/fail）。wait（报告缺失/无判定）留在 TEST
  等报告——这是"还没考"不是"考砸了"，不烧 retreat 预算；fail 且预算未耗尽 → `_retreat`；
  fail 且 retreat_count>=3 → `_degraded_delivery`（done + delivery_report.md）。✓
- AC6：`cmd_start` 用与 `_cross_family_review` 完全相同的 `load_env` 加载链（项目 .env +
  全局 ~/.harness/.env）后查 key，保证提示与真实启用状态一致，不会误报。✓
- AC7：清残留在"确认是新任务"之后、`_save` 之前执行，进行中任务被拒绝时不会误删。✓
- AC8/AC9：prompts/01_spec.md Step 3.5 黑盒强制决策；README 无人值守模式（三种结局表）
  + Hermes 晨报。✓

## 自审发现并处理的问题

1. **AC6 测试非密闭**（实现正确，测试漏了全局 ~/.harness/.env 这个变量）→ 按协议走
   change_request.md 留痕，修测试为 HOME 隔离，断言未放松。详见 CR-1。
2. **pre_edit hook 防御过度**：`startswith("test_")` 连协议要求的 test_bug_report.md
   都拦。修为 `and name.endswith(".py")`，与报错文案语义一致。已确认 `_run_tests` 只
   glob `test_*.py`，放行 .md 不会让任何门禁读到假测试。详见 CR-2。
3. **repo 缺自己的 ruff 基线**：不配置则向上继承外层仓库严格规则，REVIEW 门禁在自家
   代码上必挂（95 个存量风格错）。补 [tool.ruff] 匹配既有压缩风格；我本次新增的代码
   在严格规则下也是 0 错误。版本号 1.1.3（已落后于 CHANGELOG）对齐为 1.2.0。

## 风险检查

- 带病交付只可能由黑盒（浊龙）失败触发；自家 AC 测试失败耗尽预算仍走 stuck——
  `_finish_test` 中 `_run_tests` 失败直接 `_retreat`，与浊龙分支互斥，无绕过路径。
- delivery_report.md / retreat_log.md 内容来自测试失败摘要与浊龙报告，无密钥类敏感信息。
- `cmd_start` 的 key 提示 fail-open（load_env 异常只跳过提示），不会阻塞开工。
- 测试验证：12/12 通过；ruff All checks passed。

PROCEED
