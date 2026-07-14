# LoopHarness v1.4：跨模型可靠交付层与公开发布

## 目标

把当前本机已验证使用的 Harness 新能力整理为可公开安装的 v1.4，并把产品首要用户明确为“刚开始用 AI coding、不会审代码但需要可靠交付的非技术 PM 与超级个体”。公开产品展示名使用 **LoopHarness**，本轮保留现有 GitHub 仓库和 Python 包名以避免旧链接失效。

## Acceptance criteria

| # | Criterion | Priority |
|---|-----------|----------|
| AC1 | 干净源码运行 `harness -h` 时保留原有 pipeline 命令，并新增 `memory-init / contract / context / evidence / readiness / learn`；上下文适配器明确支持 `claude / codex / kimi / glm`。 | P0 |
| AC2 | Delivery Contract 只授权项目内非敏感路径；最小上下文只读取合同允许的文件，拒绝越界路径、`.env`、密钥/凭据文件、超限或不可读文件，且拒绝内容不会进入生成的 context bundle。 | P0 |
| AC3 | Evidence receipt 保存 artifact 相对路径、SHA-256、大小、种类和结果；`readiness` 必须重新核对 artifact 当前 hash，并按每类最新 receipt 判定，文件被改动或最新结果失败时不得虚报更高就绪度。 | P0 |
| AC4 | 学习候选只分 `adopt / confirm / receipt_only`；模型自我反思不得直接 adopt，只有用户明确指令或真实有效 evidence receipt 可以进入 adopt，否则自动降为 confirm。 | P0 |
| AC5 | `install.sh` 在全新 HOME 下可重复执行，安装标准库实现并生成可执行 `~/.local/bin/harness`；第二次安装不重复污染 shell 配置，安装后无需依赖源码目录即可运行帮助和 Delivery 命令。 | P0 |
| AC6 | 公开候选仓库不得包含 `/Users/<local-user>` 等本机绝对路径、真实高熵 API key/token、`.bak-*`、运行日志、缓存或真实项目资料；CLI 错误不得打印秘密文件内容。 | P0 |
| AC7 | README 首屏以 LoopHarness 和非技术 PM/超级个体为核心，明确 Codex、Claude、Kimi、GLM 的真实支持边界，提供 3 分钟可复制 Demo、可信测试证据链接、适合/不适合人群，并删除“仅支持 Claude Code”等过时承诺。 | P0 |
| AC8 | 版本统一为 `1.4.0`；原有 12 条基线测试与新增门禁全绿，`ruff`、`py_compile`、干净安装 smoke 均通过。 | P0 |
| AC9 | 仓库名和 Python 包名本轮保持兼容；产品展示名改变不得破坏旧 `harness init/start/advance/status` 用户旅程。 | P1 |

## Affected files

| File | Change |
|------|--------|
| `claude_hh/delivery.py` | 新增跨模型记忆、合同、上下文、证据、就绪度与三篮子学习，并补证据实时校验。 |
| `claude_hh/pipeline.py` | 注册六个交付命令，更新用户可见帮助和跨模型文案。 |
| `claude_hh/__init__.py` | 版本升级到 1.4.0。 |
| `claude_hh/tests/test_delivery.py` | 正式回归测试。 |
| `prompts/01_spec.md` | 同步部署版跨模型交付上下文要求。 |
| `prompts/02_implement.md` | 同步部署版 IMPLEMENT 约束。 |
| `prompts/03_review.md` | 同步部署版独立审查约束。 |
| `prompts/04_test.md` | 同步部署版最终用户可见结果门禁。 |
| `install.sh` | 幂等安装与 `~/.local/bin/harness` 入口。 |
| `README.md` | LoopHarness 跨模型定位、3 分钟 Demo、证据和用户边界。 |
| `CHANGELOG.md` | v1.4 变更记录。 |
| `RELEASE_NOTES.md` | GitHub 发布说明。 |
| `pyproject.toml` | 版本与描述更新。 |
| `.gitignore` | 忽略本地规划、Harness 运行态、缓存、日志和备份。 |

## 测试策略

**黑盒测试不需要。** 本任务没有 GUI；用户旅程是本地 CLI，新增测试会在临时 HOME/临时项目中启动真实 Python 子进程，覆盖帮助、安装、合同、上下文、证据、就绪度和学习的最终可见结果。GitHub 页面发布后再用远端页面/API 做只读核验。

## Out of scope

- 本轮不改 GitHub 仓库 URL 和 Python 包名；先用展示名验证传播效果。
- 本轮不承诺具体 Star 数，不购买 Star、不自动群发推广。
- 本轮不发布 PyPI 包；GitHub 安装与源码安装先闭环。
- 本轮不把用户级强制 Opus hooks、真实项目 Hermes、日志或安装目录备份公开。
- 本轮不改变 G4 第三方 API 的凭据配置方式。

## 风险与停止条件

- 安装版功能无法由测试解释或依赖本机私有状态：不移植，记录为内部实验。
- 秘密扫描、干净安装或证据 fail-closed 任一 P0 失败：禁止推送默认分支。
- README 中的效果数字无法回到仓库证据：删除或改成明确实验条件，不扩大宣传。
