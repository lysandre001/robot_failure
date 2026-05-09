# 实验输出入口

**关系分析等「可引用结论」**：只看本目录下某个 `YYYY-MM-DD_*` 子文件夹。

1. 打开同目录的 `registry.csv`，找到最新一行里的 `output_dir`（或 `run_id`）。
2. 进入该文件夹，先读 **`summary.md`**，再看 **`config.json`**（输入数据与词表哈希）、**`metrics.csv`**。
3. 具体表：`relation_v1_*.csv` 等均在同一 run 目录内。

**Phase1 清洗表与图表**（与单次实验 run 分开）：`../phase1/`（如 `clean_comments_unified.csv`、`figures/`）。

**Notebook 一键**：`phase1/notebook_one_click.py` 中的 `run_notebook(CFG)`；配置见 `notebooks/phase1_structured.ipynb` 前几格。
