# COLUMN_MAP — YouTube harvest → canonical wide table

| Export column (canonical) | Source |
|---------------------------|--------|
| 帖子id | videos.video_id |
| 帖子链接 | videos.video_url or `https://www.youtube.com/watch?v={id}` |
| 用户id | videos.channel_id |
| 帖子用户名 | videos.channel_title |
| 帖子类型 | constant `video` |
| 帖子标题 | videos.title |
| 帖子发布时间 | videos.published_at (normalized) |
| 帖子正文 | videos.description |
| 帖子话题 | videos.tags |
| 帖子IP属地 | videos.channel_country |
| 帖子评论数 | videos.comment_count |
| 帖子点赞数 | videos.like_count |
| 帖子转发数 | (empty) |
| 帖子收藏数 | (empty) |
| 一级评论用户名 | comments.author_display_name |
| 一级评论用户id | comments.author_channel_id |
| 一级评论内容 | comments.text |
| 一级评论时间 | comments.published_at (normalized) |
| 一级评论地址 | comments.author_channel_country |
| 一级评论点赞数 | comments.like_count |
| 一级评论回复数 | count of harvested L2 under this L1 |
| 一级评论id | comments.comment_id (top-level) |
| 一级评论图片链接 | (empty) |
| 二级评论用户名 | comments.author_display_name |
| 二级评论用户id | comments.author_channel_id |
| 二级评论内容 | comments.text |
| 二级评论时间 | comments.published_at (normalized) |
| 二级评论地址 | comments.author_channel_country |
| 二级评论点赞数 | comments.like_count |
| 二级评论id | comments.comment_id (reply) |
| 二级评论图片链接 | (empty) |
