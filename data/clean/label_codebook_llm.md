# LLM 打标受控码本

与 `phase1/label_manual_comments.py` 中 system prompt 一致，供论文附录与人工改码对照。

## `llm_figure_code`

| code | 中文参考标签 | 选用线索 |
|------|--------------|----------|
| `competitor` | 竞争者/被超越对象 | 比速度、比人类、马拉松胜负 |
| `threat` | 威胁/不安对象 | 失业、取代人类、恐怖谷 |
| `pet_cute` | 可爱宠物/孩童式 | 萌、可怜、想养 |
| `tool` | 工具/道具 | 遥控器、演示装置、技术展品 |
| `patient` | 照护/救助对象 | 摔倒、失败、加油救治 |
| `fraud_fake` | 造假/噱头 | 假的、摆拍、营销剧本 |
| `spectacle` | 奇观/节目 | 看热闹、玩梗、娱乐消费 |
| `personified_peer` | 拟人同伴 | 当人/同事/选手对话 |
| `other` | 其他 | 以上不贴切；`llm_figure_label` 写概括（≤20 字） |

## `llm_stance`

| 值 | 定义 |
|----|------|
| `支持` | 肯定能力、进步、可爱、有意义、辩护 |
| `反对` | 嘲讽、否定价值、质疑造假、排斥、恐惧 |
| `中立` | 陈述、提问、调侃难判；须在 reason 说明 |

## `llm_emotion_valence`

`positive` | `negative` | `mixed` | `neutral`（`llm_emotion` 本身开放用词）

## `llm_d1`–`llm_d4`（Polarity）

| 维 | 英文键 | 问什么 |
|----|--------|--------|
| D1 | Technical Capability | 速度、稳定性、工程水平 |
| D2 | Affective Engagement | 可爱、好笑、可怜、喜爱、厌恶 |
| D3 | Societal Value | 科技进步、意义、浪费、就业、伦理 |
| D4 | Human Impact | 人类地位、替代、威胁、照护 |

极性：`Pos`（积极）| `Neg`（消极）| `N/A`（未涉及）。各维独立标注。
