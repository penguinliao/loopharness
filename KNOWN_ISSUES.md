# Known Issues — Claude H-H v1.0.3

> 透明清单。这些是已知但**未达到"用户撞了出生产事故"标准**的问题，按 v1.0 manifesto"Every line must earn its keep on A/B data"原则**不发 hotfix**。
>
> 真有用户在实际场景撞到任何一项，请提 GitHub issue，**用真实使用证据 + 复现步骤**触发对应修复。

---

## Issue #1：`hermes-review` 输入 `G` / `global` 默认走 L2（项目级），不走 L1（全局）

- **症状**：UI 提示 `[P]roject / [G]lobal (默认 P)`，但 code 只识别小写 `g`。输入 `G`、`Global`、`global` 都会**静默走 L2**。
- **后果**：无数据丢失，但 PM 想加到全局清单的条目可能进了项目级。
- **绕过**：输入小写 `g`。
- **触发修复**：用户报告"我输 G 但没进全局清单"。
- **修法预算**：3 行（`if loc in ("g", "G", "global"):`）。

## Issue #2：v1.0 → v1.0.3 跨版本 `proposed_skills.md` 不被读取

- **症状**：v1.0 用户跑完 pipeline 后 hermes_propose 写到 `proposed_skills.md`。如果用户在 review 之前升级到 v1.0.3，旧文件不被新版 `_read_proposals()` 读取。
- **后果**：旧 review 队列被孤立。
- **绕过**：升级前先跑 `harness hermes-review` 处理完队列。
- **触发修复**：用户报告"我从 v1.0 升级后旧的提议消失了"。
- **修法预算**：5 行（兼容老路径）。

## Issue #3：`HOME` 环境变量未设时 `Path.home()` 抛 RuntimeError

- **症状**：在没有设置 `HOME` 的 CI / Docker 受限环境运行 `harness hermes-show` 或 `harness hermes-review` 会显示 traceback。
- **后果**：工具崩溃但不损坏数据。
- **绕过**：设置 `HOME` 环境变量。
- **触发修复**：用户在 CI / Docker 场景报告 traceback。
- **修法预算**：10 行（顶层 try/except）。
- **当前评估**：Claude H-H 用户主要是本地开发的非技术 PM，几乎不在 CI/Docker 场景跑。

## Issue #4：bullet 解析正则严格要求 `**Bold**` 格式

- **症状**：在 L1/L2 写 `- key — desc`（无粗体）的 bullet **不会进合并清单**，且没有警告。
- **后果**：PM 自己写的非标准 bullet 被静默忽略。
- **绕过**：跟着内置 L0 清单的格式抄（`- **粗体名称** — 描述`）。
- **触发修复**：用户报告"我加的 bullet 没生效"。
- **修法预算**：扩正则有副作用（破 v1.0 single-markdown-simple 立场），更可能改成"loader 在丢弃时打 stderr warning"（5 行）。

## Issue #5：测试覆盖盲区

- **症状**：`test_load_layers_only_builtin_equals_v1` 只断言输出含 header 字符串，没断言"完全无 hermes 文件时严格等价 v1.0 行为"。
- **后果**：未来重构 `hermes_loader` 时可能引入静默回归而测试不抓。
- **绕过**：手动跑 `harness hermes-show` 在空环境下确认行为。
- **触发修复**：未来 v1.1+ 重构 hermes_loader 时一并加。
- **修法预算**：5 行新单测。

---

## 为什么这些不发 hotfix

按 v1.0 manifesto，每条修改必须：
1. 有真实用户撞到的证据
2. 修了之后 PM 实际场景有改善

5 个 issue 当前都不满足这两条。强行修就是"为完整性加复杂度"——v1.0 manifesto 明确拒绝。

如果以后某条被真实用户报告，会在那个 hotfix 里**单独修该条**，并在 release notes 引用本文档。

---

*Last updated: 2026-04-26 with v1.0.3 release.*
