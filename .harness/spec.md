# spec：loop 化② — fresh-context 调度 + 外测独立验收(不押注浊龙)

## 背景与目标

实测证据(claude-hh-experiments)：把同一任务挂上 H-H 后，判定结果一致，
但成本 2.4×、轮次 27 vs 6、cache_read 5.8×。根因 = 实现/返工在**单条长会话**里
自我监工，每轮重读全部历史(re-read 税)。loop engineering 共识：进度落文件、
每轮 fresh context、独立验收在单独进程跑。

本任务只做**两个被证据支撑、且可测**的改动，其余划到范围外（见末尾）。

PM 心智模型（本 spec 采用此定义）：
- **内测** = Claude 自己写测试 + 自跑 + 自检（白盒、自报、便宜，拦显眼问题）
- **外测** = 独立 agent 验收（干净上下文，只看 spec + 产物，不信任自报；真关卡）

已知约束：浊龙黑盒 UI 自动化最近一次实测埋雷发现率仅 20%（2026-06-11），
故**外测不得把放行依据押在浊龙上**。

> 注：本任务有意**反转** v1.0.x 协议"不派子 agent"的决定——单长会话正是 2.4× 的根因。
> fresh 子 agent 派工是本次核心取舍，已经 PM 拍板。

## 改动文件

- `claude_hh/pipeline.py`：新增外测独立验收门禁 `_check_external_review`；
  改 `_finish_test` 使放行/回炉只由"独立验收 verdict"决定，浊龙降级为**仅记录的旁证**，
  其 PASS/FAIL 永不影响门禁判定。
- `prompts/02_implement.md`：开工指令改为"派一个 fresh 子 agent 做本轮开发/返工，
  只喂 spec + 错题本 + 相关文件；干完写盘退出；不要在主会话里累积"。
- `prompts/06_external_test.md`（新增）：外测——派独立验收 agent 干净上下文核 AC，
  Web 可加浊龙截图当旁证。
- `CLAUDE.md`：协议补"fresh-context 派工 + 两个 PM checkpoint + 外测独立验收"段。

## 验收标准（P0）

**AC1（P0｜外测放行只看独立验收，不看浊龙）**
`_check_external_review(root)` 读 `.harness/external_review.md` 末段，
严格词边界匹配 PASS/FAIL（过滤 ``` 代码块）。
- external_review = PASS 且 zhuolong_report = FAIL → 返回 ("pass", _)（**浊龙 FAIL 不拦**）
- external_review = FAIL 且 zhuolong_report = PASS → 返回 ("fail", 原因)（**浊龙 PASS 不放水**）
- external_review 缺失/无判定 → 返回 ("wait", _)（不烧 retreat 预算）

**AC2（P0｜浊龙仅旁证、永不改判）**
同一 external_review 判定下，喂入浊龙报告 PASS / FAIL / 缺失三种，
`_check_external_review` 的决策（pass/fail/wait）必须**完全一致**——浊龙对门禁零影响。

**AC3（P0｜外测 fail 自动回炉，预算耗尽诚实交付，永不挂起）**
external_review = FAIL 且 retreat_count < 3 → 回 IMPLEMENT，
原因 append 进 `retreat_log.md`（错题本）。
external_review = FAIL 且 retreat_count ≥ 3 → 带病交付（done + `delivery_report.md` 列遗留），
绝不卡死（stuck）。

**AC4（P0｜错题本每轮 fresh worker 必读 + 有界派工）**
`prompts/02_implement.md` 含明确指令：本轮开工**第一步读 `.harness/retreat_log.md`**，
不重复已失败的改法；且含"派 fresh 子 agent、只喂 spec + 错题本 + 相关文件"的有界派工指令。

**AC5（P0｜独立验收跑在干净上下文、fail-open 不阻塞）**
`prompts/06_external_test.md` 明确：独立验收 agent **只看 spec + 产物**、看不到实现过程；
判定写 `external_review.md`。验收工具不可用 → fail-open（记日志、不阻塞），与二审/三审同策略。

## 测试方案

- **内测（本仓库 .harness/test_loop_eng2.py，pytest）**：
  - 构造临时 .harness 目录，写不同组合的 `external_review.md` / `zhuolong_report.md`，
    调 `_check_external_review`，断言门禁决策（AC1/AC2）；构造 FAIL + 不同 retreat_count
    断言回炉/带病交付（AC3）。
  - 读 `prompts/02_implement.md` / `prompts/06_external_test.md` 断言关键指令存在（AC4/AC5）。
  - 每用例 walltime < 5s；dummy env 注入；禁 bare assert；tempfile 隔离。
- **外测（本任务自身吃狗粮）**：改造后用新流程跑"实现它自己"，
  由独立验收 agent 对照本 spec AC 干净核对，verdict 落 `external_review.md`。
- **归档旧 test**：`test_ac_zhuolong_loop.py` 测的是"浊龙 FAIL→回炉"旧门禁前提，
  与本次"浊龙仅旁证"设计矛盾，归档到 `.harness/archive_loop_eng2/`（覆盖不丢——
  同样的回炉/带病交付/正常 done 三行为由 test_loop_eng2.py 用 external_review 承接）。

## 不在本次范围（活协议边界，下轮再做）

- 把 pipeline 的 REVIEW/TEST 阶段**物理重命名/重排**成内测/外测两段独立 stage——
  本次复用现有 stage 承载语义，不动 stage 枚举，降风险。
- 真机小程序/App 外测自动化（技术上需人工点，非本次架构能解决）。
- 调度员"派 fresh 子 agent"的**硬性 hook 强制**（本次靠 prompt + 协议指令，
  hook 物理拦截留待数据证明必要后再加，避免过度脚手架）。
