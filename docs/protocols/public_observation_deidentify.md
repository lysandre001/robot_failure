# 公开评论观察（IRB 8a）脱敏与排除规则

与线上面板观察一致：**仅公开可见文本**；不把个人当作研究参与者。实现见 `phase1/deidentify.py`、`phase1/comment_content_filter.py`、`phase1/pipeline.py`。

## 采集边界（流程外）

- 不抓私密群、不登录受限内容、不与用户互动、不识别账号。
- 不采集头像、图片、个人主页。
- 宽表 raw 可含平台导出列（含用户 id、昵称、IP 属地）；**昵称类列不进入 clean 长表**（当前 `build_level1/2` 未映射 `*用户名`）。

## 评论排除（Phase 1 过滤）

配置：[config/topic_modeling/comment_content_filter.json](../../config/topic_modeling/comment_content_filter.json)

| 规则 | 行为 |
|------|------|
| `contains_mention` | 正文含 `@` / `＠` → **整句排除** |
| `only_mentions` | 去掉 @ 后无实质内容 → 排除 |
| 其它 | 纯 emoji、重复片段、英文套话等（见 gate 文档） |

## 脱敏（raw → clean 写出前）

| 项 | 做法 |
|----|------|
| `user_id` | 从所有 **public** clean/shared/demo 表移除 |
| `location`（评论 IP/地址） | 同上 |
| 侧车文件 | `data/clean/{platform}/{batch}/comment_pii_sidecar.csv`：`comment_id` + `user_id` + `location` + `platform` + `source_batch`，**仅本地质控/去重**，不出现在发表、demo、gold 交回模板、分析产物 |
| 发表引用 | 英译 + 必要时轻度改写；汇总报告（主题、情感、分布） |

## 重跑

改规则或脱敏逻辑后对该 batch **重跑** `run_preprocess.py`。旧 clean 若仍含 `user_id`/`location` 列，视为脱敏前快照。

## 索引

[docs/registry.md](../registry.md) → `public_observation`
