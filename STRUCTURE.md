# 项目结构（可复现流水线）

> 脚本完整索引见 [`tools/README.md`](tools/README.md)。

## 目录

| 路径 | 作用 |
|------|------|
| `run_preprocess.py` | **Phase 1 清洗入口**（`run_phase1.py` 为兼容别名） |
| `phase1/pipeline.py` | 清洗流水线编排 |
| `phase1/preprocess.py` | 读 Excel、合并类别、去重、统一表 |
| `phase1/comment_content_filter.py` | 评论噪音规则（库 + 可被 audit 工具调用） |
| `phase1/topic_modeling.py` | **主题建模主入口**（shared corpus + LDA/NMF/BERTopic） |
| `phase1/topic_lda.py` | 分词、停用词 |
| `phase1/topic_visualize.py` | BERTopic 可视化 |
| `phase1/keyword_filter.py` | 关键词探索（`output/explore/`） |
| `phase1/xhs_io.py` | 小红书 raw 导入/合并（库） |
| `tools/` | 一次性导入、辅助导出、ad-hoc 分析 CLI |
| `config/` | 帖子编码、噪音规则 JSON |
| `data/clean/` | canonical 清洗产物 |
| `output/phase1/` | 清洗流水线输出 |
| `output/experiments/` | 正式主题建模实验 |
| `output/explore/` | 关键词探索临时产物 |

## 命令

```bash
cd /Users/yilin/Desktop/project/robot_failure
source .venv/bin/activate

# 清洗
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx

# 主题建模
PYTHONUNBUFFERED=1 python -m phase1.topic_modeling --device cpu \
  --input-csv data/clean/clean_comments_unified.csv --run-id <run_id>

# 辅助导出
python -m tools.export_comments_per_post
```

详见 [`phase1/RUNBOOK.md`](phase1/RUNBOOK.md)。
