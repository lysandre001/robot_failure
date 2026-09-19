# Phase1 stage summary

- platform: youtube
- source_batch: 2604-marathon
- raw_input: /Users/yilin/Desktop/project/robot_failure/data/rawdata/youtube/2604-marathon/canonical.csv
- clean_dir: /Users/yilin/Desktop/project/robot_failure/data/clean/youtube/2604-marathon

                   stage                       description  rows  unique_posts  unique_comment_id                                                     notes
A4_unified_before_filter                一二级合并长表（Phase1过滤前） 28664           322              28664 L1=17154; L2=11510; platform=youtube; batch=2604-marathon
 A5_unified_after_filter Phase1过滤后（clean_comments_unified） 23350           313              23350  L1=16739; L2=6611; platform=youtube; batch=2604-marathon
        A6_shared_corpus      主题建模shared analyzable corpus 20874           313              20874                     platform=youtube; batch=2604-marathon
