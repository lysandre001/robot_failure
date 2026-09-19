# Phase1 stage summary

- platform: youtube
- source_batch: 2608-olympic
- raw_input: /Users/yilin/Desktop/project/robot_failure/data/rawdata/youtube/2608-olympic/canonical.csv
- clean_dir: /Users/yilin/Desktop/project/robot_failure/data/clean/youtube/2608-olympic

                   stage                       description  rows  unique_posts  unique_comment_id                                                    notes
A4_unified_before_filter                一二级合并长表（Phase1过滤前） 63209           694              63209 L1=41879; L2=21330; platform=youtube; batch=2608-olympic
 A5_unified_after_filter Phase1过滤后（clean_comments_unified） 53252           674              53252 L1=41216; L2=12036; platform=youtube; batch=2608-olympic
        A6_shared_corpus      主题建模shared analyzable corpus 48235           674              48235                     platform=youtube; batch=2608-olympic
