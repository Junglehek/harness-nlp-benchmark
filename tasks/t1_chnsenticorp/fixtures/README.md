# T1 fixtures 说明（研究者内部文件，不随任务下发给 Agent）

## 一、Gold 安全方案（防 Agent 作弊）

- Agent 工作区（workspace）仅放置**不含 gold_label** 的输入数据（字段：`text_id`、`raw_text`）
- gold_label 文件存放于本目录 `t1_gold.json`，由 evaluator.py 在评分阶段独立读取
- Agent 运行期间无法接触 gold 文件（目录隔离，不复制进 workspace）

## 二、文件清单

| 文件 | 用途 |
|------|------|
| `t1_gold.json` | gold 标签，格式 `[{"text_id": 1, "gold_label": 1}, ...]` |
| `prepare_workspace.py` | 数据准备脚本（见下） |
| `README.md` | 本说明 |

## 三、数据准备与工作区重置（每次运行前执行）

```bash
# 从源数据生成 fixtures/t1_gold.json 并重置工作区
python3 fixtures/prepare_workspace.py \
  --source ../../../../eval_datasets/chnsenticorp/ChnSentiCorp_htl_all.csv \
  --run-root ../../runs/t1/A/run_001
```

生成结构：

```
../../runs/t1/A/run_001/workspace/input/t1_input.json   # Agent 输入（无 gold）
fixtures/t1_gold.json                                  # gold（已存在则校验后沿用）
```

**重置口径**：重跑本脚本即重置——会清空并重建 `../../runs/t1/A/run_001/workspace/`（等价于统一控制变量的 `rm -rf workspace && cp -r fixtures workspace`，且保证输入文件不含 gold）。实际遍历 `run_001` 至 `run_010`，共 10 遍。

**评分**：Agent 运行结束后执行

```bash
python3 evaluator.py --run-dir ../../runs/t1/A/run_001/workspace
```

评分结果写入 `../../runs/t1/A/run_001/t1_autoscore.json`（含供 Judge 使用的一致性比对）。
