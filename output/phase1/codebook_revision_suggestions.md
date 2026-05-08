# Codebook 修订建议（阶段一自动草案）

以下内容来自探索性词典与分布，**须人工核验**后再写入正式 codebook。

## 1. 关系框定 / 角色化候选

- 词典维度：`athlete`, `hero_progress`, `failure_comedy`, `baby_cute`, `threat_compete`, `product_tech`, `nation_tech`。
- 下一步：对每个维度各抽 20 条高赞评论，合并/拆分为 codebook 中的「关系框定」子类。

### 各类别角色词典均值（全评论层级合并）

```
                role_athlete  role_hero_progress  role_failure_comedy  role_baby_cute  role_threat_compete  role_product_tech  role_nation_tech
post_category                                                                                                                                  
all                 0.039410            0.014560             0.344593        0.052611             0.007765           0.017278          0.012619
humane,nohuman      0.061120            0.030608             0.049884        0.006877             0.011817           0.029155          0.018210
lovely,nohuman      0.025126            0.007897             0.193108        0.194544             0.002872           0.004307          0.002513
strong,human        0.053974            0.023553             0.295388        0.017664             0.026497           0.011776          0.008832
strong,nohuman      0.058120            0.019525             0.133797        0.007870             0.013168           0.019525          0.023309
unknown             0.000000            0.045455             0.045455        0.000000             0.000000           0.090909          0.000000
weak,human          0.010626            0.009052             0.311295        0.030697             0.004723           0.005116          0.005116
weak,nohuman        0.018006            0.008562             0.362251        0.035382             0.004029           0.007177          0.006673
```

## 2. 心智投射 / 拟人化线索候选


- 维度：`pronoun_*`, `kin_terms`, `mind_volition`, `body_pain`, `care_moral`。

- 下一步：与 Phase2「心智属性投射」维度对齐；注意 **人称代词** 与 **亲昵称谓** 应分码。


```
                ph_pronoun_ta_obj  ph_pronoun_ta_m  ph_pronoun_ta_f  ph_kin_terms  ph_mind_volition  ph_body_pain  ph_care_moral
post_category                                                                                                                   
all                      0.013201         0.019414         0.001941      0.008154          0.027179      0.008154       0.005048
humane,nohuman           0.023828         0.037485         0.000872      0.004165          0.027509      0.022375       0.006877
lovely,nohuman           0.030510         0.031945         0.003230      0.046662          0.028356      0.027279       0.003948
strong,human             0.041217         0.043180         0.000000      0.002944          0.033366      0.015702       0.001963
strong,nohuman           0.028303         0.042531         0.000454      0.002422          0.039049      0.016498       0.004843
unknown                  0.000000         0.000000         0.000000      0.000000          0.000000      0.045455       0.000000
weak,human               0.005510         0.014168         0.001968      0.023613          0.024400      0.011413       0.002755
weak,nohuman             0.008688         0.011458         0.001637      0.005918          0.020902      0.027827       0.006673
```

## 3. 人机边界协商候选


```
                bd_human_side  bd_machine_side  bd_contrast_markers
post_category                                                      
all                  0.178800         0.116871             0.006601
humane,nohuman       0.328555         0.189074             0.012786
lovely,nohuman       0.112706         0.059584             0.006461
strong,human         0.230618         0.122669             0.006869
strong,nohuman       0.246405         0.152717             0.011049
unknown              0.090909         0.090909             0.000000
weak,human           0.119638         0.073987             0.003542
weak,nohuman         0.112692         0.067867             0.004281
```

## 4. 玩梗与互动模板


套话模板命中率（`您是…它是…` 类）按类别：

```
post_category
strong,human      0.000981
all               0.000000
humane,nohuman    0.000000
lovely,nohuman    0.000000
strong,nohuman    0.000000
unknown           0.000000
weak,human        0.000000
weak,nohuman      0.000000
```

- 下一步：在 codebook 增加「互文/玩梗」或「套话接龙」标签（二元或多标签）。


## 5. 高回复一级评论（协商与 meme 高发位）


完整列表见 `top_high_reply_l1.csv`。请在编码指南中注明：**一级 vs 二级** 分码。
