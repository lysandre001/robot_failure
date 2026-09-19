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

## 用户级去重（进入 analysis clean 前）

在 Phase 1 内容过滤 **之后**、写出 `clean_comments_unified.csv` **之前**（`phase1/deidentify.py` → `dedupe_user_identical_content`）：

| 规则 | 行为 |
|------|------|
| 刷屏 | 同一 **非空** `user_id` + **规范化后相同** `content` → 只保留 `comment_id` 最早一条，其余删除 |
| 无 `user_id` | 不参与此去重（评论仍可在 clean 中） |

**分析用 clean 不含**「同用户重复粘贴」的多条副本。去重条数与 **独立用户数** 写入 `comment_deidentify_report.json`（字段 `removed_user_identical_content`、`n_distinct_user_id`），供论文 aggregate 表述；**不**在发表表导出 `user_id`。

独立用户数定义：final clean 中 **非空平台 user_id** 的 `nunique`（侧车与报告一致，仅本地）。

## 脱敏（raw → clean 写出前）

| 项 | 做法 |
|----|------|
| `user_id` | 从所有 **public** clean/shared/demo 表移除 |
| `location`（评论 IP/地址） | 同上 |
| 侧车文件 | `comment_pii_sidecar.csv`：与 **去重后** final clean 行一一对应；仅本地质控 |
| 发表引用 | 英译 + 必要时轻度改写；汇总报告（主题、情感、分布、独立用户数） |

## 重跑

改规则或脱敏逻辑后对该 batch **重跑** `run_preprocess.py`。旧 clean 若仍含 `user_id`/`location` 列，视为脱敏前快照。

## 索引

[docs/registry.md](../registry.md) → `public_observation`
