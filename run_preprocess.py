#!/usr/bin/env python3
"""Phase 1 评论清洗流水线入口。

稳定管线第 1 步：读 Excel → 去重 → 噪音过滤 → 写出 clean_comments_unified.csv。
详见 phase1/RUNBOOK.md 与 writing/data_preprocessing_protocol.md。
"""
from phase1.pipeline import main

if __name__ == "__main__":
    main()
