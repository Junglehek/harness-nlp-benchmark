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

### 核心矩阵（3 条件 + 动态升级）

| 条件 | Harness | 底层模型 | 测量目标 |
|:---:|:---|:---|:---|
| A | DeepSeek Harness | DeepSeek-V4 | 基线 |
| B | DeepSeek Harness | GPT-5.6 Terra | **模型效应**（同 harness，换模型） |
| C | OpenAI Codex | GPT-5.6 Terra | **Harness 效应**（同模型，换 harness） |

> **动态升级**：Phase 1 实测 Codex 能否接入 DeepSeek-V4。若验证通过，升级为 **2×2 全交叉（+ 条件 D：Codex+V4，共 60 次运行）**，效应分离更严谨；若失败，保持 3 条件（45 次运行）。

### 控制变量
- **超时**：10 分钟/任务
- **Token 预算**：100K/任务
- **初始状态**：每次运行前由 `fixtures/` 重置
- **评估协议**：自动 Oracle (`evaluator.py`) + LLM-as-Judge (`rubric.md`)

---

## 评测任务（5 个）

| # | 任务 | 类型 | 难度 | Oracle 自动化率 |
|:---:|:---|:---|:---:|:---:|
| T1 | Brown Corpus 文体关键词提取 | 语料库分析 | ⭐⭐ | 60% |
| T2 | LCMC 中英文句长对比 | 跨语言对比 | ⭐⭐⭐ | 70% |
| T3 | CLUENER 2020 中文 NER | 命名实体识别 | ⭐⭐⭐ | 90% |
| T4 | WMT19 平行语料质量筛选（抽样 1K） | 双语对齐检查 | ⭐⭐⭐ | 70% |
| T5 | ChnSentiCorp 中文情感分析 | 文本分类 | ⭐⭐ | 90% |

> 覆盖：分类 / NER / 情感 / 对齐，中英双语，⭐⭐~⭐⭐⭐ 梯度。

---

## 快速开始（复现）

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/harness-nlp-benchmark.git
cd harness-nlp-benchmark

# 2. 安装依赖
# DSH: Node.js 20+, npm install -g @deepseek-ai/dsh
# Codex: 按官方文档配置 CLI
# Python: pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 OPENAI_API_KEY

# 4. 运行单个任务预实验
python scripts/run_task.py --task t5_chnsenticorp --condition A --dry-run

# 5. 运行完整评测
# 3 条件：5 任务 × 3 条件 × 3 遍 = 45 次
# 2×2 全交叉（若条件 D 验证通过）：5 任务 × 4 条件 × 3 遍 = 60 次
python scripts/run_benchmark.py --config benchmark.yaml
```

> 详细环境配置见 [docs/setup.md](docs/setup.md)

---

## 仓库结构

```
harness-nlp-benchmark/
├── tasks/                    # 标准化任务目录
│   ├── t1_brown_corpus/
│   │   ├── README.md         # 自然语言任务描述（Agent 输入）
│   │   ├── data/             # 输入数据集（只读）
│   │   ├── fixtures/         # 初始工作区
│   │   ├── evaluator.py      # 自动评分 Oracle
│   │   └── rubric.md         # LLM-as-Judge 评分标准
│   ├── t2_lcmc/
│   ├── t3_cluener/
│   ├── t4_wmt19/
│   └── t5_chnsenticorp/
├── scripts/                  # 运行与评测脚本
│   ├── run_task.py
│   ├── run_benchmark.py
│   └── evaluate.py
├── results/                  # 运行结果与轨迹
│   ├── pilot/                # 预实验数据
│   └── final/                # 正式实验数据
├── log/                      # 开发过程记录
├── docs/                     # 文档
│   └── setup.md
├── benchmark.yaml            # 实验矩阵配置
├── report.md                 # 最终报告（撰写中）
└── README.md                 # 本文件
```

---

## 初步结果（待更新）

| 指标 | DSH-V4 (A) | DSH-Terra (B) | Codex-Terra (C) | Codex-V4 (D) |
|:---|:---:|:---:|:---:|:---:|
| T5 成功率 | — | — | — | 动态条件 |
| T5 平均步数 | — | — | — | 动态条件 |
| T5 平均 Token | — | — | — | 动态条件 |
| **模型效应** | — | — | — | — |
| **Harness 效应** | — | — | — | — |

> 预实验进行中，预计 2026-08-30 更新首批数据。

---

## 核心发现（撰写中）

- 🔍 **模型效应**：同 harness 下，换模型对 NLP 数据工程任务的影响程度？
- 🛠️ **Harness 效应**：同模型下，DSH 与 Codex 在工具选择、错误恢复、代码质量上的差异？
- 📊 **任务差异**：哪些任务对 harness 设计更敏感？

---

## 技术栈

- **Agent 框架**：DeepSeek Harness (v0.1.0), OpenAI Codex CLI
- **模型后端**：DeepSeek-V4, GPT-5.6 Terra
- **评测**：dsh-eval, custom `evaluator.py`, Claude Sonnet (LLM-as-Judge, temperature=0)
- **语言**：Python 3.10+, Node.js 20+
- **数据**：HuggingFace Datasets, statmt.org

---

## 预算

- **3 条件（45 次运行）**：约 ¥100 以内
- **2×2 全交叉（60 次运行，若条件 D 验证通过）**：约 ¥85–120
- 预实验（T5 × 3 条件 × 1 遍）先实测单次成本，再决定全量规模

---

## 引用

如果你参考了本项目的方法或数据，请引用：

```bibtex
@misc{harness-nlp-benchmark,
  title={Harness-NLP-Benchmark: A Pilot Study on Harness Effects in NLP Data Engineering},
  author={<你的名字>},
  year={2026},
  howpublished={\url{https://github.com/<你的用户名>/harness-nlp-benchmark}},
}
```

**相关文献**：
- Yao, Y., et al. (2026). Harness-Bench: Measuring harness effects across models in realistic agent workflows. *arXiv preprint* arXiv:2605.27922.

---

## 进度

- [x] 实验设计定稿（2026-08-23）
- [x] GitHub 仓库 + README 发布（2026-08-23）
- [ ] Phase 1: 环境准备与预实验
- [ ] Phase 2: 基线测试（45/60 次运行）
- [ ] Phase 3: 效应分离分析
- [ ] Phase 4: 报告撰写与开源发布

---

## License

MIT

---

> **免责声明**：本项目为个人独立研究，DSH 目前处于 Developer Preview 阶段，实验结果仅供方法参考，不构成对任何产品的商业评价。
