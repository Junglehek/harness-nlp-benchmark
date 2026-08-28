# T1 冒烟测试报告

**日期**：2026-08-25  
**测试者**：用户  
**evaluator 版本**：evaluator.py（含 --gold 参数，支持自定义 gold 路径）

---

## 测试 1：evaluator 逻辑验证

### 1.1 完美答案测试
- **输入**：test_perfect.json（10 条，全对）
- **gold**：fixtures/test_gold.json（10 条）
- **命令**：`python evaluator.py --run-dir ./runs/t1/run_default --gold ./fixtures/test_gold.json`
- **结果**：自动分 90.00/90（格式 27/27 + accuracy 63/63）
- **结论**：✅ 通过

### 1.2 错误答案测试
- **输入**：test_wrong.json（10 条，错 3 条，accuracy=0.7）
- **gold**：fixtures/test_gold.json（10 条）
- **命令**：同上
- **结果**：自动分 71.10/90（格式 27/27 + accuracy 44.1/63）
- **结论**：✅ 通过，与预期 71.1 一致

---

## 测试 2：fixtures 安全隔离验证
- **检查路径**：runs/t1/run_default/workspace/input/t1_input.json
- **检查结果**：仅含 text_id 和 raw_text，无 gold_label 字段
- **结论**：✅ 通过，Agent 运行期间无法接触 gold

---

## 测试 3：格式错误检测验证
- **输入**：故意构造的缺字段 JSON（`[{"text_id": 1, "pred_label": 1}]`，缺 raw_text）
- **结果**：evaluator 报格式错误、扣分、不崩溃，正常结束
- **结论**：✅ 通过

---

## 待补测试
- 测试 4（rubric 打分合理性）：需 Claude Sonnet API，延后执行
- 测试 5（端到端流程）：需 Claude Sonnet API，延后执行

---

## 总体结论

T1 的 evaluator.py、fixtures 隔离机制、输出格式规范已通过冒烟测试，满足 Phase 1 启动条件。