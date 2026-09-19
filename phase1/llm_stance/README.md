# LLM Stance Annotation Pipeline (OpenRouter)

> **archived**：历史三模型 stance 宽表；新任务走 `human_label_llm/run_experiment.py` 与 `config/codebook/`。

最小可跑的三模型 stance 标注流水线。输入是双人标注 Excel，输出是
每个模型一份 JSONL（断点续跑），最后合并成宽 CSV 供论文统计使用。

## 目标模型（OpenRouter slug）

| 论文里写的名字 | OpenRouter slug（默认，按需改） |
|---|---|
| Claude 4.7   | `anthropic/claude-sonnet-4.7` |
| GPT 5.5      | `openai/gpt-5.5`             |
| Gemini 3.1   | `google/gemini-3.1-pro`      |

> ⚠️ 不同时间 OpenRouter slug 会变。**跑前到 https://openrouter.ai/models 复制
> 当前真正可用的 slug**，写进 `MODELS` 字典或用 `--models` 参数覆盖。

## 一次性准备

```bash
cd /Users/yilin/project/2604-robotic_failure_research
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 安装本流水线额外依赖
pip install requests python-dotenv tqdm

# 在 phase1/llm_stance/ 下建一个 .env（不入 git）
echo 'OPENROUTER_API_KEY=sk-or-...' > phase1/llm_stance/.env
```

## 跑

```bash
# 1. 三模型并行标注（每模型一份 JSONL，断点续跑）
python -m phase1.llm_stance.annotate \
  --input  /Users/yilin/Desktop/research_writing/overleaf/robostance-emnlp/resource/双人标注label_l1_30perpost_llm\(1\).xlsx \
  --outdir phase1/llm_stance/output \
  --workers 8

# 中途断了再跑一次同样命令会跳过已标条目。

# 2. 合并三模型 + 三人类标签 → 一张宽 CSV
python -m phase1.llm_stance.aggregate \
  --input  /Users/yilin/Desktop/research_writing/overleaf/robostance-emnlp/resource/双人标注label_l1_30perpost_llm\(1\).xlsx \
  --jsonl-dir phase1/llm_stance/output \
  --out    phase1/llm_stance/output/stance_wide.csv
```

输出 `stance_wide.csv` 列：

```
comment_id, post_id, post_category, content,
human1, human2, llm_orig,
claude_4_7, gpt_5_5, gemini_3_1,
claude_4_7_reason, gpt_5_5_reason, gemini_3_1_reason
```

直接喂给论文统计脚本（per-model κ、混淆矩阵、majority-vote gold 等）。

## 设计要点

- **无 SDK 依赖**：只用 `requests` 直打 OpenRouter `/chat/completions`，
  避免 anthropic/openai SDK 各家 breaking change。
- **断点续跑**：每条评论一行 JSONL，写入前检查 `comment_id` 是否已在文件里。
- **结构化输出**：prompt 要求 JSON，解析失败时**重试一次**，再失败记
  `stance=PARSE_ERROR` 并保留原文便于事后修补。
- **并发但温和**：默认 8 个 worker，失败指数退避 + jitter。
- **prompt 与论文 Appendix B 一致**：见 `prompts.py`，改 prompt 时同步
  修改论文。
