"""从已存 BERTopic 模型 reload 出 5 张 HTML 可视化。不再 fit。

用法：
    ./.venv/bin/python -m phase1.topic_visualize \\
        --run-id 2026-05-09_topic_full_corpus_bge_base \\
        --variant bert_kmeans_k7 \\
        --class-col robot_status post_category

依赖：
    - <run_dir>/<variant>/model/                # bt.save 产物（safetensors 或 pickle）
    - <run_dir>/<variant>/doc_topics.csv        # 文档级 topic 与元数据
    - <run_dir>/embeddings.npy                  # 句向量缓存（可选，documents_2d 用）
    - <run_dir>/umap_reduced.npy                # UMAP 5D 降维结果（documents_2d 用）

输出：<run_dir>/<variant>/figs/*.html
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase1.config import ROOT


def _resolve_paths(run_id: str, variant: str) -> tuple[Path, Path, Path]:
    run_dir = ROOT / "output" / "experiments" / run_id
    variant_dir = run_dir / variant
    figs_dir = variant_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, variant_dir, figs_dir


def _load_model(variant_dir: Path, embedding_model_name: str | None):
    """优先尝试用本地 HF 缓存的 SentenceTransformer 作为 embedding_model 重载。"""
    from bertopic import BERTopic

    model_dir = variant_dir / "model"
    model_pkl = variant_dir / "model.pkl"
    if model_dir.exists():
        model_path = model_dir
    elif model_pkl.exists():
        model_path = model_pkl
    else:
        raise FileNotFoundError(
            f"未找到模型：{model_dir} 或 {model_pkl}（请先用 phase1.topic_modeling 跑出 bt.save）"
        )

    encoder = None
    if embedding_model_name:
        try:
            from sentence_transformers import SentenceTransformer
            try:
                encoder = SentenceTransformer(embedding_model_name, local_files_only=True)
            except Exception:
                encoder = SentenceTransformer(embedding_model_name, local_files_only=False)
            print(f"[viz] encoder = {embedding_model_name}", flush=True)
        except Exception as e:
            print(f"[viz][WARN] encoder load failed: {e}; fallback BERTopic.load 不传 encoder", flush=True)
            encoder = None
    bt = BERTopic.load(str(model_path), embedding_model=encoder) if encoder else BERTopic.load(str(model_path))
    return bt


def _safe_write(fig: Any, path: Path) -> None:
    try:
        fig.write_html(str(path))
        print(f"[viz] wrote {path}")
    except Exception as e:
        print(f"[viz][WARN] failed to write {path}: {e}")


def _plot_documents_2d(
    bt: Any,
    doc_topics: pd.DataFrame,
    reduced_5d: np.ndarray,
    out_path: Path,
    *,
    title: str,
) -> None:
    """用预计算的 UMAP 5D 再降到 2D，按 topic 上色，hover 文本前 80 字。"""
    try:
        import plotly.express as px
        from umap import UMAP
    except Exception as e:
        print(f"[viz][WARN] plotly/umap 缺失，跳过 documents_2d: {e}")
        return

    if reduced_5d is None or len(reduced_5d) == 0:
        print("[viz][WARN] umap_reduced.npy 不可用，跳过 documents_2d")
        return
    if len(reduced_5d) != len(doc_topics):
        print(
            f"[viz][WARN] umap_reduced 行数({len(reduced_5d)}) ≠ doc_topics({len(doc_topics)})；跳过 documents_2d"
        )
        return

    print("[viz] re-reduce 5D -> 2D for documents plot…", flush=True)
    umap2 = UMAP(n_neighbors=15, n_components=2, min_dist=0.1, metric="euclidean", random_state=42)
    coords = umap2.fit_transform(reduced_5d)

    topic_col = "topic_assigned" if "topic_assigned" in doc_topics.columns else "topic"
    df = doc_topics.copy()
    df["x"] = coords[:, 0]
    df["y"] = coords[:, 1]
    df["topic_label"] = df[topic_col].astype(str)
    df["hover"] = df["content"].astype(str).str.slice(0, 80)

    sample_n = min(8000, len(df))
    if sample_n < len(df):
        df = df.sample(sample_n, random_state=42).reset_index(drop=True)

    fig = px.scatter(
        df,
        x="x",
        y="y",
        color="topic_label",
        hover_data={"hover": True, "x": False, "y": False, "topic_label": True},
        title=title,
        opacity=0.55,
    )
    fig.update_traces(marker=dict(size=4))
    fig.update_layout(legend_title_text="topic")
    _safe_write(fig, out_path)


def visualize(
    run_id: str,
    variant: str,
    class_cols: list[str],
    embedding_model_name: str | None,
    top_n_topics: int = 20,
    n_words: int = 12,
) -> None:
    run_dir, variant_dir, figs_dir = _resolve_paths(run_id, variant)
    if not variant_dir.is_dir():
        raise FileNotFoundError(f"variant 目录不存在：{variant_dir}")

    print(f"[viz] run_dir = {run_dir}")
    print(f"[viz] variant = {variant}")

    bt = _load_model(variant_dir, embedding_model_name)
    print(f"[viz] BERTopic loaded; n_topics = {len(bt.get_topics())}")

    doc_topics = pd.read_csv(variant_dir / "doc_topics.csv")
    docs = doc_topics["content"].astype(str).tolist()

    try:
        fig = bt.visualize_barchart(top_n_topics=top_n_topics, n_words=n_words)
        _safe_write(fig, figs_dir / "topics_barchart.html")
    except Exception as e:
        print(f"[viz][WARN] visualize_barchart failed: {e}")

    try:
        fig = bt.visualize_heatmap()
        _safe_write(fig, figs_dir / "topics_heatmap.html")
    except Exception as e:
        print(f"[viz][WARN] visualize_heatmap failed: {e}")

    try:
        fig = bt.visualize_hierarchy()
        _safe_write(fig, figs_dir / "topics_hierarchy.html")
    except Exception as e:
        print(f"[viz][WARN] visualize_hierarchy failed: {e}")

    for col in class_cols:
        if col not in doc_topics.columns:
            print(f"[viz][WARN] class_col '{col}' 不在 doc_topics.csv 中，跳过")
            continue
        try:
            classes = doc_topics[col].fillna("(missing)").astype(str).tolist()
            tpc = bt.topics_per_class(docs, classes=classes)
            fig = bt.visualize_topics_per_class(tpc, top_n_topics=top_n_topics)
            _safe_write(fig, figs_dir / f"topics_per_class_{col}.html")
        except Exception as e:
            print(f"[viz][WARN] topics_per_class[{col}] failed: {e}")

    reduced_path = run_dir / "umap_reduced.npy"
    reduced_5d = np.load(reduced_path) if reduced_path.is_file() else None
    if reduced_5d is None:
        print(f"[viz][WARN] {reduced_path} 不存在；documents_2d 跳过（请重跑 topic_modeling 生成）")
    _plot_documents_2d(
        bt,
        doc_topics,
        reduced_5d,
        figs_dir / "documents_2d.html",
        title=f"Documents 2D — {run_id}/{variant}",
    )

    print(f"[viz] done. figs at {figs_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="BERTopic 可视化（reload 已存模型，不再 fit）")
    ap.add_argument("--run-id", type=str, required=True)
    ap.add_argument("--variant", type=str, required=True, help="如 bert_kmeans_k7 / bert_hdbscan_mcs100")
    ap.add_argument(
        "--class-col",
        type=str,
        nargs="+",
        default=["robot_status", "post_category"],
        help="topics_per_class 用的元数据列（多列各出一张图）",
    )
    ap.add_argument(
        "--embedding-model",
        type=str,
        default="BAAI/bge-base-zh-v1.5",
        help="重载 BERTopic 时附带的 SentenceTransformer 名（仅 documents_2d 等需要）",
    )
    ap.add_argument("--top-n-topics", type=int, default=20)
    ap.add_argument("--n-words", type=int, default=12)
    args = ap.parse_args()

    visualize(
        run_id=args.run_id,
        variant=args.variant,
        class_cols=list(args.class_col),
        embedding_model_name=args.embedding_model,
        top_n_topics=args.top_n_topics,
        n_words=args.n_words,
    )


if __name__ == "__main__":
    sys.exit(main())
