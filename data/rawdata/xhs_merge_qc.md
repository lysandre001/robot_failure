# 第二批 CSV 清洗 QC

- 生成时间：2026-05-19T19:16:41
- 输入：`/Users/yilin/Desktop/project/robot_failure/2-小红书帖子数据.csv`
- 输出：`/Users/yilin/Desktop/project/robot_failure/data/rawdata/xhs_batch2_wide_sanitized.csv`

## 统计

| 指标 | 值 |
|------|-----|
| 原始字节 | 25,980,182 |
| 移除 NUL | 6,610,790 |
| 保留行 | 20,988 |
| 跳过行 | 1,568 |
| 唯一帖子数 | 17 |

## 跳过行字段数分布（前 20）

- `wrong_field_count`：1568 行
- 字段数 `1`：894 行
- 字段数 `0`：670 行
- 字段数 `2`：1 行
- 字段数 `9`：1 行
- 字段数 `45`：1 行
- 字段数 `29`：1 行

## 跳过行样例（行号, 列数, 原因）

- L135: 2 列, wrong_field_count
- L136: 1 列, wrong_field_count
- L137: 0 列, wrong_field_count
- L138: 1 列, wrong_field_count
- L139: 0 列, wrong_field_count
- L140: 1 列, wrong_field_count
- L141: 0 列, wrong_field_count
- L142: 1 列, wrong_field_count
- L143: 1 列, wrong_field_count
- L144: 0 列, wrong_field_count
- L145: 1 列, wrong_field_count
- L146: 0 列, wrong_field_count
- L147: 1 列, wrong_field_count
- L148: 0 列, wrong_field_count
- L149: 1 列, wrong_field_count
- L150: 1 列, wrong_field_count
- L151: 0 列, wrong_field_count
- L152: 1 列, wrong_field_count
- L153: 0 列, wrong_field_count
- L154: 1 列, wrong_field_count
- L155: 0 列, wrong_field_count
- L156: 1 列, wrong_field_count
- L157: 1 列, wrong_field_count
- L158: 0 列, wrong_field_count
- L159: 1 列, wrong_field_count
- L160: 0 列, wrong_field_count
- L161: 1 列, wrong_field_count
- L162: 0 列, wrong_field_count
- L163: 1 列, wrong_field_count
- L164: 1 列, wrong_field_count
- L165: 0 列, wrong_field_count
- L166: 1 列, wrong_field_count
- L167: 0 列, wrong_field_count
- L168: 1 列, wrong_field_count
- L169: 0 列, wrong_field_count
- L170: 1 列, wrong_field_count
- L171: 1 列, wrong_field_count
- L172: 0 列, wrong_field_count
- L173: 1 列, wrong_field_count
- L174: 0 列, wrong_field_count
- L175: 1 列, wrong_field_count
- L176: 0 列, wrong_field_count
- L177: 1 列, wrong_field_count
- L178: 1 列, wrong_field_count
- L179: 0 列, wrong_field_count
- L180: 1 列, wrong_field_count
- L181: 0 列, wrong_field_count
- L182: 1 列, wrong_field_count
- L183: 0 列, wrong_field_count
- L184: 1 列, wrong_field_count
