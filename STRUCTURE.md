# 项目结构（可复现流水线）

## 目录

| 路径 | 作用 |
|------|------|
| `小红书帖子数据.xlsx` | 原始数据（不入库） |
| `phase1/config.py` | 根路径、`output/phase1`、Matplotlib |
| `phase1/lexicons.py` | 探索性词典（可迭代） |
| `phase1/preprocess.py` | **步骤 A**：读 Excel、合并类别、去重、统一表 |
| `phase1/features.py` | **步骤 B**：词典命中与玩梗特征 |
| `phase1/analysis.py` | **步骤 C**：统计图、共现、主题聚类、辅助 CSV |
| `phase1/reports.py` | **步骤 D**：质量说明、摘要、codebook 草案 |
| `phase1/pipeline.py` | 串联 1–8 步 |
| `run_phase1.py` | 入口：`python run_phase1.py` |
| `notebooks/phase1_structured.ipynb` | 与上同序的分步 Notebook |
| `output/phase1/` | 全部产物（CSV / MD / PNG / JSON） |

## 命令

```bash
cd /Users/yilin/Desktop/project/robot_failure
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_phase1.py
jupyter notebook notebooks/phase1_structured.ipynb
```
