# Harness-NLP-Benchmark

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: In Progress](https://img.shields.io/badge/status-in%20progress-blue)]()

> **基于 Harness-Bench 方法论的 DeepSeek Harness 与 OpenAI Codex 在 NLP 数据工程任务上的效应分离评测**

---

## 为什么做这个项目？

现有 Agent 框架对比多聚焦于通用编程任务（SWE-bench、HumanEval），而**语料库语言学+NLP 数据工程**这一细分场景下的 harness 行为差异尚无人系统测量。

本项目受 [Harness-Bench (Yao et al., 2026)](https://arxiv.org/abs/2605.27922) 启发，采用**固定外部任务条件、交叉 harness-model 配置**的设计，首次尝试分离 **模型效应**（同 harness 换模型）与 **Harness 效应**（同模型换 harness）在真实 NLP 工作流中的贡献。

---

## 实验设计

### 2×2 全交叉矩阵（四条件均已验证通过）

| 条件 | Harness | 底层模型 | 测量目标 |
|:---:|:---|:---|:---|
| A | DeepSeek Harness (v0.149.1) | DeepSeek-V4 | 基线 |
| B | DeepSeek Harness (v0.149.1) | GPT-5.6 Terra | **模型效应**（同 harness，换模型） |
| C | OpenAI Codex CLI | GPT-5.6 Terra | **Harness 效应**（同模型，换 harness） |
| D | OpenAI Codex CLI | DeepSeek-V4 | 交叉验证（同模型换 harness + 同 harness 换模型） |

> **条件 B/D 兼容性均于 2026-08-27 实测通过**：B 经 OfoxAI 平台接入 GPT-5.6-Terra，D 经 DeepSeek API（`https://api.deepseek.com/v1`，`wire_api = "responses"`）接入 Codex CLI。2×2 全交叉正式确立。

### 运行规模

| 参数 | 值 |
|:---|:---|
| 条件数 | 4（A/B/C/D） |
| 任务数 | 5（T1–T5） |
| 每条件每任务遍数 | **n = 10**（2026-08-28 拍板冻结） |
| 正式实验总运行量 | **4 × 5 × 10 = 200 次** |
| T1 Phase 1 预实验 | 4 × 10 = 40 次 |

### 控制变量
- **超时**：10 分钟/任务
- **Token 预算**：100K/任务
- **初始状态**：每次运行前由 `fixtures/` 重置
- **评估协议**：双层评分 = 自动 Oracle 90% + LLM-as-Judge 10%

### 统计口径
- 均值、标准差、中位数、极差、四分位数
- IQR 异常值识别（Q1 − 1.5×IQR ~ Q3 + 1.5×IQR），异常值标记不删除
- 同时报告含异常值与剔除异常值两套统计
- 技术异常（503/空输出/超时/截断）单独标记

---

## 评测任务（5 个）

| # | 任务 | 类型 | 难度 | 状态 |
|:---:|:---|:---|:---:|:---:|
| T1 | ChnSentiCorp 中文情感二分类 | 文本分类 | ⭐⭐ | ✅ 三件套冻结，冒烟测试通过 |
| T2 | Brown Corpus 文体关键词提取 | 语料库分析 | ⭐⭐⭐ | 骨架搭建 |
| T3 | 跨语言主题对齐 | 跨语言对比 | ⭐⭐⭐⭐ | 待设计（英文语料待确认） |
| T4 | CLUENER 2020 中文 NER | 命名实体识别 | ⭐⭐⭐⭐ | 骨架搭建 |
| T5 | WMT19 平行语料质量筛选修复 | 双语对齐检查 | ⭐⭐⭐⭐ | 骨架搭建 |

> 覆盖：分类 / 关键词 / NER / 对齐 / 跨语言，中英双语，⭐⭐~⭐⭐⭐⭐ 梯度。任务编号于 2026-08-24 重构，不追溯旧编号。

---

## 评分机制：双层架构

| 层级 | 名称 | 占比 | 执行者 | 评分对象 |
|:---|:---|:---:|:---|:---|
| 第一层 | Oracle 自动评分 | 90% | `evaluator.py`（确定性程序） | 格式合规、数值正确性 |
| 第二层 | LLM-as-Judge | 10% | `judge.py`（Claude Sonnet 5） | 报告质量、可读性、分析深度 |

**Judge 配置（全局冻结）**：
- 模型：`anthropic/claude-sonnet-5` via OfoxAI
- temperature = 0（写死）
- **median_of_3 机制**：每个 run 评 3 次取中位数（因 temperature=0 实际不稳定，同报告 5 次评分极差达 28.8）
- 审计：每次评分独立保存 `t1_judge_log_001~003.json`，最终 `t1_judgescore.json` 含 `raw_scores` 数组

**T1 Judge 五维度**：

| 维度 | 权重 | 性质 |
|:---|:---:|:---:|
| 报告完整性 | 30% | 客观 |
| 统计指标计算正确性 | 30% | 客观 |
| 格式规范性 | 20% | 客观 |
| 可读性 | 10% | 主观 |
| 分析深度 | 10% | 主观 |

> 主观维度仅 20%，客观维度 80%，降低 Judge 主观性影响。rubric.md 含 0-19 分严格锚点，消除同情分。

---

## 快速开始（复现）

```bash
# 1. 克隆仓库
git clone https://github.com/Junglehek/harness-nlp-benchmark.git
cd harness-nlp-benchmark

# 2. 安装依赖
# DSH: Node.js 20+, npm install -g @deepseek-ai/dsh
# Codex: 按官方文档配置 CLI
# Python: 3.10+（evaluator/judge 仅用标准库，无需 pip install）

# 3. 配置 API Key
export DEEPSEEK_API_KEY="sk-..."    # 条件 A/D
export OPENAI_API_KEY="sk-..."      # 条件 C
export OFOXAI_API_KEY="sk-..."      # 条件 B + Judge

# 4. 运行 T1 预实验（4 条件 × 10 遍 = 40 次）
python scripts/run_benchmark.py --task t1 --conditions A B C D --repeat 10

# 5. Judge 评分（median_of_3）
cd tasks/t1_chnsenticorp
python3 judge.py --batch "runs/t1/*/run_*" --repeat 3
```

---

## 仓库结构

```
harness-nlp-benchmark/
├── tasks/                          # 标准化任务目录
│   ├── t1_chnsenticorp/            # ✅ 已冻结（三件套 + judge.py）
│   │   ├── README.md               # 任务指令（Agent 输入）
│   │   ├── evaluator.py            # 自动评分 Oracle（90 分）
│   │   ├── judge.py                # LLM-as-Judge（10 分，median_of_3）
│   │   ├── rubric.md               # Judge 评分标准（含 0 分锚点）
│   │   ├── data/                   # 输入数据集（只读）
│   │   ├── fixtures/               # 初始工作区 + 受保护 gold
│   │   ├── smoke_test_data/        # 冒烟测试样本（好/中/差三档）
│   │   ├── smoke_test_results/     # 冒烟测试结果
│   │   └── runs/t1/run_default/    # 冒烟测试端到端样本
│   ├── t2_brown_corpus/            # 骨架
│   ├── t4_cluener/                 # 骨架
│   └── t5_wmt19/                   # 骨架
├── scripts/                        # 运行与评测脚本（待编写）
├── results/
│   ├── pilot/                      # 预实验结果
│   └── final/                      # 正式实验结果
├── log/                            # 开发过程记录
├── docs/                           # 文档
└── .gitignore
```

> T3（跨语言主题对齐）目录待搭建，英文语料待确认。

---

## T1 冒烟测试结果（2026-08-28）

T1 已通过全部 5 项冒烟测试，三件套冻结：

| 测试项 | 状态 | 证据 |
|:---|:---:|:---|
| evaluator 逻辑（完美 90.00 / 错误 71.10） | ✅ | `smoke_test_results/t1_autoscore_{perfect,wrong}.json` |
| fixtures 隔离（workspace 无 gold_label） | ✅ | `workspace/input/` 无 gold |
| 格式错误检测 | ✅ | `smoke_test_results/t1_autoscore_badformat.json` |
| rubric 打分合理性（median_of_3） | ✅ | Good 70.80 / Medium 59.50 / Bad 12.00 |
| 端到端流程 | ✅ | `runs/t1/run_default/t1_judgescore.json` |

**测试 4 三档梯度（median_of_3）**：

| 档位 | Judge 总分 | Judge 分(10分制) | 梯度差 |
|:---|:---:|:---:|:---:|
| Good | 70.80 | 7.08 | — |
| Medium | 59.50 | 5.95 | ↓ 11.3 |
| Bad | 12.00 | 1.20 | ↓ 47.5 |

---

## 初步结果（待更新）

| 指标 | DSH-V4 (A) | DSH-Terra (B) | Codex-Terra (C) | Codex-V4 (D) |
|:---|:---:|:---:|:---:|:---:|
| T1 成功率 | — | — | — | — |
| T1 平均分 | — | — | — | — |
| **模型效应** | — | — | — | — |
| **Harness 效应** | — | — | — | — |

> T1 预实验待启动（4 条件 × 10 遍 = 40 次）。

---

## 核心发现（撰写中）

- 🔍 **模型效应**：同 harness 下，换模型对 NLP 数据工程任务的影响程度？
- 🛠️ **Harness 效应**：同模型下，DSH 与 Codex 在工具选择、错误恢复、代码质量上的差异？
- 📊 **任务差异**：哪些任务对 harness 设计更敏感？

---

## 技术栈

- **Agent 框架**：DeepSeek Harness (v0.149.1), OpenAI Codex CLI (v0.149.1)
- **模型后端**：DeepSeek-V4, GPT-5.6 Terra
- **Judge 模型**：Claude Sonnet 5 via OfoxAI（temperature=0, median_of_3）
- **评测**：custom `evaluator.py`（Oracle 90%）+ `judge.py`（LLM-as-Judge 10%）
- **语言**：Python 3.10+（evaluator/judge 仅用标准库）, Node.js 20+
- **数据**：HuggingFace Datasets, statmt.org, ChnSentiCorp, Brown Corpus, CLUENER 2020, WMT19

---

## 预算

- **正式实验**：4 条件 × 5 任务 × 10 遍 = 200 次运行
- **Judge 调用**：200 × 3（median_of_3）= 600 次 API 调用
- **预估总费用**：待 T1 预实验实测后精确计算（n=10 较 n=3 增加约 3.3×）
- **预算上限**：¥120（初始口径，待 T1 pilot 后重估）

---

## 引用

如果你参考了本项目的方法或数据，请引用：

```bibtex
@misc{harness-nlp-benchmark,
  title={Harness-NLP-Benchmark: A Pilot Study on Harness Effects in NLP Data Engineering},
  author={Boze Lin},
  year={2026},
  howpublished={\url{https://github.com/Junglehek/harness-nlp-benchmark}},
}
```

**相关文献**：
- Yao, Y., et al. (2026). Harness-Bench: Measuring harness effects across models in realistic agent workflows. *arXiv preprint* arXiv:2605.27922.

---

## 进度

- [x] 实验设计定稿（2026-08-23）
- [x] GitHub 仓库 + README 发布（2026-08-23）
- [x] 任务编号重构 + 难度梯度重设（2026-08-24）
- [x] T1 三件套编写 + 冻结（2026-08-24）
- [x] 条件 B/D 兼容性验证通过，2×2 全交叉确立（2026-08-27）
- [x] 全局遍数 n=10 拍板冻结（2026-08-28）
- [x] 双层评分机制 + LLM-as-Judge 设计冻结（2026-08-28）
- [x] T1 冒烟测试五项全通过 + 三件套冻结 v2（2026-08-28）
- [ ] Phase 1: T1 预实验（4 条件 × 10 遍 = 40 次）
- [ ] T2–T5 任务细则定稿 + 三件套编写
- [ ] Phase 2: 正式实验（200 次运行）
- [ ] Phase 3: 效应分离分析
- [ ] Phase 4: 报告撰写与开源发布

---

## License

MIT

---

> **免责声明**：本项目为个人独立研究，DSH 目前处于 Developer Preview 阶段，实验结果仅供方法参考，不构成对任何产品的商业评价。
