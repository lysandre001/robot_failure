"""可脚本调用也可 Notebook 逐步调用的流水线。"""
from __future__ import annotations

from pathlib import Path

from phase1.analysis import (
    boundary_outputs,
    ensure_dirs,
    interaction_map,
    meme_outputs,
    personhood_outputs,
    role_aggregate,
    topic_clusters,
)
from phase1.config import OUT, configure_matplotlib
from phase1.features import apply_lexicons
from phase1.topic_lda import export_lda_result, run_lda
from phase1.preprocess import (
    apply_post_category_by_post,
    build_level1,
    build_level2,
    coerce_engagement,
    load_raw_frames,
    merge_post_category,
    unified_comments,
)
from phase1.reports import (
    build_phase1_summary,
    write_codebook_suggestions,
    write_data_quality,
)


def run_phase1_pipeline(
    *,
    xlsx: Path | str | None = None,
    post_category_overrides: dict[str | int, str] | None = None,
    write_csv: bool = True,
    run_topics: bool = True,
    run_lda_topics: bool = False,
    lda_topics_k: int = 10,
    lda_tokenizer: str = "jieba",
    verbose: bool = True,
) -> dict:
    """
    执行完整第一阶段。返回关键 DataFrame 供 Notebook 继续分析。

    post_category_overrides
        可选：`帖子id` → `类别`。会与 `config/post_category_by_post.csv` 合并，同 id 以本参数为准。

    Returns
    -------
    dict with keys: main_df, merged, l1, l2, unified, enriched
    """
    configure_matplotlib()
    ensure_dirs()
    if verbose:
        print("1/8 读取 Excel…", flush=True)
    main_df, counts = load_raw_frames(xlsx)
    merged = merge_post_category(main_df, counts)
    merged = apply_post_category_by_post(merged, overrides=post_category_overrides)

    if verbose:
        print("2/8 构建一级/二级/统一表…", flush=True)
    l1 = coerce_engagement(build_level1(merged))
    l2 = coerce_engagement(build_level2(merged))
    unified = coerce_engagement(unified_comments(l1, l2))

    if write_csv:
        l1.to_csv(OUT / "clean_l1_comments.csv", index=False)
        l2.to_csv(OUT / "clean_l2_comments.csv", index=False)
        unified.to_csv(OUT / "clean_comments_unified.csv", index=False)

    if verbose:
        print("3/8 数据质量…", flush=True)
    write_data_quality(merged, l1, l2, unified)

    if verbose:
        print("4/8 互动结构…", flush=True)
    interaction_map(l1)

    if verbose:
        print("5/8 词典特征…", flush=True)
    enriched = apply_lexicons(unified)
    if write_csv:
        enriched.to_csv(OUT / "comments_enriched.csv", index=False)

    if verbose:
        print("6/8 角色/拟人/玩梗/边界…", flush=True)
    role_aggregate(enriched)
    personhood_outputs(enriched)
    meme_outputs(enriched)
    boundary_outputs(enriched)

    if run_topics:
        if verbose:
            print("7/8 主题聚类…", flush=True)
        topic_clusters(
            unified["content"].tolist(),
            unified["post_category"].tolist(),
            top_n=min(8000, len(unified)),
        )

    if run_lda_topics:
        if verbose:
            print("8/9 LDA 主题（可选）…", flush=True)
        lda_result = run_lda(
            unified,
            tokenizer=lda_tokenizer,
            n_topics=lda_topics_k,
        )
        export_lda_result(lda_result, prefix="lda")

    if verbose:
        print("9/9 报告…", flush=True)
    build_phase1_summary(enriched, l1)
    write_codebook_suggestions(enriched, l1)

    if verbose:
        print("完成。输出目录:", OUT, flush=True)

    return {
        "main_df": main_df,
        "merged": merged,
        "l1": l1,
        "l2": l2,
        "unified": unified,
        "enriched": enriched,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 Phase 1 流水线")
    parser.add_argument(
        "--xlsx",
        type=str,
        default=None,
        help="小红书 Excel 路径；默认同环境变量 ROBOTIC_FAILURE_XLSX，否则项目根/小红书帖子数据.xlsx",
    )
    parser.add_argument(
        "--run-lda-topics",
        action="store_true",
        help="额外运行可配置 LDA 主题建模并导出 lda_*.csv",
    )
    parser.add_argument(
        "--lda-topics-k",
        type=int,
        default=10,
        help="LDA 主题数（仅在 --run-lda-topics 时生效）",
    )
    parser.add_argument(
        "--lda-tokenizer",
        type=str,
        default="jieba",
        choices=["jieba", "pkuseg", "char_bigram"],
        help="LDA 中文分词器",
    )
    args = parser.parse_args()
    run_phase1_pipeline(
        xlsx=args.xlsx,
        run_lda_topics=args.run_lda_topics,
        lda_topics_k=args.lda_topics_k,
        lda_tokenizer=args.lda_tokenizer,
    )
