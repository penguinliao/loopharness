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
- [ ] v1.1：补 Hermes 清单分类（file handle、HTTP 响应一致性）+ 修判分框架的 3 个已知 bug
- [ ] v1.2：多文件重构场景验证 + 多模型支持（Haiku 测试）
- [ ] v2.0：基于真实使用数据的 Hermes 自动建议机制（仍人工 gate）

---

## License

MIT — see [LICENSE](LICENSE)

## 项目历史

v1.0 从 v0.3.4（仍在 [penguinliao/claude-hh](https://github.com/penguinliao/claude-hh)）演进而来。完整 A/B 实验数据在 [penguinliao/claude-hh-experiments](https://github.com/penguinliao/claude-hh-experiments)。

> "把不创造价值的部分删掉，比再加一层防御更需要勇气。" —— v1.0 release note
