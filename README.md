# LoopHarness

> 给**非技术 PM 和超级个体**的跨模型可靠交付层：先锁定要交付什么，再给 AI 最小上下文，最后用可核对证据判断做到哪一步。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-pytest-blue.svg)](claude_hh/tests/test_delivery.py)

你可以继续用熟悉的 `harness init → start → advance → status` 做 spec-first 开发，也可以用 v1.4 新增的 Delivery Contract、最小上下文、evidence receipt 和 `readiness`，避免 AI 把“我写完了”说成“已经可靠上线”。

LoopHarness 不要求你会审代码。它把交付拆成几份能看懂、能追溯的东西：

- **Delivery Contract**：目标、验收标准、风险和允许读取的资料。
- **最小上下文**：只打包合同授权的项目内文件，拒绝 `.env`、凭据和越界路径。
- **Evidence receipt**：记录 artifact 相对路径、SHA-256、大小、种类和声明结果；默认不把声明当成验证。
- **readiness**：重新核对当前文件 hash，分开展示当前声明与受信宿主提供的独立验证。
- **三篮子学习**：`adopt / confirm / receipt_only`；模型反思不能自行变成长期规则。

## 支持哪些 AI

| AI coding agent | 当前支持边界 |
|---|---|
| Claude | 支持原有项目 hooks、四阶段 pipeline，以及 v1.4 Delivery 命令 |
| Codex | 支持 Delivery Contract、最小上下文 bundle、证据、就绪度与共享记忆 |
| Kimi | 支持同一套 agent adapter 和文件式交付协议；不代替 Kimi 自己的会话管理 |
| GLM | 支持同一套 agent adapter 和文件式交付协议；不代替 GLM 自己的会话管理 |

这里的“跨模型”指四种 agent 都能消费同一种、受合同约束的上下文和交付证据。LoopHarness **不会替你安装或登录这些 AI，也不会声称四家的原生 hook 能力完全相同**。

## 30 秒安装

```bash
git clone https://github.com/penguinliao/claude-hh-v1.git loopharness
cd loopharness
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
harness -h
```

安装器只复制 Python 标准库实现与项目资源，并生成独立可执行的 `~/.local/bin/harness`；重复执行不会重复写 shell 配置。

## 3 分钟 Demo

下面这段可以直接复制。它不会连接任何模型或外部服务。

```bash
mkdir -p /tmp/loopharness-demo/docs
cd /tmp/loopharness-demo
printf '只返回公开发布信息。\n' > docs/brief.md

harness memory-init
harness contract "发布一个可靠 Demo" \
  --ac "帮助命令可运行" \
  --ac "结果有可核对声明回执" \
  --allow docs/brief.md

harness context "生成发布上下文" --agent codex --include docs/brief.md
printf '1 passed\n' > functional.txt
harness evidence functional functional.txt --outcome passed
harness readiness
```

你会看到 `.delivery/contract.json`、`.delivery/context_bundle.md`、`.delivery/evidence.jsonl` 和 `.delivery/readiness.json`。Demo 里的 receipt 是 **declared**：它只证明 `functional.txt` 登记时的身份以及当前 hash 是否仍一致，不证明文件内容真实，也不会把等级抬高到 Preview/Pilot/Production。再修改文件后重跑 `harness readiness`，旧 receipt 会失效。

Python library API 的调用方可以显式传入 `verification="verified"`。只有完成了真实测试、人工验收或外部系统校验的受信宿主才应这样标记；LoopHarness 不验证调用方身份，也不会自行把普通声明升级为 verified。CLI 不提供该升级参数。

LoopHarness 是交付流程和可追溯性工具，不是对本地恶意代码的安全沙箱：已经拥有任意 Python 执行权或项目文件写权限的进程仍能篡改记录。生产安全结论必须结合独立测试、访问控制和真实环境验收。

`harness learn` 的 agent CLI 只接受 `model_reflection` 和 `evidence_receipt`。`user_explicit` 只保留在 Python library API 中，供已验证用户身份的宿主事件调用；模型不能通过 CLI 冒充用户明确指令。

## 原有 pipeline 仍兼容

```bash
cd your-project
harness init
harness start "做一个用户搜索功能"
harness status
# AI 按提示完成 SPEC → IMPLEMENT → REVIEW → TEST，并在每阶段运行 harness advance
```

REVIEW 会依次执行自审、`ruff/mypy` 静态检查、干净上下文二审和跨家族审查。自审或静态检查明确失败会回炉到 IMPLEMENT；干净二审和跨家族服务不可用或结果不可解析时会跳过。跨家族审查首次提出新的反对意见会回炉，连续相似反对可能触发熔断，降级为 advisory 后允许继续。

## 可选：无人值守

如果当前宿主支持 `/loop`（例如提供该命令的 Claude Code 环境），可以让宿主定期执行 `harness status`，需要推进时再执行 `harness advance`。`/loop` 是宿主能力，LoopHarness **不内置 daemon，也不会自行常驻运行**。

自动测试已经通过，但外测失败并耗尽回炉预算时，LoopHarness 会自动生成 `delivery_report` 并进入 `done⚠️`，再由负责人决定是否上线。无人值守只减少重复操作，不替负责人做上线决策。

## Hermes 晨报

LoopHarness 不内置 scheduler。你可以用宿主已有的定时任务，或每天人工复制同一条模板：“读取项目 inbox，汇总新增反馈与证据，提出待确认的规则变更，并列出尚缺证据的事项。”晨报只生成待确认提议；未经用户明确确认或有效证据 receipt，禁止自动 `adopt`。

仓库名和 Python 包名仍保留为 `claude-hh-v1` / `claude_hh`，避免旧安装链接和脚本失效；公开产品展示名从 v1.4 起使用 LoopHarness。

## 可信证据

- [Delivery 层正式回归测试](claude_hh/tests/test_delivery.py)：覆盖授权边界、hash 重验、最新 receipt 和学习降级。
- [诚实性与升级加固测试](claude_hh/tests/test_delivery_hardening.py)：覆盖声明/验证分离、CLI 身份边界、symlink fail-closed 和旧 hook 清理。
- [历史 pipeline 回归测试](claude_hh/tests/)：覆盖 `init/start/advance/status` 兼容旅程。
- [v1.4 变更记录](CHANGELOG.md) 与 [发布说明](RELEASE_NOTES.md)：列出范围和已知边界。

本仓库不承诺 Star 数、通用准确率或“所有项目自动上线”。可信结论以你本地执行 `pytest`、`ruff` 和实际 artifact receipt 为准。

## 适合 / 不适合

适合：

- 不会审代码，但需要让 AI 按明确验收标准交付的非技术 PM。
- 一个人同时做产品、开发和发布，希望降低模型换来换去的上下文成本。
- 团队想保留“读了什么、凭什么说通过、现在是否仍有效”的轻量审计记录。

不适合：

- 需要云端多租户平台、权限后台或托管式 agent 调度的团队。
- 没有任何测试或可保存 artifact，却希望工具自动证明生产可靠的项目。
- 要求 LoopHarness 代替安全审计、人工产品验收、备份恢复演练或线上监控的场景。

## 开发验证

```bash
python3 -m pytest -q
ruff check .
python3 -m py_compile claude_hh/*.py claude_hh/tests/*.py
```

MIT License。欢迎提交能复现真实交付问题的 issue 和测试。
