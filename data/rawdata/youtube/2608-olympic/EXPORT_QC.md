# Export QC — YouTube 2608-olympic

- Generated: 2026-09-19T14:01:38
- Harvest: `/Users/yilin/project/社交媒体爬虫/youtube爬虫方案/data/output/whrg_hashtag__2608`
- Source: experiment whrg_hashtag__2608 (World Humanoid Robot Games window)
- Filter: videos with ≥1 harvested comment in comments.csv

## Counts

| metric | value |
|--------|------:|
| videos in harvest | 1290 |
| comments in harvest | 63231 |
| videos exported (with comments) | 695 |
| orphan comments (no video row) | 0 |
| wide table rows | 63208 |
| L1-only rows | 41879 |
| L2 reply rows | 21329 |

## Required fields

| check | count (must be 0) |
|-------|------------------:|
| empty 帖子id | 0 |
| empty 一级评论id | 0 |
| empty 一级评论内容 | 0 |
| L2 without parent_id in source | 0 |
| skipped empty comment text | 14 |

## Column count

- Header columns: **31** (robot_failure wide_io EXPECTED_WIDE_COLS=31)

## Downstream note

robot_failure `run_preprocess.py --platform youtube` is not wired yet; `wide_io.is_valid_wide_post_id` rejects alphanumeric YouTube ids until adapted.
