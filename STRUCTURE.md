# 目录树

同事对照本文件放文件。**本文件只描述位置，不包含数据。**

操作步骤见 [docs/OPERATING.md](docs/OPERATING.md)。列含义见 [data/canonical_comment_schema.md](data/canonical_comment_schema.md)。

## 不入库

| 类别 | 位置 | 原因 |
|------|------|------|
| 密钥 | `.env` | API key |
| 原始抓取 | `data/rawdata/**` 下的 csv / xlsx / mp4 | 体积大、可重放 |
| 清洗大表 | `data/clean/**/*.csv` 及 `data/demo/**/*.csv` | 由 Phase 1 / demo 脚本生成 |
| 实验产物 | `output/**` 下的 npy、模型、日志、视频缓存 | 可重跑；current 结论已在 registry |
| Notebook | `notebooks/**/*.ipynb` | 诊断用，不是管线入口 |

目录本身用 `.gitkeep` 保留。规则在 [.gitignore](.gitignore)。

## 树

```
robot_failure/
├── CURRENT.md                          # 当前真源入口
├── STRUCTURE.md                        # 本文件
├── run_preprocess.py                   # Phase 1 入口
├── config/
│   ├── post_category_by_post.csv       # XHS 帖子分类
│   ├── post_category/                  # {platform}_{batch}.csv
│   └── topic_modeling/                 # 过滤与停用词
├── data/
│   ├── canonical_comment_schema.md
│   ├── rawdata/                        # 只放原始导出，不改原件
│   │   ├── xhs/
│   │   ├── tiktok/{2604-marathon,2608-olympic}/
│   │   ├── douyin/2608-olympic/
│   │   └── youtube/{2604-marathon,2608-olympic}/
│   │       └── canonical.csv           # 映射后另存，不覆盖原件（本地）
│   ├── clean/{platform}/{batch}/       # Phase 1 只写这里
│   │   ├── clean_comments_unified.csv
│   │   ├── shared_analyzable_corpus.csv
│   │   └── phase1_preprocess_stage_summary.csv
│   └── demo/{platform}_{batch}/        # 阅读/标注抽样，不是主库
├── docs/
│   ├── OPERATING.md
│   └── functions.md
├── human_label_llm/
│   ├── experiment/                     # yaml；勿改 _defaults 的旧入口
│   ├── label_data/gold/                # 人工金标
│   └── output/<run_id>/                # 人机比对，本地
├── output/experiments/<run_id>/        # 主题实验；current 只读
├── phase1/                             # 清洗与主题代码
└── tools/                              # comment_lang、demo、video（点名才跑）
```

批次名：马拉松 `2604-marathon`，运动会 `2608-olympic`。平台名：`xhs` / `tiktok` / `douyin` / `youtube`。
