"""可脚本调用也可 Notebook 逐步调用的流水线。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from phase1.analysis import (
    boundary_outputs,
    ensure_dirs,
    interaction_map,
    meme_outputs,
    personhood_outputs,
    role_aggregate,
    topic_clusters,
)
from phase1.config import CLEAN_DIR, OUT, POST_CATEGORY_BY_POST_CSV, ROOT, configure_matplotlib
from phase1.features import apply_lexicons
from phase1.topic_lda import export_lda_result, load_corpus_gate_stopwords, run_lda
from phase1.comment_content_filter import COMMENT_CONTENT_FILTER_JSON
from phase1.deidentify import (
    dedupe_user_identical_content,
    deidentify_for_public,
    drop_pii_columns,
    write_deidentify_report,
    write_pii_sidecar,
)
from phase1.preprocess import (
    apply_post_category_by_post,
    build_level1,
    build_level2,
    coerce_engagement,
    filter_valid_comments,
    load_raw_wide_table,
    merge_post_category,
    normalize_post_id,
    unified_comments,
)
from phase1.stage_summary import build_stage_summary_rows, write_stage_summary
from phase1.topic_modeling import TopicModelingConfig, build_shared_analyzable_corpus
from phase1.reports import (
    build_phase1_summary,
    write_codebook_suggestions,
    write_data_quality,
)


def _post_category_csv_for(platform: str, source_batch: str) -> Path | None:
    p = ROOT / "config" / "post_category" / f"{platform}_{source_batch}.csv"
    return p if p.is_file() else None


def _export_comments_per_post(unified: pd.DataFrame, out_csv: Path) -> None:
    g = unified.groupby(["帖子id", "comment_level"]).size().unstack(fill_value=0)
    g = g.rename(columns={1: "L1", 2: "L2"})
    for c in ("L1", "L2"):
        if c not in g.columns:
            g[c] = 0
    g = g[["L1", "L2"]].astype(int)
    g["合计"] = g["L1"] + g["L2"]
    g.reset_index().to_csv(out_csv, index=False, encoding="utf-8-sig")


def run_phase1_pipeline(
    *,
    xlsx: Path | str | None = None,
    input_path: Path | str | None = None,
    platform: str = "xhs",
    source_batch: str = "batch1",
    clean_dir: Path | str | None = None,
    post_category_overrides: dict[str | int, str] | None = None,
    write_csv: bool = True,
    run_topics: bool = False,
    run_lda_topics: bool = False,
    lda_topics_k: int = 10,
    lda_tokenizer: str = "jieba",
    min_chars: int = 0,
    drop_repeated_single_char: bool = False,
    apply_comment_content_rules: bool = True,
    content_rules_path: Path | str | None = None,
    export_shared: bool = True,
    verbose: bool = True,
    legacy_lexicon_features: bool = False,
) -> dict:
    """
    执行完整第一阶段。返回关键 DataFrame 供 Notebook 继续分析。

    post_category_overrides
        可选：`帖子id` → `类别`。会与 `config/post_category_by_post.csv` 合并，同 id 以本参数为准。

    Returns
    -------
    dict with keys:
    - main_df, merged
    - l1, l2 (去重后未过滤)
    - unified_before_filter (统一长表过滤前)
    - unified (统一长表过滤后)
    - l1_filtered, l2_filtered (过滤后按层级拆分)
    - enriched：若 legacy_lexicon_features=True 则为 enriched；否则与 unified 相同引用
    """
    configure_matplotlib()
    ensure_dirs()
    plat = platform.lower().strip()
    out_clean = (
        Path(clean_dir)
        if clean_dir is not None
        else ROOT / "data" / "clean" / plat / source_batch
    )
    out_clean.mkdir(parents=True, exist_ok=True)

    data_path = input_path or xlsx
    if data_path is None and plat == "xhs":
        from phase1.preprocess import resolve_data_xlsx

        data_path = resolve_data_xlsx(None)
    if data_path is None:
        raise ValueError("需指定 --input 或 --xlsx")

    if verbose:
        print(f"1/8 读取数据 ({plat}/{source_batch})…", flush=True)
    main_df, counts = load_raw_wide_table(data_path, platform=plat)
    main_df["帖子id"] = main_df["帖子id"].map(normalize_post_id)
    counts["帖子id"] = counts["帖子id"].map(normalize_post_id)
    merged = merge_post_category(main_df, counts)
    merged["帖子id"] = merged["帖子id"].map(normalize_post_id)
    cat_csv = _post_category_csv_for(plat, source_batch)
    if plat == "xhs":
        merged = apply_post_category_by_post(merged, overrides=post_category_overrides)
    elif cat_csv is not None:
        merged = apply_post_category_by_post(
            merged, csv_path=cat_csv, overrides=post_category_overrides
        )
    else:
        if "post_category" not in merged.columns:
            merged["post_category"] = "unknown"
        else:
            merged["post_category"] = merged["post_category"].fillna("unknown")
        merged["robot_status"] = ""
        merged["human_role"] = ""

    if verbose:
        print("2/8 构建一级/二级/统一表…", flush=True)
    l1 = coerce_engagement(build_level1(merged))
    l2 = coerce_engagement(build_level2(merged))
    unified_before_filter = coerce_engagement(unified_comments(l1, l2))
    rules_path: Path | str | None = None
    if apply_comment_content_rules:
        rules_path = content_rules_path or (
            COMMENT_CONTENT_FILTER_JSON if COMMENT_CONTENT_FILTER_JSON.is_file() else None
        )
    report_path = (out_clean / "comment_content_filter_report.json") if rules_path else None
    unified = filter_valid_comments(
        unified_before_filter,
        min_chars=min_chars,
        drop_empty_content=True,
        drop_repeated_single_char=drop_repeated_single_char,
        content_rules_path=rules_path,
        content_filter_report_path=report_path,
    )
    unified, dedup_stats = dedupe_user_identical_content(unified)
    l1_filtered = unified[unified["comment_level"] == 1].copy()
    l2_filtered = unified[unified["comment_level"] == 2].copy()

    for frame in (unified_before_filter, unified, l1, l2, l1_filtered, l2_filtered):
        frame["platform"] = plat
        frame["source_batch"] = source_batch

    unified_before_filter = drop_pii_columns(unified_before_filter)
    unified, pii_sidecar = deidentify_for_public(unified)
    l1 = drop_pii_columns(l1)
    l2 = drop_pii_columns(l2)
    l1_filtered = drop_pii_columns(l1_filtered)
    l2_filtered = drop_pii_columns(l2_filtered)

    shared_n: int | None = None
    shared_summary: dict | None = None

    if write_csv:
        write_pii_sidecar(pii_sidecar, out_clean)
        write_deidentify_report(
            out_clean,
            {
                **dedup_stats,
                "platform": plat,
                "source_batch": source_batch,
                "pii_sidecar_rows": int(len(pii_sidecar)),
            },
        )
        l1.to_csv(out_clean / "clean_l1_comments.csv", index=False)
        l2.to_csv(out_clean / "clean_l2_comments.csv", index=False)
        unified_before_filter.to_csv(out_clean / "clean_comments_unified_before_filter.csv", index=False)
        unified.to_csv(out_clean / "clean_comments_unified.csv", index=False)
        l1_filtered.to_csv(out_clean / "clean_l1_comments_filtered.csv", index=False)
        l2_filtered.to_csv(out_clean / "clean_l2_comments_filtered.csv", index=False)
        _export_comments_per_post(unified, out_clean / "comments_per_post_L1_L2.csv")

    if export_shared and write_csv:
        gate_sw = load_corpus_gate_stopwords()
        pc_csv: Path = POST_CATEGORY_BY_POST_CSV
        if plat != "xhs" and cat_csv is not None:
            pc_csv = cat_csv
        cfg = TopicModelingConfig(
            run_id=f"export_shared_{plat}_{source_batch}",
            input_csv=out_clean / "clean_comments_unified.csv",
            platform=plat,
            post_category_by_post_csv=pc_csv,
        )
        shared, excluded, shared_summary = build_shared_analyzable_corpus(cfg, stopwords=gate_sw)
        shared.to_csv(out_clean / "shared_analyzable_corpus.csv", index=False)
        excluded.to_csv(out_clean / "excluded_meaningless.csv", index=False)
        (out_clean / "shared_corpus_summary.json").write_text(
            __import__("json").dumps(shared_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        shared_n = int(shared_summary.get("n_shared", len(shared)))

    if write_csv:
        rows = build_stage_summary_rows(
            platform=plat,
            source_batch=source_batch,
            n_posts=int(main_df["帖子id"].nunique()),
            unified_before=unified_before_filter,
            unified_after=unified,
            shared_n=shared_n,
        )
        write_stage_summary(
            out_clean,
            rows,
            meta={
                "platform": plat,
                "source_batch": source_batch,
                "raw_input": str(Path(data_path).resolve()),
                "clean_dir": str(out_clean.resolve()),
            },
        )

    if verbose:
        print("3/8 数据质量…", flush=True)
    write_data_quality(merged, l1, l2, unified, out_dir=out_clean)

    if verbose:
        print("4/8 互动结构…", flush=True)
    interaction_map(l1, out_dir=out_clean)

    enriched = unified
    if legacy_lexicon_features:
        if verbose:
            print("5/8 词典特征（legacy）…", flush=True)
        enriched = apply_lexicons(unified)
        if write_csv:
            enriched.to_csv(OUT / "comments_enriched.csv", index=False)

        if verbose:
            print("6/8 角色/拟人/玩梗/边界（legacy）…", flush=True)
        role_aggregate(enriched)
        personhood_outputs(enriched)
        meme_outputs(enriched)
        boundary_outputs(enriched)
    else:
        if verbose:
            print("5/8 跳过 lexicon 特征（默认）。使用 --legacy-lexicon-features 启用。\n", flush=True)

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
    if legacy_lexicon_features:
        report_df = enriched
        build_phase1_summary(report_df, l1)
        write_codebook_suggestions(report_df, l1)

    if verbose:
        print("完成。清洗表:", out_clean / "clean_comments_unified.csv", flush=True)
        if shared_n is not None:
            print(f"  shared corpus: {shared_n:,}", flush=True)

    return {
        "platform": plat,
        "source_batch": source_batch,
        "clean_dir": out_clean,
        "shared_summary": shared_summary,
        "main_df": main_df,
        "merged": merged,
        "l1": l1,
        "l2": l2,
        "unified_before_filter": unified_before_filter,
        "unified": unified,
        "l1_filtered": l1_filtered,
        "l2_filtered": l2_filtered,
        "enriched": enriched,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 Phase 1 流水线")
    parser.add_argument(
        "--platform",
        type=str,
        default="xhs",
        choices=["xhs", "tiktok", "douyin", "youtube"],
        help="数据来源平台",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="原始数据路径（CSV 或 XHS xlsx）",
    )
    parser.add_argument(
        "--batch",
        type=str,
        default="batch1",
        dest="source_batch",
        help="批次标识，如 batch1 / batch2 / merged",
    )
    parser.add_argument(
        "--clean-dir",
        type=str,
        default=None,
        help="清洗产物目录（默认 data/clean/{platform}/{batch}）",
    )
    parser.add_argument(
        "--xlsx",
        type=str,
        default=None,
        help="（兼容）同 --input；小红书 Excel 路径",
    )
    parser.add_argument(
        "--no-export-shared",
        action="store_true",
        help="不导出 shared_analyzable_corpus",
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
    parser.add_argument(
        "--min-chars",
        type=int,
        default=0,
        help="统一评论最小字符长度阈值（默认不过滤）",
    )
    parser.add_argument(
        "--drop-repeated-single-char",
        action="store_true",
        help="去掉由同一字符重复组成的评论（如 哈哈哈哈 / 啊啊啊啊）；若已启用 comment_content_filter.json 则忽略",
    )
    parser.add_argument(
        "--no-comment-content-rules",
        action="store_true",
        help="不应用 config/topic_modeling/comment_content_filter.json",
    )
    parser.add_argument(
        "--content-rules",
        type=str,
        default=None,
        help="评论噪音规则 JSON 路径（默认 config/topic_modeling/comment_content_filter.json）",
    )
    parser.add_argument(
        "--legacy-lexicon-features",
        action="store_true",
        help="启用旧版 lexicon 特征与 role_aggregate 等输出（默认关闭）",
    )
    parser.add_argument(
        "--run-topics",
        action="store_true",
        help="额外运行旧版 sklearn topic_clusters（默认关；正式主题建模用 phase1.topic_modeling）",
    )
    args = parser.parse_args()
    run_phase1_pipeline(
        xlsx=args.xlsx,
        input_path=args.input or args.xlsx,
        platform=args.platform,
        source_batch=args.source_batch,
        clean_dir=args.clean_dir,
        export_shared=not args.no_export_shared,
        run_topics=args.run_topics,
        run_lda_topics=args.run_lda_topics,
        lda_topics_k=args.lda_topics_k,
        lda_tokenizer=args.lda_tokenizer,
        min_chars=args.min_chars,
        drop_repeated_single_char=args.drop_repeated_single_char,
        apply_comment_content_rules=not args.no_comment_content_rules,
        content_rules_path=args.content_rules,
        legacy_lexicon_features=args.legacy_lexicon_features,
    )
