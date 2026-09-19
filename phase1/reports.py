"""步骤 D：数据质量说明与 Markdown 报告。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from phase1.config import OUT


def write_data_quality(
    main: pd.DataFrame,
    l1: pd.DataFrame,
    l2: pd.DataFrame,
    u: pd.DataFrame,
    *,
    out_dir: Path | None = None,
) -> None:
    from pathlib import Path as _Path

    dest = _Path(out_dir) if out_dir is not None else OUT
    dest.mkdir(parents=True, exist_ok=True)
    cat_posts = l1.groupby("post_category")["帖子id"].nunique()
    lines = [
        "# 数据质量摘要",
        "",
        f"- 主表行数: {len(main)}",
        f"- 唯一帖子数: {main['帖子id'].nunique()}",
        f"- 一级评论去重后: {len(l1)}",
        f"- 二级评论去重后: {len(l2)}",
        f"- 统一评论表行数: {len(u)}",
        f"- 空一级内容行(去重前可估算): {(main['一级评论内容'].isna() | (main['一级评论内容'].astype(str).str.strip() == '')).sum()}",
        "",
        "## 各类别帖子数（去重一级评论表）",
        "",
        cat_posts.to_string(),
        "",
    ]
    (dest / "data_quality.md").write_text("\n".join(lines), encoding="utf-8")


def write_codebook_suggestions(enriched: pd.DataFrame, l1: pd.DataFrame) -> None:
    role_cols = [c for c in enriched.columns if c.startswith("role_")]
    ph_cols = [c for c in enriched.columns if c.startswith("ph_")]
    bd_cols = [c for c in enriched.columns if c.startswith("bd_")]

    parts = [
        "# Codebook 修订建议（阶段一自动草案）",
        "",
        "以下内容来自探索性词典与分布，**须人工核验**后再写入正式 codebook。",
        "",
        "## 1. 关系框定 / 角色化候选",
        "",
        "- 词典维度：`athlete`, `hero_progress`, `failure_comedy`, `baby_cute`, `threat_compete`, `product_tech`, `nation_tech`。",
        "- 下一步：对每个维度各抽 20 条高赞评论，合并/拆分为 codebook 中的「关系框定」子类。",
        "",
    ]
    rc = enriched.groupby("post_category")[role_cols].mean().sort_index()
    parts.append("### 各类别角色词典均值（全评论层级合并）\n")
    parts.append("```\n" + rc.to_string() + "\n```\n")

    parts.append("## 2. 心智投射 / 拟人化线索候选\n\n")
    parts.append("- 维度：`pronoun_*`, `kin_terms`, `mind_volition`, `body_pain`, `care_moral`。\n")
    parts.append("- 下一步：与 Phase2「心智属性投射」维度对齐；注意 **人称代词** 与 **亲昵称谓** 应分码。\n\n")
    ph = enriched.groupby("post_category")[ph_cols].mean().sort_index()
    parts.append("```\n" + ph.to_string() + "\n```\n")

    parts.append("## 3. 人机边界协商候选\n\n")
    bd = enriched.groupby("post_category")[bd_cols].mean().sort_index()
    parts.append("```\n" + bd.to_string() + "\n```\n")

    parts.append("## 4. 玩梗与互动模板\n\n")
    tmpl = enriched.groupby("post_category")["template_style"].mean().sort_values(ascending=False)
    parts.append("套话模板命中率（`您是…它是…` 类）按类别：\n\n```\n" + tmpl.to_string() + "\n```\n")
    parts.append("- 下一步：在 codebook 增加「互文/玩梗」或「套话接龙」标签（二元或多标签）。\n\n")

    parts.append("## 5. 高回复一级评论（协商与 meme 高发位）\n\n")
    parts.append("完整列表见 `top_high_reply_l1.csv`。请在编码指南中注明：**一级 vs 二级** 分码。\n")

    (OUT / "codebook_revision_suggestions.md").write_text("\n".join(parts), encoding="utf-8")


def build_phase1_summary(enriched: pd.DataFrame, l1: pd.DataFrame) -> None:
    lines = [
        "# 第一阶段分析摘要报告",
        "",
        "## 产物",
        "",
        "- `clean_l1_comments.csv` / `clean_l2_comments.csv` / `clean_comments_unified.csv`",
        "- `data_quality.md`",
        "- `interaction_by_category.csv`, `top_high_reply_l1.csv`",
        "- `role_scores_by_category_level.csv`, `personhood_by_category_level.csv`",
        "- `boundary_by_category_level.csv`, `boundary_contrast_sample.csv`",
        "- `meme_template_counts.csv`, `meme_heavy_highlike_sample.csv`, `char4grams_top_by_category_L1.csv`",
        "- `cooccurrence_robot_pronouns.json`",
        "- `topic_clusters_terms.csv`, `topic_cluster_by_category.csv`",
        "- `figures/*.png`",
        "",
        "## 进入第二阶段 codebook 的候选线索（机器生成，需人工核验）",
        "",
    ]
    role_cols = [c for c in enriched.columns if c.startswith("role_")]
    ph_cols = [c for c in enriched.columns if c.startswith("ph_")]
    has_lexicon = bool(role_cols or ph_cols or "template_style" in enriched.columns)
    if has_lexicon:
        for cat in sorted(enriched["post_category"].dropna().unique()):
            sub = enriched[enriched["post_category"] == cat]
            lines.append(f"### {cat}")
            if "template_style" in sub.columns:
                tmpl_rate = sub["template_style"].mean()
                lines.append(f"- 套话模板命中率(您是…它是…风格): {tmpl_rate:.3%}")
            if role_cols:
                rmean = sub[role_cols].mean().sort_values(ascending=False).head(3)
                lines.append(
                    "- 角色词典均值 Top3: "
                    + ", ".join(f"{k.replace('role_','')}={v:.3f}" for k, v in rmean.items())
                )
            if ph_cols:
                pmean = sub[ph_cols].mean().sort_values(ascending=False).head(3)
                lines.append(
                    "- 拟人线索 Top3: "
                    + ", ".join(f"{k.replace('ph_','')}={v:.3f}" for k, v in pmean.items())
                )
            lines.append("")
    else:
        lines.append("（未启用 `--legacy-lexicon-features`，跳过词典/模板统计。）\n")

    lines.append("## 高回复一级评论（玩梗/协商潜在热点）")
    lines.append("见 `top_high_reply_l1.csv` 前 10 行摘取：")
    top10 = l1.nlargest(10, "reply_count")[["post_category", "reply_count", "like_count", "content"]]
    for _, r in top10.iterrows():
        excerpt = str(r["content"])[:120].replace("\n", " ")
        rc = pd.to_numeric(r["reply_count"], errors="coerce")
        lc = pd.to_numeric(r["like_count"], errors="coerce")
        ri = int(rc) if pd.notna(rc) else 0
        li = int(lc) if pd.notna(lc) else 0
        lines.append(f"- [{r['post_category']}] replies={ri} likes={li} — {excerpt}")

    (OUT / "phase1_summary_report.md").write_text("\n".join(lines), encoding="utf-8")
