# Growth Batch A：英文首屏、真实 Demo、CI 与四模型激活

## 用户结果

陌生的非技术 PM 或 solo builder 打开 GitHub 后，30 秒内能理解 LoopHarness 解决什么问题，看到真实交付状态变化，选择 Claude/Codex/Kimi/GLM 任一工具继续，并从真实 CI 判断当前 main 是否健康。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | 默认 `README.md` 使用英文首屏，并在顶部提供中文版链接；首屏同时讲清“切换 coding agent 不丢项目记忆”和“不盲信 agent 自报 done”两个可见结果。 | P0 |
| AC2 | `README.zh-CN.md` 保留完整中文版，安装、Demo、四模型边界和证据边界与英文版一致，不宣称自动迁移完整聊天历史或四家原生 hook 等价。 | P0 |
| AC3 | README 首屏引用一个仓库内 SVG 视觉 Demo；SVG 可访问、无外部脚本，展示 Contract → Context → declared evidence → Contract-only/invalidated 的真实状态，不伪造 Production-ready。 | P0 |
| AC4 | README 给出 Claude、Codex、Kimi、GLM 的可复制交接步骤：生成 `.delivery/context_bundle.md`、让所选 agent 读取该文件、完成后登记 artifact 并运行 readiness；明确文件协议不等于登录或控制模型。 | P0 |
| AC5 | `.github/workflows/ci.yml` 在 Python 3.9 与 3.13 上运行默认 pytest，并执行 ruff 与 compileall；README 的 CI badge 指向该真实 workflow。 | P0 |
| AC6 | `pyproject.toml` 增加 Homepage、Repository、Issues、Changelog URL，发行名仍为 `claude-hh`，Python 下限仍为 3.9。 | P0 |
| AC7 | `HN_POST_DRAFT.md` 改为当前 LoopHarness 发布叙事，链接新仓库，不保留旧 v1.0、Claude-only 或未经证实的准确率提升数字。 | P0 |
| AC8 | 默认 README 给出真实 before/after 场景和预期终端输出；不能把用户手写 `1 passed` 描述成独立验证，不能承诺 Star、通用准确率或生产可靠性。 | P0 |
| AC10 | IMPLEMENT→REVIEW 门禁接受本阶段真实修改的产品代码、文档和配置（至少 `.py/.md/.toml/.yml/.yaml/.svg`），但 `.harness` 运行物、planning files、缓存和早于本阶段的旧文件都不能冒充实现。 | P0 |
| AC11 | 自动 reviewer diff 对 tracked/untracked 使用同一安全过滤：不得包含 `.env`、token/credential、`.harness`、planning、缓存或项目外 symlink 内容；安全的新增 Markdown/SVG/YAML/TOML 必须以完整 diff 进入审查。 | P0 |
| AC12 | reviewer 材料不得静默截断：本批所有安全改动必须完整进入 Claude/DeepSeek prompt；超过 80,000 字符时 review 明确 FAIL 并要求拆批，不能截前 20,000 字符后假绿。 | P0 |
| AC9 | 现有 CLI、交付层和历史 pipeline 回归测试继续通过；新增内容不包含密钥、本机绝对路径或真实用户资料。 | P1 |

## Affected files

| File | Change |
|------|--------|
| `README.md` | 英文主首页、价值场景、真实输出、四模型激活、CI badge 与中文入口。 |
| `README.zh-CN.md` | 中文完整版本及相同诚实边界。 |
| `assets/loopharness-demo.svg` | 工业控制台/飞行记录仪风格的真实流程视觉。 |
| `.github/workflows/ci.yml` | Python 3.9/3.13 pytest、ruff、compileall。 |
| `pyproject.toml` | 官方项目 URL，不改发行名和 Python 下限。 |
| `HN_POST_DRAFT.md` | 当前英文发布文案，删除旧版夸大叙事。 |
| `claude_hh/pipeline.py` | `_check_impl` 识别近期真实产品代码/文档/配置，排除运行物与缓存。 |
| `.harness/test_growth_batch_a.py` | 本批锁定验收。 |
| `.harness/test_growth_docs_config_gate.py` | 文档/配置门禁根因回归。 |
| `.harness/test_growth_review_safety.py` | reviewer 敏感路径、symlink 与完整材料 fail-closed 回归。 |
| `claude_hh/tests/test_pipeline_document_changes.py` | 公开回归，覆盖文档任务、审查安全和可执行 HN Demo。 |

## Out of scope

- 不改 `claude_hh` 包名、CLI 命令名或交付层业务逻辑；只修 IMPLEMENT 改动识别范围。
- 不宣称自动导入 Claude/Codex/Kimi/GLM 的完整历史或替代各家会话管理。
- 不做官网、托管服务、遥测、付费功能或生产部署。
- 不对外发帖；只准备 HN/社交发布文案，外部发布另行授权。
- 不承诺本批能直接产生 Star，只记录发布前后的真实 Star 基线。

## 测试策略

**黑盒测试不需要。** 本批没有运行中的 Web/App 交互界面；用户可见结果是静态 README、SVG 和 GitHub CI 配置，锁定测试直接检查最终可见文本、链接、视觉语义和 workflow 命令。TEST 后还会渲染 SVG 真看图，并在推送后通过 GitHub API 核验公开 README、CI 与 Star 基线。

## 风险

- 英文首屏可能在翻译时扩大能力边界；测试锁定“文件协议≠原生集成”和 declared≠verified。
- CI 首次运行可能暴露 Python 版本差异；不能用跳过测试换绿色。
- SVG 若只好看但不表达真实状态会形成营销假象；必须逐项对照 CLI 真输出。
- 扩大门禁扩展名后，缓存、`.harness` 或 planning files 可能制造假阳性；锁定测试必须覆盖这些反例和旧 mtime。
- reviewer diff 会发送给外部模型；tracked 与 untracked 任一旁路泄露秘密都属于 P0，必须复用同一文件安全判断。
- 大 diff 若静默截断会让尾部文件逃审；超过明确预算时宁可要求拆批，也不能把“不完整”写成“已审查”。

## Open questions for PM

- 无阻塞问题；按用户已确认的“优先获星、面向超级个体、强调编程记忆迁移与可靠交付”执行。
