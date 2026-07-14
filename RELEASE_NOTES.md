# LoopHarness v1.4.0 — Release Notes

**Release candidate date**: 2026-07-14

## 一句话

LoopHarness 把原有 spec-first pipeline 扩展成跨 Claude、Codex、Kimi、GLM 的可靠交付层：
先锁定 Delivery Contract，再给模型最小上下文，最后只用当前仍有效的 artifact 证据报告
就绪度。

## 新增

- `harness memory-init`：幂等创建项目内跨模型共享记忆。
- `harness contract`：保存目标、验收标准、风险与资料授权。
- `harness context`：为四种 agent 生成同格式的最小上下文 bundle。
- `harness evidence`：为项目内 artifact 写入默认标为 declared 的 SHA-256 receipt。
- `harness readiness`：重验当前 hash，分开报告 declared 与 verified，只用 verified 计算交付等级。
- `harness learn`：将学习候选放入 adopt、confirm 或 receipt_only。

## 安全与诚实边界

- 合同拒绝 `.env`、密钥/凭据文件、项目外路径；上下文对未授权、过大或不可读文件 fail closed。
- receipt 不是内容真实性证明：默认 declared 只证明 artifact 登记时的身份与当前 hash；
  artifact 被改动、删除或同种 evidence 最新结果失败后，连当前声明也会失效。
- verified 只由完成真实检查的受信宿主通过 library API 显式写入；CLI 不提供自我认证入口。
- 模型自我反思不能直接成为长期规则；agent CLI 不能使用 `user_explicit`。该来源只供验证了
  用户身份的宿主事件通过 library API 调用；只有当前有效的 verified receipt 可支持证据型学习。
- `.delivery`、`.agent-memory` 或内部任意子项是 symlink 时读写 fail closed，避免把项目记录或读取重定向到外部；拒绝时不会擅自删除用户 symlink。
- `harness init` 会移除旧 `.claude-hh/hooks/`，同时保留无关 hooks，并确保当前两个 hook 各一份。
- CLI 错误只报告路径/类型问题，不回显秘密文件内容。
- LoopHarness 不是对本地恶意代码的安全沙箱；拥有任意 Python/项目文件写权限的进程仍可篡改本地记录。

## 兼容性

仓库名 `claude-hh-v1`、Python 包名 `claude_hh` 和 `harness init/start/advance/status` 保持不变。
LoopHarness 是公开产品展示名。Claude 保留原生项目 hook 旅程；Codex、Kimi、GLM 当前接入
文件式合同、上下文、证据和记忆协议，不声称拥有相同的原生 hook 或会话控制能力。

## 安装与验证

`install.sh` 会把标准库实现复制到安装目录，并在 `HARNESS_BIN_DIR`（默认
`~/.local/bin`）生成独立可执行文件。安装器可重复运行，不会重复写 shell PATH。

发布候选门禁：锁定 v1.4 测试、正式 delivery 回归、历史 pipeline 回归、`ruff`、
`py_compile`、`git diff --check` 与全新 HOME 安装 smoke。

完整复现命令见 [README](README.md)，正式 delivery 用例见
[claude_hh/tests/test_delivery.py](claude_hh/tests/test_delivery.py)。
