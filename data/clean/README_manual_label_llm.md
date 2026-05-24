# LLM 辅助人工标注样本打标

对 [`manual_label_l1_30perpost.csv`](manual_label_l1_30perpost.csv) 的一级评论 `content` 做四维 LLM 打标，输出带 25 列 LLM 字段的 [`manual_label_l1_30perpost_llm.csv`](manual_label_l1_30perpost_llm.csv)（原列保留）。

## 复现命令

```bash
cd /Users/yilin/Desktop/project/robot_failure
source .venv/bin/activate
pip install 'openai>=1.0.0'

# 试跑 100 条（默认）
python -m phase1.label_manual_comments \
  --limit 100 \
  --relic-env-dir /Users/yilin/Desktop/project/relic3/relic_3.0_test

# 全量 945 条（断点续跑）
python -m phase1.label_manual_comments --limit 0 --resume
```

## API 密钥（只读 relic3，不修改 relic3）

脚本按顺序加载 `relic_3.0_test/.env` 与 `relic_3.0_test/scripts/.env`，解析优先级：

1. `DEEPSEEK_API_KEY` → `https://api.deepseek.com`，`deepseek-v4-pro`
2. `OPENROUTER_API_KEY` → `deepseek/deepseek-v4-pro`
3. `SILICONFLOW_API_KEY` → 警告后降级 `deepseek-ai/DeepSeek-V3`

日志仅打印 `provider` / `model`，不输出密钥。

## 输出列（25 列 LLM）

| 层次 | 列 | 说明 |
|------|-----|------|
| A 关系想象 | `llm_figure_code`, `llm_figure_label`, `llm_figure_reason`, `llm_figure_display` | 受控码 + 中文标签 + 原因；display=`【标签】原因` |
| B 立场 | `llm_stance`, `llm_stance_reason`, `llm_stance_display` | `支持` / `中立` / `反对` |
| C 情感 | `llm_emotion`, `llm_emotion_valence`, `llm_emotion_reason`, `llm_emotion_display` | 开放情感词；valence: positive/negative/mixed/neutral |
| D 四维 | `llm_d1`–`llm_d4`, `llm_d1_reason`–`llm_d4_reason`, `llm_dimensional_display` | 每维 `Pos` / `Neg` / `N/A` |
| Meta | `llm_provider`, `llm_model`, `llm_labeled_at`, `llm_parse_ok`, `llm_error` | |

码本释义见 [`label_codebook_llm.md`](label_codebook_llm.md)。

## 断点与 QC

- Checkpoint：`label_checkpoint.jsonl`（每行含 `comment_id`, `raw_json`, `labels`, `parse_ok`, `error`）
- `--resume` 跳过已成功 `comment_id`
- 脚本结束打印 stance/figure/D1–D4 分布与 5 条随机 spot-check

## 试跑结果（2026-05-19，n=100）

- 成功率：100%
- `llm_stance`：中立 64 / 支持 27 / 反对 9
- 主要 `llm_figure_code`：competitor 48, spectacle 21, patient 12
- 模型：`deepseek` / `deepseek-v4-pro`，`temperature=0`

## Git

`label_checkpoint.jsonl` 与 `*_llm.csv` 已在根目录 `.gitignore` 中忽略（含评论原文）。

## 实现

[`phase1/label_manual_comments.py`](../../phase1/label_manual_comments.py)
