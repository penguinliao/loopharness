# 自审报告：loop 化②（第 2 轮，stale-verdict 已修）

## AC 覆盖

- **AC1/AC2**：`_check_external_review` 物理上只读 `external_review.md`，从不引用 zhuolong
  → 浊龙取任何值都改变不了判定。AC2 测试真喂浊龙 PASS/不通过/缺失三种并断言决策集合唯一。
- **AC3**：`_external_gate` 决策 wait/retreat/degraded/pass，retreat_count≥3 边界与 spec 一致。
- **AC4**：`prompts/02_implement.md` 含错题本必读 + fresh 子 agent 有界派工指令。
- **AC5**：`prompts/06_external_test.md` 含认知隔离(只看 spec+产物) + external_review.md + fail-open。

## 第 1 轮发现的问题 → 已修

stale 验收 verdict 导致空转回炉：外测没过 → 回炉 → 返工后读到上一轮残留的旧判定 → 立刻又回炉。
**修复**：新增 `_invalidate_external_review`，在 `_finish_test` 的 retreat 分支（retreat 前、
degraded 不删）清掉 stale 的 external_review.md，强制返工后变 "wait" 重新外测。
手动验证：修前 gate=retreat → 清掉 → gate=wait（强制重新验收）。
后置条件已由 `test_ac3_external_missing_gate_waits` 覆盖。

## 检查项

- ruff 整仓干净；mypy 未安装(gate 跳过)；全套 43 测试过。
- CJK 词边界正则已实测：`判定：通过`→PASS、`不通过`→正确归为没过且不误命中 PASS。
- 本轮顺手修了一个 P2 文案（delivery_report 拼接缺换行，已补）。
- **二审抓到的 P0 已修**：`_check_external_review` 原来"PASS 词压过不通过词"——一份判没过
  但正文含"通过/PASS"的验收报告会被误放行，击穿安全门禁。已改成 fail-closed 的
  "末位判定为准"（照搬 `_check_review` 已验证逻辑）。手动验证：判没过+正文含"通过"→正确归为没过。
- 遗留 P2（不阻断）：两个 tail 解析函数可抽公共 helper，后续整洁化。

## 独立 Sub-agent 审查结论

> 独立 Explore sub-agent（干净上下文，只看 spec + diff + 测试，不知代码怎么写的）原文判定。

独立判定：通过（PROCEED），无 P0 阻断问题。要点：

- AC1/AC2 满足：`_check_external_review` 函数体只构造 external_review.md 路径，全程无 zhuolong
  引用，浊龙物理上无法影响判定；AC2 测试真喂三种浊龙值断言决策集合唯一，是真行为断言。
- AC3 满足：四态决策正确，`>=3` 边界与 spec"≥3 带病交付"一致，测试用 0 和 3 两点覆盖边界。
- stale-verdict 已修：`_invalidate_external_review` 在 retreat 分支先清后退，degraded 分支
  保留旧报告供 delivery_report 引用，逻辑闭环。
- _finish_test 无回归：无 external_brief 直接 done；浊龙降级为旁证只 print 不门禁；无 brief 时
  `_check_zhuolong` 返回 pass 不误打印。
- 测试真实性：12 个测试真 import 真调函数断言返回值，tempfile 隔离、无 bare assert；
  AC4/AC5 读 prompt 断言关键串符合 spec 测试方案约定，非假绿。
- 新 P0 排查：read_text/unlink 有 exists/missing_ok 保护，re 模块顶部已 import 不会 NameError；
  向后兼容（浊龙降级是 spec 明确要求的设计内变更）；CJK 正则边界已独立实测无误。

总结：5 条 P0 AC 实现与测试一致，stale-verdict 修复时机正确，无回归、无新阻断问题，可放行。

PROCEED
