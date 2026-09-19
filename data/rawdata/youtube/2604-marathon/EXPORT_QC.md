# Export QC — YouTube 2604-marathon

- Generated: 2026-09-19T14:01:36
- Harvest: `/Users/yilin/project/社交媒体爬虫/youtube爬虫方案/data/output/beijing_robot_marathon_exp__2604`
- Source: experiment beijing_robot_marathon_exp__2604 (matches configs/beijing_robot_marathon.yaml window)
- Filter: videos with ≥1 harvested comment in comments.csv

## Counts

| metric | value |
|--------|------:|
| videos in harvest | 552 |
| comments in harvest | 28671 |
| videos exported (with comments) | 322 |
| orphan comments (no video row) | 0 |
| wide table rows | 28663 |
| L1-only rows | 17154 |
| L2 reply rows | 11509 |

## Required fields

| check | count (must be 0) |
|-------|------------------:|
| empty 帖子id | 0 |
| empty 一级评论id | 0 |
| empty 一级评论内容 | 0 |
| L2 without parent_id in source | 0 |
| skipped empty comment text | 2 |

## Column count

- Header columns: **31** (robot_failure wide_io EXPECTED_WIDE_COLS=31)

## Downstream note

robot_failure `run_preprocess.py --platform youtube` is not wired yet; `wide_io.is_valid_wide_post_id` rejects alphanumeric YouTube ids until adapted.
