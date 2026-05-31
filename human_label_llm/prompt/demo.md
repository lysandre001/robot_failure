# Prompt 与 experiment 一一对应

| 输入条件 | prompt 文件 | experiment 别名 |
|----------|-------------|-----------------|
| 仅评论 | `eval_object_v1_comment_only.md` | `object` |
| 评论 + video caption | `eval_object_v1_comment_caption.md` | `object_caption` |
| 仅评论 | `eval_emotion_v1_comment_only.md` | `emotion` |
| 评论 + video caption | `eval_emotion_v1_comment_caption.md` | `emotion_caption` |

```bash
python human_label_llm/run_experiment.py dryrun object -n 1
python human_label_llm/run_experiment.py dryrun object_caption -n 1
```
