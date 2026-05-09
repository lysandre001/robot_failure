# Phase1 预处理阶段汇报（步骤 A）

## 阶段汇总
```
                   stage                  description  rows  unique_posts unique_comment_id comment_level missing_content missing_content_rate
             A0_raw_main                原始主表（小红书帖子数据） 36867            16              <NA>          <NA>            <NA>                 <NA>
      A1_merged_category 主表合并 post_category（含按帖子id覆写） 36867            16              <NA>          <NA>            <NA>                 <NA>
             A2_l1_dedup                 一级评论去重后（未过滤） 18893            16             18893             1              53             0.002805
             A3_l2_dedup                 二级评论去重后（未过滤） 17499            16             17499             2             161             0.009201
A4_unified_before_filter             一级+二级统一评论长表（过滤前） 36392            16             36392           1+2             214              0.00588
 A5_unified_after_filter     统一评论长表（过滤后：空值/最小长度/重复字符） 31245            16             31245           1+2               0                  0.0
      A6_l1_after_filter                    一级评论（过滤后） 16808            16             16808             1               0                  0.0
      A7_l2_after_filter                    二级评论（过滤后） 14437            16             14437             2               0                  0.0
```

## 关键键与去重检查 + 过滤效果
```
 counts_post_id_duplicated  l1_comment_id_duplicated_after_dedup  l2_comment_id_duplicated_after_dedup  l2_orphan_parent_comment_id  filtered_removed_total  filtered_removed_l1  filtered_removed_l2
                         0                                     0                                     0                            0                    5147                 2085                 3062
```
