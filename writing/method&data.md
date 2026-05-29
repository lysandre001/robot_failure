# 方法与数据（草稿）

数据下载与预处理的全文级说明见：

- **[data/clean/data_preprocessing_protocol.md](../data/clean/data_preprocessing_protocol.md)**（正文 Methods 段落 + 附录表稿，与代码一致）
- 阶段计数表：[data/clean/phase1_preprocess_stage_summary.csv](../data/clean/phase1_preprocess_stage_summary.csv)

**摘要**：理论抽样 16 帖 + anchor 17 帖 → Phase 1 清洗 **46,051** 条评论 → 主题建模 shared corpus **28,055** 条（两批适用同一套清洗函数；第二批仅在 CSV 导入阶段额外容错）。

---

数据下载（待与正式稿对齐）

数名研究员在一周的时间里，通过搜索机器人「马拉松」等关键词进行检索，并以目的性抽样选取帖子。合并语料共 **33** 帖（第一批理论抽样 **16** 帖，第二批 anchor **17** 帖）。预处理包括：宽表拆分为一、二级评论并按评论 ID 去重、空内容与可配置噪音规则过滤；主题建模前另设 shared corpus 筛选（最短长度、有效词数、全库正文去重等），详见上述 protocol 文档。

