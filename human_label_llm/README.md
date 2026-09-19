# Human vs LLM 标注比对

**入口**：[README.md](../README.md) · **实验 yaml / registry**：[experiment/README.md](experiment/README.md) · **金标协议**：[label_data/GOLD_PROTOCOL.md](label_data/GOLD_PROTOCOL.md)

```bash
python human_label_llm/run_experiment.py dryrun -c human_label_llm/experiment/<yaml>
python human_label_llm/run_experiment.py infer -c human_label_llm/experiment/<yaml>
python human_label_llm/run_experiment.py compare -c human_label_llm/experiment/<yaml>
```

新任务：复制 `experiment/_labeling_template.yaml` → 登记 `experiment/registry.csv` → 勿改 `experiment/_defaults.yaml`。

Prompt：`prompt/{layer}_{zh|en}.md` 或 legacy `eval_*`。平台与文本列：`labeling_paths.py`。
