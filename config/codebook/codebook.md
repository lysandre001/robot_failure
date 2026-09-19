# 评论码本（论文主测量 · 三层）

真源路径：`config/codebook/`。帖子级 **机器人状态 × 人的形象** 见 `config/post_category/`，仅用于 RQ3 情境横切，**不是**本码本字段。

列名与旧表别名见 [label_map.yaml](label_map.yaml)。

## 1. 主体（评论在评谁 / 评什么）

封闭七类（与 `human_label_llm` 评估对象一致）：

| 标签 | 含义 |
|------|------|
| 机器人本身 | 直接评价机器人实体、表现、能力 |
| 自身经验 | 评论者自身经历、立场、身份 |
| 符号 | 隐喻、梗、文化符号 |
| 事件 | 赛事、新闻事件、场景 |
| 其他人 | 人类他人、组织、国家等 |
| 无主体 | 无明确评价对象 |
| 其他 | 以上均不贴切 |

Gold 列名：**`主体`**（兼容 **`评估对象`**）。

## 2. 观念（立场与理由域）

### 2.1 立场 `stance`

| 值 | 定义 |
|----|------|
| 支持 | 肯定能力、进步、可爱、有意义、辩护 |
| 反对 | 嘲讽、否定、质疑造假、排斥、恐惧 |
| 中立 | 陈述、提问、调侃难判（须 reason） |

### 2.2 理由极性 `d1`–`d4`

各维独立：`Pos` | `Neg` | `N/A`（未涉及）。

| 列 | 问什么 |
|----|--------|
| d1 | 技术能力（速度、稳定性、工程） |
| d2 | 情感卷入（可爱、好笑、可怜、喜爱、厌恶） |
| d3 | 社会价值（进步、浪费、就业、伦理） |
| d4 | 人类影响（地位、替代、威胁、照护） |

### 2.3 可选：`figure_code`（机器人被看成什么）

附录或 RQ2 细化用，**不与主体七类混报**。枚举见 [data/clean/label_codebook_llm.md](../../data/clean/label_codebook_llm.md) 的 `llm_figure_code` 表。

## 3. 情感

封闭四类，Gold 列名 **`情感`**（兼容 `情感(p/neg/n/m)`）：

`Positive` | `Negative` | `Neutral` | `Mixed`（首字母大写）

## 4. 语言与模型输入

| 平台 | 模型读列 | Prompt 语言 |
|------|----------|-------------|
| xhs, douyin | `content` | 中文 |
| tiktok, youtube | `content_en` | 英文（缺译先跑 `tools.comment_lang`） |

实现：`human_label_llm/labeling_paths.py` + experiment yaml 的 `platform` / `data.text_column`。
