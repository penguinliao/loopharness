# Claude H-H v1.0

> **300 行 Python，让 Claude Code 在听不懂的需求面前也能写对代码。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-required-orange.svg)](https://claude.ai/download)

**这是一个产品级反思版本。** v0.3.4 有 8600 行代码，A/B 实测发现只有 4% 真正在创造价值。v1.0 砍掉那 96%，并把 Hermes（经验沉淀机制）做对了。

测试数据：
- 用户搜索（PM 说"做个搜索"，AI 默认写错）→ vanilla 60% / **v1.0 100%**
- 忘记密码（最难的业务逻辑题）→ vanilla 20% / v0.3.4 40% / **v1.0 100%**

---

## 这个工具解决什么问题

你是 PM，对 Claude Code 说："**我想让用户能搜其他人**"。

vanilla Claude Code 会写：
```python
@app.get("/search")
def search(q: str):
    return db.execute("SELECT * FROM users WHERE username = ?", (q,)).fetchall()
```

**问题**：
- 精确匹配。搜 `john` 不会匹配到 `johnny` 和 `johnson`
- 返回了 `password_hash` 字段（数据泄漏）
- 没有结果数量上限
- 空查询返回所有用户

PM 看到代码——读不懂，看到能跑——以为搞定了。上线后才发现这些坑。

**v1.0 让 AI 在写代码前先想清楚**：
1. 强迫 AI 把 acceptance criteria 写成 spec
2. 给 AI 看一份"PM 通常会忘记说但希望对的事"清单（比如"搜索默认 partial match"、"响应不能含 password_hash"）
3. AI 在 spec 里把这些都列入验收标准
4. 然后再写代码 + 测试
5. 测试不过 → AI 自动回去改代码（最多 3 次，再不过就停下让你看）

结果：同一个 PM 输入，AI 写出来的代码是这样：

```python
@app.get("/search")
def search(q: str = ""):
    if not q.strip():
        raise HTTPException(400, "查询词不能为空")
    if len(q) > 100:
        raise HTTPException(400, "查询词过长")
    rows = db.execute(
        "SELECT id, username, email, bio FROM users "
        "WHERE LOWER(username) LIKE LOWER(?) LIMIT 50",
        (f"%{q}%",),
    ).fetchall()
    return {"results": [dict(r) for r in rows]}
```

partial match ✓ 防 SQL 注入 ✓ 排除 password_hash ✓ 长度上限 ✓ 空查询拒绝 ✓ — 一次写对，没有人工审查。

---

## 30 秒安装

```bash
curl -fsSL https://raw.githubusercontent.com/penguinliao/claude-hh-v1/main/install.sh | bash
source ~/.zshrc   # 或开新终端
```

安装后多了一个 `harness` 命令。

## 在你的项目里用起来

```bash
cd your-project/
harness init                       # 一次性：往项目里装 hooks
harness start "做个用户搜索功能"      # 启动 pipeline，进入 SPEC 阶段

# 现在打开 Claude Code，告诉它你的需求。AI 会自动：
#   1. SPEC 阶段：读 Hermes 清单 + 写 acceptance criteria + 写测试
#   2. IMPLEMENT 阶段：写代码（spec 和测试被 hook 锁死，不能改）
#   3. REVIEW 阶段：自审代码 vs spec
#   4. TEST 阶段：自动跑测试
#   5. 不过就回 IMPLEMENT 改，最多 3 次

harness status     # 任何时候看现在到哪一步了
```

跑完后你会得到：
- `.harness/spec.md` — AI 整理的 acceptance criteria（你能看懂的中文/英文）
- `.harness/test_*.py` — 自动测试脚本
- 项目代码 — 实测都过了的实现
- 自动的 retreat 机制——AI 不会"装作过了"

---

## 真实案例对比

我们做了 5 个 PM 视角的真实任务（"加注册"、"做搜索"、"忘记密码"、"接 OpenAI/Stripe"、"用户注册"），每题都用 vanilla Claude 和 v1.0 各跑一遍。

### 案例 1：用户搜索（最能体现 v1.0 价值）

| 维度 | vanilla Claude | v1.0 |
|------|--------------|------|
| Partial match（搜 john 找到 johnny+johnson） | ❌ 写成精确匹配 | ✅ 用 LIKE %q% |
| 响应不含 password_hash | ❌ 整行返回 | ✅ 显式 SELECT 排除 |
| 结果数量上限（防 DoS） | ❌ 无限制 | ✅ LIMIT 50 |
| 空查询处理 | ❌ 返回所有用户 | ✅ 返 400 |
| SQL 注入防护 | ✅ 参数化 | ✅ 参数化 |
| **总分** | **3/5（60%）** | **5/5（100%）** |

差异来自哪里？v1.0 的 SPEC 阶段强迫 AI 把"partial match"明确列入 AC，然后才能写代码。AC 一旦写下，AI 在 IMPLEMENT 阶段不会偷懒用 `=` 而非 `LIKE`。

### 案例 2：忘记密码（业务逻辑硬核题）

业务流程：
1. 用户填邮箱 → 我们发 reset token
2. 用户点链接 → 改新密码

v1.0 在这道题上能做到的，**vanilla Claude 和 v0.3.4 都做不到**：
- ✅ Token 用 `secrets.token_urlsafe`（不是 `random`）
- ✅ Token 15 分钟过期
- ✅ Token 单次使用
- ✅ 改密码后 DB 真正更新
- ✅ 防邮箱枚举（无论邮箱存不存在响应一样）

| 版本 | 通过率 |
|------|------|
| vanilla Claude | 20%（1/5） |
| v0.3.4（8600 行） | 40%（2/5） |
| **v1.0（300 行）** | **100%（5/5）** |

为什么 v1.0 能做到 v0.3.4 做不到？因为 v1.0 把"自动学习"换成了"手工维护的清单"。`hermes/implicit_expectations.md` 里直接写明了这些隐含期望，SPEC 阶段强迫 AI 应用。

### 案例 3：接外部服务（retreat 机制实战）

PM 任务："接 OpenAI 和 Stripe API"

v1.0 第一次写 → REVIEW 阶段 AI 自审发现"启动时 fail-fast 没做对"→ retreat 回 IMPLEMENT → 修 → 再审 → 再 fail → retreat 第 2 次 → 修对 → 通过。

**最终通过率：100%（6/6）**。retreat 机制让 AI 自己发现自己的问题，不需要 PM 来回看代码。

---

## 设计哲学（如果你好奇为什么这么少代码）

我们删掉了 v0.3.4 的这些东西：

| 删掉的东西 | 删掉原因 |
|----------|--------|
| 8 维度评分引擎（746 行） | 实测对 Sonnet 完全没帮助。换成 ruff + mypy 就够 |
| micro/standard/full 路由 | 复杂度无收益。一种流程就够 |
| 自动 skill_extractor | 从未产出可用 skill。换成手工清单 |
| post_edit / post_agent / pre_commit hook | 边角案例，常误伤正常流程 |
| cooldown 计时器 | 修了 4 次粒度还是不对 |
| 突变测试 / 遥测 / autofix | 用户从不看的功能 |

**原则**：每留下的一行代码必须有 A/B 数据证明它创造价值。

---

## 与 v0.3.4 对比

| 维度 | v0.3.4 | v1.0 |
|------|--------|------|
| 代码量 | 8600 行 Python | **298 行 Python**（-96%） |
| 安装时间 | ~5 分钟 | **30 秒** |
| 一道任务平均 token | ~1.5M | ~600K |
| 一道任务平均成本（API 等价） | $0.8-1.5 | **$0.5** |
| Hooks 数量 | 6 | **2** |
| 流水线阶段 | 5 个（SPEC/DESIGN/IMPLEMENT/REVIEW/TEST） | **4 个**（合掉 DESIGN） |
| 路由分级 | micro/standard/full | **单一流程** |
| Self-improving 机制 | skill_extractor（实测无效） | **Hermes 手工清单 + 人工审核** |
| 测试同样 5 道 PM 任务的通过率 | 平均 ~70% | **平均 ~92%** |

---

## 谁会想用？

**适合**：
- 用 Claude Code 做生产级项目的 PM
- 受够了"AI 看起来写完了，但其实没做对"
- 需要把 PM 的模糊需求转成可执行的 acceptance criteria
- 团队里有非技术成员需要审 AI 写的代码
- 不想为不创造价值的复杂度付钱

**不适合**：
- 5 分钟玩具项目（pipeline overhead 不划算）
- 用 Cursor / Aider / Continue（v1.0 仅支持 Claude Code）
- 写 Ruby / Go / Rust（仅 Python / TypeScript / Vue）

---

## 路线图

- [x] v1.0：核心 spec-first pipeline（4 阶段、retreat、Hermes 手工清单）
- [x] v1.1：**G4 跨家族审查**（3 家 LLM 独立审 git diff，≥2 家 P0=0 × 3 轮才放行 DEPLOY；含 21 个跨项目 P0 类别先验防御库）
- [ ] v1.2：Hermes × G4 化学反应 — Hermes 清单注入 SPEC + G4 prompt；G4 检出反哺 Hermes，让飞轮转起来
- [ ] v1.3：多文件重构场景验证 + 多模型支持（Haiku 测试）
- [ ] v2.0：基于真实使用数据的 Hermes 自动建议机制（仍人工 gate）

## v1.1 新增：G4 跨家族审查

v1.1 引入 **G4 终审 gate**——专治"AI 自己审自己代码"的盲区。

### 怎么个跨家族法

测试通过后，3 家不同模型家族**并行独立**审查你的 `git diff`：
- 🔵 **Claude Opus 4.7**
- 🟢 **Claude Sonnet 4.6**
- 🟣 **DeepSeek V4 Pro**

放行条件：**≥2 家**报告 `P0=0`，且**连续 3 轮**保持。任何一家发现 P0 → pipeline 自动 retreat 到 IMPLEMENT 修。

### 为什么单家族审查不够

Claude 审 Claude 代码 = 同源 RLHF 盲区。三家不同训练管线的 LLM 都漏的 bug，比任一家漏的 bug 罕见得多。

### 自举数据

我们用 v0.3.4 老仓库当被审对象，跑了 **18 轮**G4：
- **65 个**真实 issue 被检出
- 蒸馏出 **21 个跨项目 P0 类别**（状态机假 PASS / Prompt injection / .env RCE / JSON 解析 / 异常吞掉 / 跨家族去重 / severity 标定...）
- 这 21 类自动注入未来所有 G4 运行作为先验防御清单——见 [`knowledge/antagonist_issues.md`](knowledge/antagonist_issues.md)

### 怎么用

```bash
# TEST 通过后，跑 G4（3 家并跑约 5-8 分钟/轮）
harness antagonist run

# 修完代码后清掉 unfixed 标记（让 stuck 解锁）
harness antagonist reset
```

### 配置

项目根 `.env`：
```bash
DEEPSEEK_API_KEY=sk-...     # 第三家共识必需
ANTHROPIC_API_KEY=sk-ant-... # v1.0 起已需
```

未配置 `DEEPSEEK_API_KEY` 时 G4 自动跳过（友好提示）——v1.1 是 v1.0.x 的严格超集，不打断已有流程。

---

## v1.2 新增：无人值守模式（loop）

> 设计来源：2026 loop 理念——官方 `/loop`（自驱节奏的异步 agent）+ Ralph Wiggum loop
> （进度沉淀在文件里，不在 AI 的上下文里）。H-H 的 pipeline 状态机天生支持无状态重入，
> 只差一个外部循环驱动器——Claude Code 原生就有，我们不重复造。

### 用法（PM 一句话）

晚上对 Claude Code 说：

```
/loop 把这个功能做完。每轮：看 harness status，做当前阶段该做的事，advance。
做完了或者卡住了就停下来叫我。
```

AI 会自己安排节奏循环推进：写规格 → 写代码 → 自审 → 测试 → 不过就带着错题本回去修。
你睡觉，它干活。

### 醒来后只有三种结局

| 结局 | 含义 | 你要做什么 |
|------|------|-----------|
| **done ✓** | 测试全过，正常交付 | 看效果，决定上线 |
| **done ⚠️（带病交付）** | 自动测试全过，但黑盒测试修了 3 轮仍有没过的项 | 读 `.harness/delivery_report.md` 的"遗留问题"，拍板上不上线 |
| **stuck** | 自家验收测试修了 3 次都不过 | 读 stuck 说明，补充需求描述或换方向 |

**永不挂起**：黑盒修不过不会卡死等人，会照常交付 + 一份诚实的交付报告（delivery_report）。
**永不糊弄**：自家验收测试（spec 里的 AC）不过的代码，绝不会被"带病交付"——那种只会 stuck。

### 错题本（让 loop 不盲改）

每次没通过，失败原因自动落盘到 `.harness/retreat_log.md`。下一轮哪怕是全新上下文的
AI，开工前也会先读错题本——不重复已经失败过的改法。这是 Ralph loop"记忆在文件不在
上下文"的直接应用。

### Hermes 晨报（经验飞轮也进 loop）

平时想到什么随口记一句（AI 帮你跑，或你自己敲）：

```bash
harness feedback "搜索应该能搜到自己"
```

然后用 Claude Code 的定时任务（`/schedule` 每天早上 8 点）跑一句：

```
读 .harness/inbox.md 和最近的 retreat_log.md，运行 harness hermes-review，
把提议的新经验条目整理成 3 行以内的晨报给我。
```

你每天早上花 30 秒 y/n 审核，清单越用越聪明——但**积累永远由人把关**，这条 v1.0 的
设计原则不变。

---

## License

MIT — see [LICENSE](LICENSE)

## 项目历史

v1.0 从 v0.3.4（仍在 [penguinliao/claude-hh](https://github.com/penguinliao/claude-hh)）演进而来。完整 A/B 实验数据在 [penguinliao/claude-hh-experiments](https://github.com/penguinliao/claude-hh-experiments)。

> "把不创造价值的部分删掉，比再加一层防御更需要勇气。" —— v1.0 release note
