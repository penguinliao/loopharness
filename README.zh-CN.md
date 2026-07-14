# LoopHarness

> **切换 coding agent 不丢项目记忆，也不再盲信 AI 说“做完了”。**

[English](README.md) · 面向使用 Claude、Codex、Kimi 或 GLM 的非技术 PM、Vibe Coding 超级个体和独立开发者。

[![CI](https://github.com/penguinliao/loopharness/actions/workflows/ci.yml/badge.svg)](https://github.com/penguinliao/loopharness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/penguinliao/loopharness)](https://github.com/penguinliao/loopharness/releases/latest)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-0b7285.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-f4b942.svg)](LICENSE)

![LoopHarness 交付飞行记录仪](assets/loopharness-demo.svg)

AI 很会写代码，真正困难的是：换一个 AI 后，你的身份、项目和开发习惯是否还在；AI 说“做完了”时，证据是否还存在。

使用 LoopHarness 之后：

- 项目记忆、决定和验收标准保存在项目自己的文件里。
- Claude、Codex、Kimi、GLM 读取同一份受合同约束的最小上下文。
- artifact 回执会重新核对当前文件 hash，文件变化后旧声明失效。
- AI 自己声明 passed 仍然只是 `Contract-only`，不能给自己认证成生产就绪。

## 四步闭环

1. **记住**：把用户明确表达的偏好、项目笔记和决定放进 `.agent-memory/`。
2. **锁定**：写清目标、验收标准、风险和允许读取的资料。
3. **交接**：给 Claude、Codex、Kimi 或 GLM 生成同一种 Markdown 上下文。
4. **核对**：登记真实 artifact，重验文件身份，并明确展示还缺哪些独立验证。

LoopHarness 是本地 Python 标准库 CLI，不要求注册 LoopHarness 云账号，也不会把项目文件发到 LoopHarness 服务器。

## 安装

```bash
git clone https://github.com/penguinliao/loopharness.git && cd loopharness && bash install.sh
export PATH="$HOME/.local/bin:$PATH"
harness -h
```

安装器把实现复制到 `~/.loopharness`，并生成 `~/.local/bin/harness`；重复执行不会重复写 PATH。

## 3 分钟真实 Demo

这段 Demo 不连接任何模型或外部服务：

```bash
mkdir -p /tmp/loopharness-demo/docs && cd /tmp/loopharness-demo
printf '只允许读取公开发布信息。\n' > docs/brief.md

harness memory-init
harness contract "发布一个可靠 Demo" \
  --ac "帮助命令可运行" \
  --ac "artifact 回执当前仍有效" \
  --allow docs/brief.md
harness context "准备发布" --agent codex --include docs/brief.md

printf '1 passed\n' > functional.txt
harness evidence functional functional.txt --outcome passed
harness readiness
```

真实输出包含：

```text
artifact 声明回执已登记 ✓（functional / passed）
  边界：只证明该文件登记时的身份与当前 hash，不证明内容真实或生产就绪。
当前交付等级：Contract-only
  当前声明回执（未独立验证）：functional
```

这里的 `1 passed` 是 Demo 自己写的，所以只能算 **declared**，不是独立验证。继续修改文件再运行 readiness：

```bash
printf 'changed\n' >> functional.txt
harness readiness
```

旧声明会因为 hash 不一致而失效。LoopHarness 没有证明测试内容为真；它证明的是“现在这份 artifact 还是不是登记时那一份”。

## 接给四种 coding agent

先创建一份合同，再按当前使用的 agent 四选一：

```bash
harness context "执行已经确认的合同" --agent claude --include docs/brief.md
harness context "执行已经确认的合同" --agent codex  --include docs/brief.md
harness context "执行已经确认的合同" --agent kimi   --include docs/brief.md
harness context "执行已经确认的合同" --agent glm    --include docs/brief.md
```

然后：

1. 告诉所选 agent：`读取 .delivery/context_bundle.md，只执行其中合同。`
2. 让它生成真实测试报告、截图或回滚日志等 artifact。
3. 用 `harness evidence functional path/to/report.txt --outcome passed` 登记当前文件。
4. 用 `harness readiness` 查看哪些是声明、哪些已有独立验证、哪些仍缺失。

这是一套文件协议。LoopHarness 不会替你登录或控制 Claude、Codex、Kimi、GLM，不会导入你的完整聊天记录，也不宣称四家拥有相同的原生 hook。Claude 保留原项目 hook 旅程；其他 agent 通过各自宿主读取同一份合同和上下文。

## 迁移的是项目记忆，不是完整聊天记录

`harness memory-init` 会创建：

```text
.agent-memory/
├── profile.md       # 用户明确表达的沟通与开发习惯
├── projects/        # 项目笔记
├── decisions/       # 长期决定
├── receipts/        # 证据指针
├── inbox.md         # 等待确认的学习候选
└── audit.jsonl      # 本地活动留痕
```

这些内容跟着项目走，所以切换 agent 后仍能复用。LoopHarness 不会导入 Claude、Codex、Kimi 或 GLM 的完整聊天记录；什么值得成为长期记忆，由你决定。

## declared 与 verified

- **declared**：CLI 只登记路径、大小、SHA-256、声明结果和文件当前是否一致，不证明内容为真。
- **verified**：只留给真正完成独立检查的受信宿主通过 Python library API 写入；CLI 不能把自己的声明升级成 verified。

LoopHarness 不认证 library caller，也不是阻止项目内恶意代码的安全沙箱。生产判断仍需真实测试、访问控制、备份恢复和真实环境验收。

## 原有 spec-first pipeline

```bash
cd your-project
harness init
harness start "做一个用户搜索功能"
harness status
# AI 按 SPEC → IMPLEMENT → REVIEW → TEST 推进，并运行 harness advance。
```

REVIEW 会运行自审、可用的 `ruff`/`mypy`、干净上下文复审和跨家族复审。外部审查不可用时会明确显示 skipped，不会冒充已经通过。

## 不是什么

- 不是云端多 agent 控制台。
- 不是不同模型厂商之间的完整聊天记录自动迁移。
- 不是“登记了 artifact 就证明内容正确”。
- 不能代替安全审计、人工产品验收、部署门禁和线上监控。
- 不承诺 Star 数、通用准确率或自动达到生产可靠性。

## 开发验证

```bash
python3 -m pytest -q
ruff check .
python3 -m compileall -q claude_hh
```

欢迎提交能复现真实交付失败的 [Issue](https://github.com/penguinliao/loopharness/issues)。MIT License。
