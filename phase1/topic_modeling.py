"""全量 shared corpus：LDA / NMF / BERTopic（BGE）对比；不依赖 lexicon。"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import itertools
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from phase1.comment_content_filter import classify_comment_noise, load_comment_filter_rules
from phase1.config import ROOT
from phase1.preprocess import normalize_text
from phase1.topic_lda import (
    clean_text,
    load_topic_stopwords,
    tokenize_text,
    _setup_tokenizer,
)

try:
    import jieba  # type: ignore
except ImportError as exc:
    raise ImportError("topic_modeling 需要 jieba。请 pip install jieba") from exc

_URL_ONLY_RE = re.compile(r"^(https?://\S+|www\.\S+)$", re.I)
_DIGITS_ONLY_RE = re.compile(r"^[\d\s]+$")
_PURE_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)


@dataclass
class TopicModelingConfig:
    run_id: str = "2026-05-09_topic_full_corpus_bge_base"
    input_csv: Path = ROOT / "output" / "phase1" / "data" / "clean_comments_unified.csv"
    comment_content_filter_json: Path = ROOT / "config" / "topic_modeling" / "comment_content_filter.json"
    post_category_by_post_csv: Path = ROOT / "config" / "post_category_by_post.csv"
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    embedding_model_fallback: str = "BAAI/bge-small-zh-v1.5"
    device: str | None = None  # None -> auto mps/cuda/cpu
    lda_k_values: tuple[int, ...] = (5, 7, 10, 12)
    bert_kmeans_k_values: tuple[int, ...] = (5, 7, 10)
    bert_hdbscan_min_cluster_sizes: tuple[int, ...] = (100, 200, 400)
    bert_hdbscan_min_samples: int | None = None
    bert_reduce_outliers: bool = True
    min_clean_chars: int = 4
    min_effective_tokens: int = 2
    random_seed: int = 42
    low_memory: bool = True
    calculate_probabilities: bool = False
    sample_per_topic: int = 30
    top_terms: int = 15
    cache_embeddings: bool = True
    lda_min_df: int = 5
    lda_max_df: float = 0.92
    nmf_min_df: int = 3
    nmf_max_df: float = 0.95
    max_features: int = 8000
    experiments_root: Path = ROOT / "output" / "experiments"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe_cfg_value(value: Any) -> Any:
    """Dataclass 快照写入 JSON：Path / tuple 等到可序列化类型。"""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _pick_device(preference: str | None) -> str:
    if preference:
        return preference
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _split_post_category(s: Any) -> tuple[str, str]:
    if pd.isna(s) or str(s).strip() == "":
        return "", ""
    parts = str(s).split("|", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), ""


def _effective_token_count(text: str, stopwords: set[str]) -> int:
    _setup_tokenizer("jieba")
    toks = tokenize_text(text, tokenizer="jieba", stopwords=stopwords)
    return len(toks)


def _is_pure_noise_row(nt: str) -> str | None:
    if not nt.strip():
        return "empty_after_normalize"
    if _PURE_PUNCT_RE.match(nt):
        return "pure_punctuation"
    if _URL_ONLY_RE.match(nt.strip()):
        return "pure_url"
    if _DIGITS_ONLY_RE.match(nt) and len(nt.strip()) >= 5:
        return "pure_digit_id"
    return None


def build_shared_analyzable_corpus(
    cfg: TopicModelingConfig,
    *,
    stopwords: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    raw = pd.read_csv(cfg.input_csv)
    n_raw = len(raw)
    rules = load_comment_filter_rules(cfg.comment_content_filter_json)

    pc = pd.read_csv(cfg.post_category_by_post_csv)
    pc = pc.rename(columns={"类别": "post_category"})
    if "帖子id" not in raw.columns:
        raise ValueError("input_csv 需含列 帖子id")
    raw = raw.drop(columns=["post_category"], errors="ignore")
    raw = raw.merge(pc[["帖子id", "post_category"]], on="帖子id", how="left")

    rs_hr = raw["post_category"].map(_split_post_category)
    raw["robot_status"] = rs_hr.map(lambda x: x[0])
    raw["human_role"] = rs_hr.map(lambda x: x[1])

    stats: dict[str, int] = {
        "excluded_empty_or_too_short": 0,
        "excluded_pure_emoji": 0,
        "excluded_only_at_mentions": 0,
        "excluded_repeated_fragment": 0,
        "excluded_pure_noise_row": 0,
        "excluded_effective_tokens_lt_min": 0,
        "excluded_duplicate_text": 0,
    }
    excluded_rows: list[dict[str, Any]] = []
    kept_rows: list[pd.Series] = []
    seen_norm: set[str] = set()

    for idx, row in raw.iterrows():
        content = row.get("content", "")
        nt = normalize_text(content)
        rid = row.get("comment_id", idx)

        if not nt or len(nt) < cfg.min_clean_chars:
            stats["excluded_empty_or_too_short"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": "empty_or_too_short", "content": content})
            continue

        noise_key = classify_comment_noise(str(content), rules)
        if noise_key == "pure_emoji":
            stats["excluded_pure_emoji"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": "pure_emoji", "content": content})
            continue
        if noise_key == "only_at_mentions":
            stats["excluded_only_at_mentions"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": "only_at_mentions", "content": content})
            continue
        if noise_key == "repeated_fragment":
            stats["excluded_repeated_fragment"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": "repeated_fragment", "content": content})
            continue

        pn = _is_pure_noise_row(nt)
        if pn:
            stats["excluded_pure_noise_row"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": pn, "content": content})
            continue

        etc = _effective_token_count(str(content), stopwords)
        if etc < cfg.min_effective_tokens:
            stats["excluded_effective_tokens_lt_min"] += 1
            excluded_rows.append(
                {"comment_id": rid, "exclude_reason": "effective_tokens_lt_min", "content": content}
            )
            continue

        dup_k = nt.casefold()
        if dup_k in seen_norm:
            stats["excluded_duplicate_text"] += 1
            excluded_rows.append({"comment_id": rid, "exclude_reason": "duplicate_text", "content": content})
            continue
        seen_norm.add(dup_k)

        row2 = row.copy()
        row2["effective_token_count"] = etc
        kept_rows.append(row2)

    shared = pd.DataFrame(kept_rows).reset_index(drop=True)
    excluded_df = pd.DataFrame(excluded_rows)
    summary = {
        "n_raw": int(n_raw),
        "n_shared": int(len(shared)),
        "coverage": float(len(shared) / n_raw) if n_raw else 0.0,
        **{k: int(v) for k, v in stats.items()},
    }
    return shared, excluded_df, summary


def _space_join_tokens(text: str, stopwords: set[str]) -> str:
    _setup_tokenizer("jieba")
    toks = tokenize_text(text, tokenizer="jieba", stopwords=stopwords)
    return " ".join(toks)


def _jieba_tokenizer_vec(text: str, stopwords: set[str]) -> list[str]:
    """用于 sklearn Count/Tfidf：先 clean_text 再分词。"""
    t = clean_text(str(text))
    if not t:
        return []
    _setup_tokenizer("jieba")
    toks = jieba.lcut(t, cut_all=False)
    out: list[str] = []
    for w in toks:
        w = w.strip()
        if not w or w in stopwords:
            continue
        if len(w) == 1:
            continue
        out.append(w)
    return out


def _topic_diversity_from_terms(topic_rows: list[str]) -> float:
    sets = []
    for row in topic_rows:
        terms = [x.strip() for x in str(row).split(",") if x.strip()]
        sets.append(set(terms[:15]))
    if len(sets) < 2:
        return 1.0
    jaccs = []
    for a, b in itertools.combinations(sets, 2):
        u = len(a | b) or 1
        jaccs.append(len(a & b) / u)
    return float(1.0 - np.mean(jaccs))


def _lda_nmf_scan_and_export(
    cfg: TopicModelingConfig,
    shared: pd.DataFrame,
    stopwords: set[str],
    run_dir: Path,
    log_stream: Any,
) -> None:
    texts = shared["content"].astype(str).tolist()
    doc_joined = [_space_join_tokens(t, stopwords) for t in texts]
    mask_nonempty = np.array([bool(d.strip()) for d in doc_joined])
    if not mask_nonempty.all():
        # 不应发生：effective tokens 已过滤
        shared = shared.loc[mask_nonempty].reset_index(drop=True)
        doc_joined = [d for d, m in zip(doc_joined, mask_nonempty, strict=False) if m]

    selection_rows: list[dict[str, Any]] = []

    # LDA + NMF per K
    for k in cfg.lda_k_values:
        # LDA CountVectorizer
        vec_lda = CountVectorizer(
            analyzer=lambda s: s.split(),
            min_df=cfg.lda_min_df,
            max_df=cfg.lda_max_df,
            max_features=cfg.max_features,
        )
        X_lda = vec_lda.fit_transform(doc_joined)
        lda = LatentDirichletAllocation(
            n_components=k,
            learning_method="batch",
            max_iter=40,
            random_state=cfg.random_seed,
            doc_topic_prior=1.0 / k,
            topic_word_prior=0.01,
        )
        dt_lda = lda.fit_transform(X_lda)
        lda_labels = dt_lda.argmax(axis=1)
        fn = np.array(vec_lda.get_feature_names_out())
        top_lda = []
        for tid in range(k):
            comp = lda.components_[tid]
            idx = np.argsort(comp)[-cfg.top_terms :][::-1]
            top_lda.append(", ".join(fn[idx]))
        perplex = float(lda.perplexity(X_lda))
        counts = np.bincount(lda_labels, minlength=k)
        selection_rows.append(
            {
                "method": "lda",
                "k": k,
                "perplexity": perplex,
                "reconstruction_err": np.nan,
                "topic_diversity": _topic_diversity_from_terms(top_lda),
                "largest_topic_share": float(counts.max() / counts.sum()),
                "smallest_topic_share": float(counts.min() / counts.sum()),
            }
        )

        topics_df = pd.DataFrame(
            {
                "topic": list(range(k)),
                "top_terms": top_lda,
                "size": [int(x) for x in counts.tolist()],
            }
        )
        topics_df.to_csv(run_dir / f"lda_k{k}_topics.csv", index=False)

        assign = shared.copy()
        assign["topic"] = lda_labels
        assign["topic_prob"] = dt_lda.max(axis=1)
        samples = (
            assign.sort_values(["topic", "topic_prob", "like_count"], ascending=[True, False, False])
            .groupby("topic", group_keys=False)
            .head(cfg.sample_per_topic)
        )
        samples.to_csv(run_dir / f"lda_k{k}_samples.csv", index=False)

        _export_cross_tabs(assign, run_dir / f"lda_k{k}_by_post_id.csv", "post_id", "帖子id")
        _export_cross_tabs(assign, run_dir / f"lda_k{k}_by_robot_status.csv", "robot_status")
        _export_cross_tabs(assign, run_dir / f"lda_k{k}_by_post_category.csv", "post_category")

        print(f"[LDA k={k}] perplexity={perplex:.2f} docs={len(assign)}", file=log_stream)

        # NMF
        vec_nmf = TfidfVectorizer(
            analyzer=lambda s: s.split(),
            min_df=cfg.nmf_min_df,
            max_df=cfg.nmf_max_df,
            max_features=cfg.max_features,
        )
        X_nmf = vec_nmf.fit_transform(doc_joined)
        nmf = NMF(
            n_components=k,
            init="nndsvda",
            random_state=cfg.random_seed,
            max_iter=400,
        )
        W = nmf.fit_transform(X_nmf)
        fn_nmf = np.array(vec_nmf.get_feature_names_out())
        nmf_labels = W.argmax(axis=1)
        top_nmf = []
        for tid in range(k):
            comp = nmf.components_[tid]
            idx = np.argsort(comp)[-cfg.top_terms :][::-1]
            top_nmf.append(", ".join(fn_nmf[idx]))
        err = float(nmf.reconstruction_err_)
        counts_n = np.bincount(nmf_labels, minlength=k)
        selection_rows.append(
            {
                "method": "nmf",
                "k": k,
                "perplexity": np.nan,
                "reconstruction_err": err,
                "topic_diversity": _topic_diversity_from_terms(top_nmf),
                "largest_topic_share": float(counts_n.max() / counts_n.sum()),
                "smallest_topic_share": float(counts_n.min() / counts_n.sum()),
            }
        )

        pd.DataFrame(
            {
                "topic": list(range(k)),
                "top_terms": top_nmf,
                "size": [int(x) for x in counts_n.tolist()],
            }
        ).to_csv(run_dir / f"nmf_k{k}_topics.csv", index=False)

        assign_n = shared.copy()
        assign_n["topic"] = nmf_labels
        assign_n["topic_prob"] = W.max(axis=1)
        samples_n = (
            assign_n.sort_values(["topic", "topic_prob", "like_count"], ascending=[True, False, False])
            .groupby("topic", group_keys=False)
            .head(cfg.sample_per_topic)
        )
        samples_n.to_csv(run_dir / f"nmf_k{k}_samples.csv", index=False)
        _export_cross_tabs(assign_n, run_dir / f"nmf_k{k}_by_post_id.csv", "post_id", "帖子id")
        _export_cross_tabs(assign_n, run_dir / f"nmf_k{k}_by_robot_status.csv", "robot_status")
        _export_cross_tabs(assign_n, run_dir / f"nmf_k{k}_by_post_category.csv", "post_category")

        print(f"[NMF k={k}] reconstruction_err={err:.4f} docs={len(assign_n)}", file=log_stream)

    pd.DataFrame(selection_rows).sort_values(["method", "k"]).to_csv(
        run_dir / "a_lda_nmf_k_selection.csv", index=False
    )


def _export_cross_tabs(
    assign: pd.DataFrame,
    out_path: Path,
    dim_col: str,
    source_col: str | None = None,
) -> None:
    col = source_col or dim_col
    topic_ids = sorted({int(t) for t in assign["topic"].dropna().unique().tolist()})
    topic_counts = assign.groupby([col, "topic"]).size().rename("count").reset_index()
    totals = assign.groupby(col).size().rename("n_comments").reset_index()
    merged = topic_counts.merge(totals, on=col)
    merged["share_within_cell"] = merged["count"] / merged["n_comments"]

    if dim_col in ("robot_status", "post_category"):
        posts = assign.groupby("帖子id").first().reset_index()[["帖子id", "robot_status", "human_role", "post_category"]]
        post_topic = assign.groupby(["帖子id", "topic"]).size().rename("cnt").reset_index()
        post_n = assign.groupby("帖子id").size().rename("n_post").reset_index()
        pt = post_topic.merge(post_n, on="帖子id")
        pt["share_within_post"] = pt["cnt"] / pt["n_post"]
        if dim_col == "robot_status":
            rs_posts = posts[["帖子id", "robot_status"]].drop_duplicates()
            pt = pt.merge(rs_posts, on="帖子id")
            avg_rows = []
            for rs in sorted(pt["robot_status"].dropna().unique()):
                subposts = pt[pt["robot_status"] == rs]["帖子id"].unique()
                if len(subposts) == 0:
                    continue
                mat = []
                for pid in subposts:
                    row = pt[pt["帖子id"] == pid]
                    vec = {int(t): row[row["topic"] == t]["share_within_post"].sum() for t in topic_ids}
                    mat.append([vec.get(t, 0.0) for t in topic_ids])
                arr = np.array(mat)
                mean_share = arr.mean(axis=0)
                for i, t in enumerate(topic_ids):
                    avg_rows.append(
                        {
                            "robot_status": rs,
                            "topic": t,
                            "mean_share_post_averaged": float(mean_share[i]),
                            "n_posts_in_status": len(subposts),
                        }
                    )
            pd.DataFrame(avg_rows).to_csv(out_path, index=False)
            return
        if dim_col == "post_category":
            pc_posts = posts[["帖子id", "post_category"]].drop_duplicates()
            pt2 = pt.merge(pc_posts, on="帖子id")
            avg_rows = []
            for pc in sorted(pt2["post_category"].dropna().unique()):
                subposts = pt2[pt2["post_category"] == pc]["帖子id"].unique()
                if len(subposts) == 0:
                    continue
                mat = []
                for pid in subposts:
                    row = pt2[pt2["帖子id"] == pid]
                    vec = {int(t): row[row["topic"] == t]["share_within_post"].sum() for t in topic_ids}
                    mat.append([vec.get(t, 0.0) for t in topic_ids])
                arr = np.array(mat)
                mean_share = arr.mean(axis=0)
                for i, t in enumerate(topic_ids):
                    avg_rows.append(
                        {
                            "post_category": pc,
                            "topic": t,
                            "mean_share_post_averaged": float(mean_share[i]),
                            "n_posts_in_category": len(subposts),
                        }
                    )
            pd.DataFrame(avg_rows).to_csv(out_path, index=False)
            return

    merged.to_csv(out_path, index=False)


def _run_bertopic_suite(
    cfg: TopicModelingConfig,
    shared: pd.DataFrame,
    stopwords: set[str],
    run_dir: Path,
    embedding_model_used: str,
    log_stream: Any,
) -> dict[str, Any]:
    print("[BERTopic] importing optional deps…", file=log_stream, flush=True)
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from umap import UMAP

    docs_raw = shared["content"].astype(str).tolist()
    device = _pick_device(cfg.device)
    cache_path = run_dir / "embeddings.npy"

    model_name = embedding_model_used
    print(f"[BERTopic] SentenceTransformer({model_name!r}, device={device!r}) …", file=log_stream, flush=True)
    # 无外网/代理卡住时，构造函数可能在解析远端 revision 时长时间阻塞；优先读本地 HF 缓存。
    try:
        encoder = SentenceTransformer(model_name, device=device, local_files_only=True)
        print("[BERTopic] 已从本地 HuggingFace 缓存加载嵌入模型。", file=log_stream, flush=True)
    except Exception as e:
        print(f"[BERTopic] 本地缓存不可用（{e}），改为在线拉取模型权重…", file=log_stream, flush=True)
        encoder = SentenceTransformer(model_name, device=device, local_files_only=False)
        print("[BERTopic] SentenceTransformer 已加载到内存。", file=log_stream, flush=True)

    if cfg.cache_embeddings and cache_path.is_file():
        embeddings = np.load(cache_path)
        print(f"[BERTopic] loaded embeddings from {cache_path}", file=log_stream, flush=True)
    else:
        print(f"[BERTopic] encoding {len(docs_raw)} docs …", file=log_stream, flush=True)
        embeddings = encoder.encode(
            docs_raw,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        if cfg.cache_embeddings:
            np.save(cache_path, embeddings)
            print(f"[BERTopic] saved {cache_path}", file=log_stream, flush=True)

    assert len(docs_raw) == len(embeddings), "docs/embeddings length mismatch"

    def make_vectorizer():
        return CountVectorizer(
            analyzer=lambda text: _jieba_tokenizer_vec(text, stopwords),
            min_df=1,
            max_df=1.0,
            max_features=8000,
        )

    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=cfg.random_seed,
    )

    vectorizer_model = make_vectorizer()
    meta_out: dict[str, Any] = {"bertopic_runs": []}

    for mcs in cfg.bert_hdbscan_min_cluster_sizes:
        min_samples = cfg.bert_hdbscan_min_samples if cfg.bert_hdbscan_min_samples is not None else mcs
        hdb = HDBSCAN(
            min_cluster_size=mcs,
            min_samples=min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )
        bt = BERTopic(
            embedding_model=encoder,
            umap_model=umap_model,
            hdbscan_model=hdb,
            vectorizer_model=make_vectorizer(),
            low_memory=cfg.low_memory,
            calculate_probabilities=cfg.calculate_probabilities,
            verbose=True,
        )
        topics_raw, _ = bt.fit_transform(docs_raw, embeddings)
        topics_raw = np.array(topics_raw)
        out_rate = float(np.mean(topics_raw == -1))
        n_topics = len(set(topics_raw.tolist())) - (1 if -1 in set(topics_raw.tolist()) else 0)

        subdir = run_dir / f"bert_hdbscan_mcs{mcs}"
        subdir.mkdir(parents=True, exist_ok=True)
        assigned = None
        if cfg.bert_reduce_outliers:
            try:
                assigned = bt.reduce_outliers(docs_raw, topics_raw.tolist(), strategy="c-tf-idf")
            except Exception as e:
                print(f"[WARN] reduce_outliers failed: {e}", file=log_stream)
                assigned = topics_raw.tolist()

        doc_topics = shared[["comment_id", "帖子id", "post_category", "robot_status", "human_role", "content"]].copy()
        doc_topics["topic_raw"] = topics_raw
        doc_topics["topic_assigned"] = assigned if assigned is not None else topics_raw
        doc_topics.to_csv(subdir / "doc_topics.csv", index=False)

        info = bt.get_topic_info()
        info.to_csv(subdir / "topics.csv", index=False)

        assign_df = shared.copy()
        assign_df["topic"] = topics_raw
        assign_df.loc[assign_df["topic"] == -1, "topic"] = np.nan
        valid = assign_df[assign_df["topic"].notna()].copy()
        valid["topic"] = valid["topic"].astype(int)
        samples = (
            valid.sort_values(["topic", "like_count"], ascending=[True, False])
            .groupby("topic", group_keys=False)
            .head(cfg.sample_per_topic)
        )
        samples.to_csv(subdir / "samples.csv", index=False)

        _export_cross_tabs(valid, subdir / "by_post_id.csv", "post_id", "帖子id")
        _export_cross_tabs(valid, subdir / "by_robot_status.csv", "robot_status")
        _export_cross_tabs(valid, subdir / "by_post_category.csv", "post_category")

        meta_out["bertopic_runs"].append(
            {
                "mcs": mcs,
                "n_topics_approx": int(n_topics),
                "outlier_rate_topic_raw": out_rate,
            }
        )
        print(
            f"[BERTopic HDBSCAN mcs={mcs}] topics~={n_topics} outlier_rate={out_rate:.3f}",
            file=log_stream,
        )

    for k in cfg.bert_kmeans_k_values:
        km = KMeans(n_clusters=k, random_state=cfg.random_seed, n_init=10)
        bt_k = BERTopic(
            embedding_model=encoder,
            umap_model=umap_model,
            hdbscan_model=km,
            vectorizer_model=make_vectorizer(),
            low_memory=cfg.low_memory,
            calculate_probabilities=False,
            verbose=True,
        )
        topics_km, _ = bt_k.fit_transform(docs_raw, embeddings)
        subdir = run_dir / f"bert_kmeans_k{k}"
        subdir.mkdir(parents=True, exist_ok=True)
        doc_topics = shared[["comment_id", "帖子id", "post_category", "robot_status", "human_role", "content"]].copy()
        doc_topics["topic"] = topics_km
        doc_topics.to_csv(subdir / "doc_topics.csv", index=False)
        info = bt_k.get_topic_info()
        info.to_csv(subdir / "topics.csv", index=False)

        assign_df = shared.copy()
        assign_df["topic"] = topics_km
        samples = (
            assign_df.sort_values(["topic", "like_count"], ascending=[True, False])
            .groupby("topic", group_keys=False)
            .head(cfg.sample_per_topic)
        )
        samples.to_csv(subdir / "samples.csv", index=False)
        _export_cross_tabs(assign_df, subdir / "by_post_id.csv", "post_id", "帖子id")
        _export_cross_tabs(assign_df, subdir / "by_robot_status.csv", "robot_status")
        _export_cross_tabs(assign_df, subdir / "by_post_category.csv", "post_category")
        print(f"[BERTopic KMeans k={k}] done.", file=log_stream)

    return meta_out


def _jaccard_terms(a: str, b: str) -> float:
    sa = set(x.strip() for x in a.split(",") if x.strip())
    sb = set(x.strip() for x in b.split(",") if x.strip())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _bert_representation_to_csv_terms(rep: Any) -> str:
    """BERTopic topics.csv 的 Representation 可能是 \"['a','b']\" 字符串，转成与 LDA top_terms 一致的逗号分隔。"""
    if rep is None or (isinstance(rep, float) and pd.isna(rep)):
        return ""
    s = str(rep).strip()
    if s.startswith("[") and "]" in s:
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (list, tuple)):
                return ", ".join(str(x).strip() for x in obj if str(x).strip())
        except (SyntaxError, ValueError, TypeError):
            pass
    return s


