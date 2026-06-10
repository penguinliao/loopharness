# Review Report — Claude 干净上下文二审（自动化双重验证）

## AC coverage

| AC | Where | Covered? |
|----|-------|----------|
| AC1 PROCEED 通过 | pipeline.py `_fresh_context_review`（末行词匹配与三审同款） | ✅ test_ac1 |
| AC2 FAIL→"判定不通过"+原因 | 同上，f"二审判定不通过：{reason}" | ✅ test_ac2 |
| AC3 fail-open（CLI 缺失/超时/非0/无法解析/空输出） | try/except + returncode + 解析兜底，5 种情况单测 | ✅ test_ac3 |
| AC4 空 diff 跳过不调 claude | 函数开头先查 `_impl_period_diff` | ✅ test_ac4 |
| AC5 链顺序 自审→静态→二审→三审 + 短路 | `_check_review` 顺序插入，3 种短路场景单测 | ✅ test_ac5 |
| AC6 跨家族 FAIL 消息含"判定不通过" | 措辞修复 + 注释钉死关键词 | ✅ test_ac6 |
| AC7/AC8 文档 | prompts/03_review.md 四道门 + README 二审/三审 | ✅ test_ac7_ac8 |

## 自审发现并已修的问题（retreat #1，已记错题本）

初版 `claude -p` 继承项目 cwd → 二审进程会加载被审项目自己的 `.claude/settings.json`
hooks，stop_check 会拦它收工 → 系统性 180s 超时。已修：`cwd=tempfile.gettempdir()`。
副作用是正收益：审查者物理上读不到仓库，"只看 diff 不许编"从软规则变硬约束。

## Three honest answers

1. **最丑的地方**：`_fresh_context_review` 与 `_cross_family_review` 有约 15 行同构的
   裁剪/解析逻辑。刻意不抽象——两者失败语义和 IO 通道完全不同（subprocess vs urllib），
   提前抽公共层会让 fail-open 路径变绕。两处出现，按三次法则还不到抽的时机。
2. **生产最可能的失败模式**：claude -p 慢（最坏 +3 分钟/次 advance）或用户 CLI 未登录
   （returncode != 0）。两者都 fail-open 放行，不阻塞，仅损失这道质检。
3. **spec 不支持的代码**：无。import tempfile 放函数内是为了不动文件顶部 import 行
   （最小 diff）。

## Scope check

改动文件 = spec 影响清单（pipeline.py / 03_review.md / README.md），无越权。

PROCEED
