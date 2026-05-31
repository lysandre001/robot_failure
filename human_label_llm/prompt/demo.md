# eval_object_v1

**一个文件**：[`eval_object_v1.md`](eval_object_v1.md)

- 顶部 `---` … `---`：**版本说明、`label_map`、JSON 解析**（formatter 读取，**不发给模型**）
- 正文 `# ROLE` 起：**实际 prompt**，`{comment}` 等由 experiment `columns` 填槽

实验配置：[`../experiment/`](../experiment/)

```bash
.venv/bin/python -m human_label_llm.run dryrun \
  -c human_label_llm/experiment/20260529_object_v1_comment_only_test.yaml -n 1
```