def write_comparison_md(
    cfg: TopicModelingConfig,
    run_dir: Path,
    summary_corpus: dict[str, Any],
    embedding_model_used: str,
) -> None:
    lda_k_ref = 7
    km_k_ref = 7
    lda_path = run_dir / f"lda_k{lda_k_ref}_topics.csv"
    bert_path = run_dir / f"bert_kmeans_k{km_k_ref}" / "topics.csv"
    lines: list[str] = []
    lines.append("# LDA / NMF / BERTopic 对比（探索性）\n")
    lines.append("本报告为 **探索性主题建模**，不构成分类器 ground truth。")
    lines.append("`robot_status` / `human_role` / `post_category` 来自研究设计的帖子抽样标签（config/post_category_by_post.csv），非模型发现。\n")
    lines.append(f"- shared corpus 覆盖率：{summary_corpus.get('coverage', 0):.4f}（{summary_corpus.get('n_shared')}/{summary_corpus.get('n_raw')}）")
    lines.append(f"- 嵌入模型：`{embedding_model_used}`\n")

    lines.append("## 方法 × K：主题词概览（对照入口）\n")
    lines.append("以下为各 `*_topics.csv` 中主题词的截断预览；完整词表与样本见同目录 CSV / `samples.csv`。\n")
    for k in cfg.lda_k_values:
        lp = run_dir / f"lda_k{k}_topics.csv"
        if lp.is_file():
            df = pd.read_csv(lp)
            lines.append(f"### LDA k={k}\n")
            for _, row in df.iterrows():
                tt = str(row.get("top_terms", ""))
                short = tt if len(tt) <= 100 else tt[:100] + "…"
                lines.append(f"- topic {row.get('topic')}: {short}")
            lines.append("")
    for k in cfg.lda_k_values:
        np_ = run_dir / f"nmf_k{k}_topics.csv"
        if np_.is_file():
            df = pd.read_csv(np_)
            lines.append(f"### NMF k={k}\n")
            for _, row in df.iterrows():
                tt = str(row.get("top_terms", ""))
                short = tt if len(tt) <= 100 else tt[:100] + "…"
                lines.append(f"- topic {row.get('topic')}: {short}")
            lines.append("")
    for k in cfg.bert_kmeans_k_values:
        bp = run_dir / f"bert_kmeans_k{k}" / "topics.csv"
        if bp.is_file():
            df = pd.read_csv(bp)
            bt_df = df[df["Topic"] >= 0] if "Topic" in df.columns else df
            lines.append(f"### BERTopic KMeans k={k}\n")
            for _, row in bt_df.iterrows():
                rep = _bert_representation_to_csv_terms(row.get("Representation"))
                short = rep if len(rep) <= 100 else rep[:100] + "…"
                lines.append(f"- topic {row.get('Topic')}: {short}")
            lines.append("")

    lines.append("## 主题 × 分层：横切表文件索引\n")
    lines.append("- LDA：`lda_k{K}_by_robot_status.csv`、`lda_k{K}_by_post_category.csv`、`lda_k{K}_by_post_id.csv`")
    lines.append("- NMF：`nmf_k{K}_...` 同上")
    lines.append("- BERTopic：`bert_hdbscan_mcs{M}/`、`bert_kmeans_k{K}/` 内同名横切表。\n")

    if lda_path.is_file() and bert_path.is_file():
        lda_t = pd.read_csv(lda_path)
        bert_t = pd.read_csv(bert_path)
        if "Representation" in bert_t.columns:
            bt_df = bert_t[bert_t["Topic"] >= 0] if "Topic" in bert_t.columns else bert_t
            b_terms = [_bert_representation_to_csv_terms(x) for x in bt_df["Representation"].tolist()]
        else:
            b_terms = []
        lines.append(f"## LDA k={lda_k_ref} 与 BERTopic KMeans k={km_k_ref} 主题词 Jaccard 配对（启发式）\n")
        for _, row in lda_t.iterrows():
            lt = str(row.get("top_terms", ""))
            best_j, best_bi = -1.0, -1
            for bi, bt in enumerate(b_terms):
                j = _jaccard_terms(lt, str(bt))
                if j > best_j:
                    best_j, best_bi = j, bi
            lines.append(f"- LDA topic {row.get('topic')}: 最近 BERTopic topic {best_bi}（Jaccard≈{best_j:.3f}）")
        lines.append("")

    lines.append("## HDBSCAN 灵敏度（min_cluster_size）\n")
    for mcs in cfg.bert_hdbscan_min_cluster_sizes:
        p = run_dir / f"bert_hdbscan_mcs{mcs}" / "topics.csv"
        if p.is_file():
            lines.append(f"- `bert_hdbscan_mcs{mcs}/topics.csv` 已生成（含 `topic_raw` / `topic_assigned` 见 `doc_topics.csv`）。")
    lines.append("\n## 解释优先级\n")
    lines.append("- HDBSCAN：`topic_raw`（含 -1 噪声）为主解释；`topic_assigned` 仅辅助阅读。\n")
    loo_p = run_dir / "loo_post_sensitivity_lda_k7_robot_status.csv"
    if loo_p.is_file():
        lines.append("\n## Leave-one-post-out（爆款帖敏感度）\n")
        lines.append(f"- `{loo_p.name}`：逐帖剔除后，LDA k=7 在 `robot_status` 上 post-averaged 主题占比的变化量。\n")
    lines.append("\n## Post-level averaging\n")
    lines.append("`by_robot_status.csv` / `by_post_category.csv` 使用「每个 post 内算主题占比，再对同维度平均」，减轻爆款帖权重。\n")

    (run_dir / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def _loo_sensitivity(
    cfg: TopicModelingConfig,
    shared: pd.DataFrame,
    stopwords: set[str],
    run_dir: Path,
) -> None:
    """Leave-one-post-out：排除某个帖子后重算 robot_status 层面 post-averaged 分布（基于 LDA k=7 标签）。"""
    k = 7
    if k not in cfg.lda_k_values:
        return
    texts = [_space_join_tokens(t, stopwords) for t in shared["content"].astype(str)]
    vec_lda = CountVectorizer(
        analyzer=lambda s: s.split(),
        min_df=cfg.lda_min_df,
        max_df=cfg.lda_max_df,
        max_features=cfg.max_features,
    )
    X = vec_lda.fit_transform(texts)
    lda = LatentDirichletAllocation(
        n_components=k,
        learning_method="batch",
        max_iter=40,
        random_state=cfg.random_seed,
        doc_topic_prior=1.0 / k,
        topic_word_prior=0.01,
    )
    dt = lda.fit_transform(X)
    labels = dt.argmax(axis=1)
    base = shared.copy()
    base["topic"] = labels
    posts = sorted(base["帖子id"].astype(str).unique())
    rows = []
    ref_tab = _robot_status_mean_table(base, k)
    for ex in posts:
        sub = base[base["帖子id"].astype(str) != ex]
        tab = _robot_status_mean_table(sub, k)
        for rs in ref_tab["robot_status"].unique():
            for t in range(k):
                r0 = ref_tab[(ref_tab["robot_status"] == rs) & (ref_tab["topic"] == t)][
                    "mean_share_post_averaged"
                ]
                r1 = tab[(tab["robot_status"] == rs) & (tab["topic"] == t)]["mean_share_post_averaged"]
                v0 = float(r0.iloc[0]) if len(r0) else 0.0
                v1 = float(r1.iloc[0]) if len(r1) else 0.0
                rows.append(
                    {
                        "excluded_post_id": ex,
                        "robot_status": rs,
                        "topic": t,
                        "delta_mean_share": v1 - v0,
                    }
                )
    pd.DataFrame(rows).to_csv(run_dir / "loo_post_sensitivity_lda_k7_robot_status.csv", index=False)


def _robot_status_mean_table(assign: pd.DataFrame, k: int) -> pd.DataFrame:
    post_topic = assign.groupby(["帖子id", "topic"]).size().rename("cnt").reset_index()
    post_n = assign.groupby("帖子id").size().rename("n_post").reset_index()
    pt = post_topic.merge(post_n, on="帖子id")
    pt["share_within_post"] = pt["cnt"] / pt["n_post"]
    posts_meta = assign.groupby("帖子id").first().reset_index()[["帖子id", "robot_status"]]
    pt = pt.merge(posts_meta, on="帖子id")
    rows = []
    for rs in sorted(pt["robot_status"].dropna().unique()):
        subposts = pt[pt["robot_status"] == rs]["帖子id"].unique()
        if len(subposts) == 0:
            continue
        mat = []
        for pid in subposts:
            row = pt[pt["帖子id"] == pid]
            vec = {int(t): row[row["topic"] == t]["share_within_post"].sum() for t in range(k)}
            mat.append([vec.get(t, 0.0) for t in range(k)])
        arr = np.array(mat)
        mean_share = arr.mean(axis=0)
        for t in range(k):
            rows.append(
                {
                    "robot_status": rs,
                    "topic": t,
                    "mean_share_post_averaged": float(mean_share[t]),
                    "n_posts_in_status": len(subposts),
                }
            )
    return pd.DataFrame(rows)


def run_experiment(cfg: TopicModelingConfig) -> Path:
    buf = io.StringIO()
    tee = Tee(sys.stdout, buf)

    run_dir = cfg.experiments_root / cfg.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    stopwords = load_topic_stopwords()
    shared, excluded, summary_corpus = build_shared_analyzable_corpus(cfg, stopwords=stopwords)

    shared.to_csv(run_dir / "shared_analyzable_corpus.csv", index=False)
    excluded.to_csv(run_dir / "excluded_meaningless.csv", index=False)

    shutil.copy2(cfg.comment_content_filter_json, run_dir / "comment_content_filter.json")
    shutil.copy2(cfg.post_category_by_post_csv, run_dir / "post_category_by_post.csv")

    embedding_used = cfg.embedding_model
    meta_run: dict[str, Any] = {}

    print("=== Topic modeling run ===", file=tee)
    print(json.dumps(summary_corpus, ensure_ascii=False, indent=2), file=tee)

    _lda_nmf_scan_and_export(cfg, shared, stopwords, run_dir, tee)

    try:
        meta_run = _run_bertopic_suite(cfg, shared, stopwords, run_dir, embedding_used, tee)
    except Exception as e:
        print(f"[BERTopic] primary model failed ({embedding_used}): {e}", file=tee)
        embedding_used = cfg.embedding_model_fallback
        print(f"[BERTopic] trying fallback: {embedding_used}", file=tee)
        meta_run = _run_bertopic_suite(cfg, shared, stopwords, run_dir, embedding_used, tee)

    try:
        _loo_sensitivity(cfg, shared, stopwords, run_dir)
    except Exception as e:
        print(f"[LOO] skipped: {e}", file=tee)

    write_comparison_md(cfg, run_dir, summary_corpus, embedding_used)

    faq = {
        "C1_chinese_tokenizer": "jieba (token_pattern=None)",
        "C2_stopwords_after_embedding": True,
        "C3_umap_random_state": cfg.random_seed,
        "C4_calculate_probabilities": cfg.calculate_probabilities,
        "C5_low_memory": cfg.low_memory,
        "C6_outlier_strategy": "reduce_outliers(strategy='c-tf-idf') + KMeans backup",
        "C7_min_topic_size_sensitivity": list(cfg.bert_hdbscan_min_cluster_sizes),
        "C8_model_used": embedding_used,
        "C10_raw_text_to_encoder": True,
        "POS_main_pipeline": False,
        "content_filter_config": str(cfg.comment_content_filter_json),
        "post_category_source": str(cfg.post_category_by_post_csv),
    }

    config_payload = {
        "run_id": cfg.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_csv": str(cfg.input_csv),
        "input_csv_sha256": _sha256_file(cfg.input_csv),
        "n_shared": int(len(shared)),
        "summary_corpus": summary_corpus,
        "embedding_model_resolved": embedding_used,
        "faq_compliance": faq,
        "config": {
            f.name: _json_safe_cfg_value(getattr(cfg, f.name))
            for f in fields(cfg)
            if f.name != "experiments_root"
        },
        "bertopic_meta": meta_run,
    }
    with open(run_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_payload, f, ensure_ascii=False, indent=2)

    log_text = buf.getvalue()
    (run_dir / "run.log").write_text(log_text, encoding="utf-8")

    reg_path = cfg.experiments_root / "registry.csv"
    line = f'{cfg.run_id},{datetime.now().strftime("%Y-%m-%d")},topic_full_corpus,,,{embedding_used},,"{run_dir}",active,main\n'
    if reg_path.is_file():
        existing = reg_path.read_text(encoding="utf-8")
        if cfg.run_id not in {
            ln.split(",", 1)[0] for ln in existing.splitlines()[1:] if ln.strip()
        }:
            with open(reg_path, "a", encoding="utf-8") as f:
                f.write(line)
    else:
        reg_path.write_text("run_id,date,task,hypothesis,input_data,method,key_params,output_dir,status,decision\n", encoding="utf-8")
        with open(reg_path, "a", encoding="utf-8") as f:
            f.write(line)

    print(f"Done. Output: {run_dir}", file=tee)
    return run_dir


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase1 全量主题建模（LDA/NMF/BERTopic）")
    ap.add_argument("--run-id", type=str, default=TopicModelingConfig.run_id)
    ap.add_argument("--input-csv", type=str, default=str(TopicModelingConfig.input_csv))
    ap.add_argument("--embedding-model", type=str, default=TopicModelingConfig.embedding_model)
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument(
        "--lda-k",
        type=int,
        nargs="+",
        default=None,
        help="LDA / NMF K 列表，如 5 7 10 12",
    )
    ap.add_argument(
        "--bert-kmeans-k",
        type=int,
        nargs="+",
        default=None,
        help="BERTopic KMeans K 列表，如 5 7 10",
    )
    ap.add_argument(
        "--hdbscan-min-cluster-sizes",
        type=int,
        nargs="+",
        default=None,
        help="BERTopic HDBSCAN min_cluster_size 列表（敏感度），如 100 200 400",
    )
    args = ap.parse_args()

    overrides: dict[str, Any] = {}
    if args.lda_k:
        overrides["lda_k_values"] = tuple(args.lda_k)
    if args.bert_kmeans_k:
        overrides["bert_kmeans_k_values"] = tuple(args.bert_kmeans_k)
    if args.hdbscan_min_cluster_sizes:
        overrides["bert_hdbscan_min_cluster_sizes"] = tuple(args.hdbscan_min_cluster_sizes)

    cfg = TopicModelingConfig(
        run_id=args.run_id,
        input_csv=Path(args.input_csv),
        embedding_model=args.embedding_model,
        device=args.device,
        **overrides,
    )
    run_experiment(cfg)


if __name__ == "__main__":
    main()
