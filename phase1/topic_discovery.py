"""Rigorous topic discovery workflow: freeze corpus, topic-number selection, review sheets, coding, backfill."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from phase1.topic_lda import tokenize_text, _setup_tokenizer

DEFAULT_RUN_ID = "2026-05-27_topic_merged_bge_hdbscan_sensitivity"
DEFAULT_BASE_MCS = 50
TOPIC_NR_CANDIDATES = list(range(10, 101, 5))
HDBSCAN_CANDIDATE_MCS = [30, 50, 80, 100]


@dataclass
class TopicDiscoveryConfig:
    run_id: str = DEFAULT_RUN_ID
    experiments_root: Path = field(default_factory=lambda: Path("output/experiments"))
    base_mcs: int = DEFAULT_BASE_MCS
    topic_nr_candidates: list[int] = field(default_factory=lambda: list(TOPIC_NR_CANDIDATES))
    hdbscan_candidate_mcs: list[int] = field(default_factory=lambda: list(HDBSCAN_CANDIDATE_MCS))
    random_state: int = 42
    analysis_unit: str = "comment"

    @property
    def run_dir(self) -> Path:
        return self.experiments_root / self.run_id

    @property
    def review_dir(self) -> Path:
        return self.run_dir / "topic_discovery_review"

    @property
    def shared_corpus_path(self) -> Path:
        return self.run_dir / "shared_analyzable_corpus.csv"

    @property
    def config_path(self) -> Path:
        return self.run_dir / "config.json"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_terms(x: Any, n: int = 12) -> list[str]:
    if pd.isna(x):
        return []
    s = str(x)
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [str(t).strip() for t in obj if str(t).strip()][:n]
    except Exception:
        pass
    return [t.strip() for t in s.split(",") if t.strip()][:n]


def load_run_config(cfg: TopicDiscoveryConfig) -> dict[str, Any]:
    with open(cfg.config_path, encoding="utf-8") as f:
        return json.load(f)


def freeze_corpus_snapshot(cfg: TopicDiscoveryConfig) -> Path:
    """Step 1: freeze corpus version, hashes, and analysis unit."""
    cfg.review_dir.mkdir(parents=True, exist_ok=True)
    run_cfg = load_run_config(cfg)
    shared = pd.read_csv(cfg.shared_corpus_path)

    snapshot = {
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "analysis_unit": cfg.analysis_unit,
        "run_id": cfg.run_id,
        "run_dir": str(cfg.run_dir.resolve()),
        "config_path": str(cfg.config_path.resolve()),
        "config_sha256": file_sha256(cfg.config_path),
        "shared_corpus_path": str(cfg.shared_corpus_path.resolve()),
        "shared_corpus_sha256": file_sha256(cfg.shared_corpus_path),
        "n_shared_comments": int(len(shared)),
        "input_csv": run_cfg.get("input_csv"),
        "input_csv_sha256": run_cfg.get("input_csv_sha256"),
        "embedding_model": run_cfg.get("embedding_model_resolved"),
        "summary_corpus": run_cfg.get("summary_corpus"),
        "exclusion_rules": {
            "source": "config.summary_corpus + comment_content_filter.json",
            "fields": [
                "excluded_empty_or_too_short",
                "excluded_pure_emoji",
                "excluded_only_at_mentions",
                "excluded_repeated_fragment",
                "excluded_pure_noise_row",
                "excluded_effective_tokens_lt_min",
                "excluded_duplicate_text",
            ],
        },
        "machine_role": "BERTopic+HDBSCAN proposes candidate topic structure only; not final social-science themes.",
        "primary_topic_field": "topic_raw",
        "sensitivity_topic_field": "topic_assigned",
    }
    out = cfg.review_dir / "corpus_freeze.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return out


def summarize_hdbscan_candidate(mcs: int, run_dir: Path) -> dict[str, Any]:
    sub = run_dir / f"bert_hdbscan_mcs{mcs}"
    topics = pd.read_csv(sub / "topics.csv")
    docs = pd.read_csv(sub / "doc_topics.csv")
    n_docs = len(docs)
    raw = docs["topic_raw"].astype(int)
    assigned = docs["topic_assigned"].astype(int)
    valid = raw >= 0
    valid_docs = int(valid.sum())
    sizes = raw[valid].value_counts()
    largest_topic = int(sizes.idxmax()) if len(sizes) else -1
    largest_share_valid = float(sizes.max() / valid_docs) if valid_docs else np.nan
    return {
        "mcs": mcs,
        "n_docs": n_docs,
        "n_topics": int((topics["Topic"] >= 0).sum()),
        "raw_outlier_rate": float((raw == -1).mean()),
        "assigned_outlier_rate": float((assigned == -1).mean()),
        "valid_docs": valid_docs,
        "largest_topic": largest_topic,
        "largest_share_valid": largest_share_valid,
        "largest_share_all": float(sizes.max() / n_docs) if len(sizes) else np.nan,
        "median_topic_size": float(sizes.median()) if len(sizes) else np.nan,
        "p25_topic_size": float(sizes.quantile(0.25)) if len(sizes) else np.nan,
        "p75_topic_size": float(sizes.quantile(0.75)) if len(sizes) else np.nan,
        "min_topic_size": int(sizes.min()) if len(sizes) else np.nan,
        "n_topics_ge_80": int((sizes >= 80).sum()) if len(sizes) else 0,
        "n_topics_ge_100": int((sizes >= 100).sum()) if len(sizes) else 0,
    }


def write_hdbscan_candidate_summary(cfg: TopicDiscoveryConfig) -> pd.DataFrame:
    rows = [summarize_hdbscan_candidate(mcs, cfg.run_dir) for mcs in cfg.hdbscan_candidate_mcs]
    df = pd.DataFrame(rows)
    out = cfg.review_dir / "hdbscan_candidate_summary.csv"
    df.to_csv(out, index=False)
    return df


def _load_docs_and_stopwords(cfg: TopicDiscoveryConfig) -> tuple[list[str], set[str], pd.DataFrame]:
    shared = pd.read_csv(cfg.shared_corpus_path)
    docs_raw = shared["content"].astype(str).tolist()
    filter_path = cfg.run_dir / "comment_content_filter.json"
    stopwords: set[str] = set()
    if filter_path.is_file():
        with open(filter_path, encoding="utf-8") as f:
            filt = json.load(f)
        stopwords = set(filt.get("stopwords", []))
    return docs_raw, stopwords, shared


def _tokenize_corpus(docs_raw: list[str], stopwords: set[str]) -> list[list[str]]:
    _setup_tokenizer("jieba")
    return [tokenize_text(d, tokenizer="jieba", stopwords=stopwords) for d in docs_raw]


def _topic_word_lists_from_model(bt: Any, top_n: int = 10) -> list[list[str]]:
    topic_ids = sorted(t for t in set(bt.topics_) if t >= 0)
    out: list[list[str]] = []
    for tid in topic_ids:
        words = [str(w).strip() for w, _ in bt.get_topic(tid)[:top_n] if str(w).strip()]
        if words:
            out.append(words)
    return out


def compute_cv_coherence(topic_word_lists: list[list[str]], tokenized_texts: list[list[str]]) -> float:
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    if not topic_word_lists:
        return float("nan")
    dictionary = Dictionary(tokenized_texts)
    filtered_topics: list[list[str]] = []
    for words in topic_word_lists:
        kept = [str(w).strip() for w in words if str(w).strip() in dictionary.token2id]
        if len(kept) >= 2:
            filtered_topics.append(kept)
    if not filtered_topics:
        return float("nan")
    cm = CoherenceModel(
        topics=filtered_topics,
        texts=tokenized_texts,
        dictionary=dictionary,
        coherence="c_v",
        processes=1,
    )
    return float(cm.get_coherence())


def _structural_diagnostics(topics_arr: np.ndarray) -> dict[str, Any]:
    raw = topics_arr.astype(int)
    valid = raw >= 0
    valid_docs = int(valid.sum())
    raw_outlier_rate = float((raw == -1).mean())
    sizes = pd.Series(raw[valid]).value_counts()
    n_topics = int(len(sizes))
    largest_share_valid = float(sizes.max() / valid_docs) if valid_docs else np.nan
    n_posts = np.nan
    return {
        "n_topics_final": n_topics,
        "raw_outlier_rate": raw_outlier_rate,
        "raw_coverage": float(valid.mean()),
        "valid_docs": valid_docs,
        "largest_topic_size": int(sizes.max()) if len(sizes) else 0,
        "largest_share_valid": largest_share_valid,
        "median_topic_size": float(sizes.median()) if len(sizes) else np.nan,
        "min_topic_size": int(sizes.min()) if len(sizes) else np.nan,
        "max_topic_size": int(sizes.max()) if len(sizes) else 0,
        "n_posts_covered": n_posts,
    }


def _load_bertopic_base(cfg: TopicDiscoveryConfig) -> Any:
    from bertopic import BERTopic

    model_dir = cfg.run_dir / f"bert_hdbscan_mcs{cfg.base_mcs}" / "model"
    return BERTopic.load(str(model_dir))


def scan_topic_numbers(cfg: TopicDiscoveryConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Step 2b: reduce_topics scan + C_V coherence + structural diagnostics."""
    docs_raw, stopwords, _ = _load_docs_and_stopwords(cfg)
    tokenized = _tokenize_corpus(docs_raw, stopwords)
    base_model_dir = cfg.run_dir / f"bert_hdbscan_mcs{cfg.base_mcs}" / "model"
    reduced_root = cfg.review_dir / f"topic_number_scan_mcs{cfg.base_mcs}"
    reduced_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for nr in cfg.topic_nr_candidates:
        print(f"[topic-number-scan] nr_topics={nr} …", flush=True)
        bt = _load_bertopic_base(cfg)
        try:
            bt.reduce_topics(docs_raw, nr_topics=nr)
        except Exception as e:
            print(f"[WARN] reduce_topics({nr}) failed: {e}", flush=True)
        topics_arr = np.asarray(bt.topics_, dtype=int)
        topic_words = _topic_word_lists_from_model(bt)
        cv = compute_cv_coherence(topic_words, tokenized)
        diag = _structural_diagnostics(topics_arr)
        info = bt.get_topic_info()
        info.to_csv(reduced_root / f"topics_nr{nr}.csv", index=False)
        doc_df = pd.read_csv(cfg.run_dir / f"bert_hdbscan_mcs{cfg.base_mcs}" / "doc_topics.csv")
        doc_df = doc_df.drop(columns=[c for c in ("topic_reduced",) if c in doc_df.columns])
        doc_df["topic_reduced"] = topics_arr
        doc_df.to_csv(reduced_root / f"doc_topics_nr{nr}.csv", index=False)
        rows.append(
            {
                "target_nr_topics": nr,
                "c_v_coherence": cv,
                **diag,
                "review_burden_ok": bool(40 <= diag["n_topics_final"] <= 100),
                "max_cluster_ok": bool(diag["largest_share_valid"] <= 0.12),
            }
        )

    curve_df = pd.DataFrame(rows).sort_values("target_nr_topics").reset_index(drop=True)
    curve_path = cfg.review_dir / "topic_number_cv_curve.csv"
    curve_df.to_csv(curve_path, index=False)

    diag_path = cfg.review_dir / "topic_number_candidate_diagnostics.csv"
    curve_df.to_csv(diag_path, index=False)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(curve_df["target_nr_topics"], curve_df["c_v_coherence"], marker="o", label="C_V")
    ax1.set_xlabel("Target nr_topics (reduce_topics)")
    ax1.set_ylabel("C_V coherence")
    ax1.set_title(f"Topic-number selection (HDBSCAN mcs={cfg.base_mcs})")
    ax1.grid(True, alpha=0.3)
    ax2 = ax1.twinx()
    ax2.plot(curve_df["target_nr_topics"], curve_df["largest_share_valid"], marker="s", color="tab:orange", alpha=0.7, label="Largest share")
    ax2.set_ylabel("Largest topic share (valid docs)")
    fig.tight_layout()
    png_path = cfg.review_dir / "topic_number_cv_curve.png"
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    return curve_df, curve_df


def select_final_topic_number(curve_df: pd.DataFrame, cfg: TopicDiscoveryConfig) -> tuple[int, str]:
    """Pick final K: structural guards first, then C_V on eligible set (not blind max)."""
    df = curve_df.copy()
    max_cv_row = df.loc[df["c_v_coherence"].idxmax()]
    max_cv = float(max_cv_row["c_v_coherence"])

    structural = df[
        (df["largest_share_valid"] <= 0.12)
        & (df["n_topics_final"] >= 40)
        & (df["n_topics_final"] <= 100)
    ].copy()

    notes: list[str] = [
        f"Base HDBSCAN candidate: mcs={cfg.base_mcs} (see hdbscan_candidate_summary.csv).",
        f"Scanned target nr_topics: {cfg.topic_nr_candidates[0]}–{cfg.topic_nr_candidates[-1]} step 5.",
        f"Maximum C_V={max_cv:.4f} at target_nr={int(max_cv_row['target_nr_topics'])} "
        f"(n_topics_final={int(max_cv_row['n_topics_final'])}, "
        f"largest_share={max_cv_row['largest_share_valid']:.3f}).",
    ]

    if int(max_cv_row["target_nr_topics"]) != int(max_cv_row.get("target_nr_topics", 0)):
        pass

    if not structural.empty:
        pick = structural.sort_values(["c_v_coherence", "largest_share_valid"], ascending=[False, True]).iloc[0]
        chosen = int(pick["target_nr_topics"])
        if int(max_cv_row["target_nr_topics"]) != chosen:
            notes.append(
                f"Rejected blind max-C_V (target_nr={int(max_cv_row['target_nr_topics'])}): "
                f"largest_share={max_cv_row['largest_share_valid']:.3f} exceeds 12% guard; "
                f"mega-cluster risk for manual merge."
            )
        notes.append(
            f"Selected target_nr={chosen}: C_V={pick['c_v_coherence']:.4f}, "
            f"n_topics_final={int(pick['n_topics_final'])}, "
            f"largest_share={pick['largest_share_valid']:.3f}, "
            f"raw_outlier_rate={pick['raw_outlier_rate']:.3f}."
        )
        notes.append(
            "Rationale: passes largest-cluster guard (<=12%), reviewable topic count, "
            "highest C_V among structurally eligible candidates."
        )
    else:
        plateau = df[df["c_v_coherence"] >= max_cv * 0.97].copy()
        fallback = plateau.sort_values(["largest_share_valid", "c_v_coherence"], ascending=[True, False]).iloc[0]
        chosen = int(fallback["target_nr_topics"])
        pick = fallback
        notes.append(
            "No candidate satisfied all structural guards; chose smallest largest_share on the C_V plateau."
        )
        notes.append(
            f"Selected target_nr={chosen}: C_V={pick['c_v_coherence']:.4f}, "
            f"n_topics_final={int(pick['n_topics_final'])}, "
            f"largest_share={pick['largest_share_valid']:.3f}."
        )

    notes_path = cfg.review_dir / "topic_number_selection_notes.md"
    notes_path.write_text("\n".join(f"- {n}" for n in notes) + "\n", encoding="utf-8")
    selection = {
        "selected_target_nr_topics": chosen,
        "selected_at": datetime.now().isoformat(timespec="seconds"),
        "base_mcs": cfg.base_mcs,
        "rejected_max_cv_target_nr": int(max_cv_row["target_nr_topics"]),
        "notes": notes,
    }
    with open(cfg.review_dir / "final_model_selection.json", "w", encoding="utf-8") as f:
        json.dump(selection, f, ensure_ascii=False, indent=2)
    return chosen, "\n".join(notes)


def materialize_final_model(cfg: TopicDiscoveryConfig, final_nr: int) -> Path:
    """Copy reduced outputs for the chosen topic number into final_model/."""
    scan_dir = cfg.review_dir / f"topic_number_scan_mcs{cfg.base_mcs}"
    final_dir = cfg.review_dir / "final_model"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)
    for name in (f"topics_nr{final_nr}.csv", f"doc_topics_nr{final_nr}.csv"):
        src = scan_dir / name
        dst = final_dir / name.replace(f"_nr{final_nr}", "_final")
        shutil.copy2(src, dst)
    meta = {
        "final_target_nr_topics": final_nr,
        "base_mcs": cfg.base_mcs,
        "topics_csv": "topics_final.csv",
        "doc_topics_csv": "doc_topics_final.csv",
    }
    with open(final_dir / "model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return final_dir


def format_examples(df: pd.DataFrame, n: int, *, include_meta: bool = True) -> str:
    if df.empty:
        return ""
    rows: list[str] = []
    for _, r in df.head(n).iterrows():
        text = str(r.get("content", "")).replace("\n", " ").strip()
        if include_meta:
            meta = (
                f"post={r.get('帖子id', '')}; "
                f"level={r.get('comment_level', '')}; "
                f"likes={r.get('like_count', '')}; "
                f"status={r.get('robot_status', '')}; role={r.get('human_role', '')}"
            )
            rows.append(f"[{meta}] {text}")
        else:
            rows.append(text)
    return "\n---\n".join(rows)


def sample_review_comments(
    sub: pd.DataFrame,
    *,
    n: int = 10,
    random_state: int = 42,
    topic_id: int = 0,
) -> pd.DataFrame:
    """Pick n unique comments: top-like, cross-post, then random fill."""
    if sub.empty:
        return sub.copy()
    sub = sub.copy()
    sub["like_count"] = pd.to_numeric(sub["like_count"], errors="coerce").fillna(0)
    sub_like = sub.sort_values(["like_count", "comment_id"], ascending=[False, True])
    picked_ids: set[str] = set()
    chunks: list[pd.DataFrame] = []

    def _take(df: pd.DataFrame, k: int, source: str) -> None:
        if k <= 0 or df.empty:
            return
        rows: list[pd.Series] = []
        for _, r in df.iterrows():
            cid = str(r["comment_id"])
            if cid in picked_ids:
                continue
            picked_ids.add(cid)
            row = r.copy()
            row["sample_source"] = source
            rows.append(row)
            if len(rows) >= k:
                break
        if rows:
            chunks.append(pd.DataFrame(rows))

    n_top = min(3, n, len(sub))
    n_cross = min(4, max(0, n - n_top), len(sub))
    n_rand = max(0, n - n_top - n_cross)

    _take(sub_like, n_top, "top_like")
    cross_pool = (
        sub_like.drop_duplicates("帖子id", keep="first")
        .sort_values(["like_count", "comment_id"], ascending=[False, True])
    )
    _take(cross_pool, n_cross, "cross_post")

    remaining = sub[~sub["comment_id"].astype(str).isin(picked_ids)]
    if n_rand > 0 and not remaining.empty:
        if len(remaining) <= n_rand:
            rem = remaining.sample(frac=1.0, random_state=random_state)
        else:
            rem = remaining.sample(n=n_rand, random_state=random_state + topic_id)
        rem = rem.copy()
        rem["sample_source"] = "random"
        chunks.append(rem)
        picked_ids.update(rem["comment_id"].astype(str).tolist())

    if len(picked_ids) < min(n, len(sub)):
        fill = sub[~sub["comment_id"].astype(str).isin(picked_ids)].sort_values(
            ["like_count", "comment_id"], ascending=[False, True]
        )
        _take(fill, min(n, len(sub)) - len(picked_ids), "fill")

    if not chunks:
        return sub.head(n).copy()
    out = pd.concat(chunks, ignore_index=True).head(n)
    out["sample_rank"] = range(1, len(out) + 1)
    return out


def format_comments_compact(df: pd.DataFrame) -> str:
    """Single-line numbered comment block for spreadsheet cells."""
    if df.empty:
        return ""
    parts: list[str] = []
    for _, r in df.iterrows():
        rank = r.get("sample_rank", "")
        text = str(r.get("content", "")).replace("\n", " ").strip()
        parts.append(
            f"{rank}. [{r.get('comment_id', '')}|post={r.get('帖子id', '')}|"
            f"likes={r.get('like_count', '')}|{r.get('sample_source', '')}] {text}"
        )
    return " || ".join(parts)


def docs_with_full_metadata(docs: pd.DataFrame, shared_corpus_path: Path) -> pd.DataFrame:
    shared = pd.read_csv(shared_corpus_path)
    meta_cols = [
        "comment_id",
        "comment_level",
        "like_count",
        "reply_count",
        "char_len",
        "location",
        "robot_status_group",
    ]
    keep = [c for c in meta_cols if c in shared.columns]
    return docs.merge(shared[keep], on="comment_id", how="left", suffixes=("", "_shared"))


def build_enhanced_topic_review_table(
    cfg: TopicDiscoveryConfig,
    *,
    topics_csv: Path,
    doc_topics_csv: Path,
    top_like_n: int = 5,
    post_diverse_n: int = 8,
    random_n: int = 5,
    review_comment_n: int = 10,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    topics = pd.read_csv(topics_csv)
    docs = pd.read_csv(doc_topics_csv)
    topic_col = "topic_reduced" if "topic_reduced" in docs.columns else "topic_raw"
    assigned_col = "topic_assigned" if "topic_assigned" in docs.columns else None
    docs = docs_with_full_metadata(docs, cfg.shared_corpus_path)
    valid_topics = topics[topics["Topic"] >= 0].copy()
    valid_topics["top_terms"] = valid_topics["Representation"].map(lambda x: ", ".join(parse_terms(x, n=12)))

    raw_docs = docs[docs[topic_col] >= 0].copy()
    raw_docs[topic_col] = raw_docs[topic_col].astype(int)
    raw_docs["like_count"] = pd.to_numeric(raw_docs["like_count"], errors="coerce").fillna(0)
    raw_docs["comment_level"] = pd.to_numeric(raw_docs["comment_level"], errors="coerce")

    rows: list[dict[str, Any]] = []
    post_rows: list[dict[str, Any]] = []
    comment_sample_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(random_state)

    for _, row in valid_topics.iterrows():
        tid = int(row["Topic"])
        sub = raw_docs[raw_docs[topic_col] == tid].copy()
        sub_like = sub.sort_values(["like_count", "comment_id"], ascending=[False, True])
        top_like = sub_like.head(top_like_n)
        post_diverse = (
            sub_like.drop_duplicates("帖子id", keep="first")
            .sort_values(["like_count", "comment_id"], ascending=[False, True])
            .head(post_diverse_n)
        )
        if len(sub) <= random_n:
            random_ex = sub.sample(frac=1.0, random_state=random_state)
        else:
            random_ex = sub.sample(n=random_n, random_state=int(rng.integers(0, 1_000_000) + tid))
        review_comments = sample_review_comments(
            sub, n=review_comment_n, random_state=random_state, topic_id=tid
        )

        post_counts = sub.groupby("帖子id").size().sort_values(ascending=False)
        n_posts = int(post_counts.size)
        top_post_share = float(post_counts.iloc[0] / len(sub)) if len(sub) else np.nan
        level_counts = sub["comment_level"].value_counts(normalize=True)
        level1_share = float(level_counts.get(1, 0.0))
        level2_share = float(level_counts.get(2, 0.0))

        for pid, cnt in post_counts.head(5).items():
            post_rows.append(
                {"topic_id": tid, "帖子id": pid, "raw_count": int(cnt), "share_raw": float(cnt / len(sub))}
            )

        assigned_count = np.nan
        if assigned_col and assigned_col in docs.columns:
            assigned_count = int((docs[assigned_col] == tid).sum())

        for _, cr in review_comments.iterrows():
            comment_sample_rows.append(
                {
                    "topic_id": tid,
                    "sample_rank": int(cr.get("sample_rank", 0)),
                    "sample_source": cr.get("sample_source", ""),
                    "comment_id": cr.get("comment_id", ""),
                    "帖子id": cr.get("帖子id", ""),
                    "comment_level": cr.get("comment_level", ""),
                    "like_count": cr.get("like_count", ""),
                    "reply_count": cr.get("reply_count", ""),
                    "robot_status": cr.get("robot_status", ""),
                    "human_role": cr.get("human_role", ""),
                    "content": cr.get("content", ""),
                }
            )

        rows.append(
            {
                "topic_id": tid,
                "raw_count": int(len(sub)),
                "assigned_count": assigned_count,
                "n_posts_raw": n_posts,
                "top_post_share_raw": top_post_share,
                "level1_share_raw": level1_share,
                "level2_share_raw": level2_share,
                "top_terms": row["top_terms"],
                "representative_docs": row.get("Representative_Docs", ""),
                "sample_comments_10": format_comments_compact(review_comments),
                "top_like_examples": format_examples(top_like, top_like_n),
                "post_diverse_examples": format_examples(post_diverse, post_diverse_n),
                "random_examples": format_examples(random_ex, random_n),
            }
        )

    review_df = pd.DataFrame(rows).sort_values("raw_count", ascending=False).reset_index(drop=True)
    post_diag_df = pd.DataFrame(post_rows).sort_values(["topic_id", "raw_count"], ascending=[True, False])
    comment_samples_df = pd.DataFrame(comment_sample_rows).sort_values(
        ["topic_id", "sample_rank"], ascending=[True, True]
    )
    return review_df, post_diag_df, comment_samples_df


def generate_final_review_materials(cfg: TopicDiscoveryConfig, final_nr: int) -> dict[str, Path]:
    final_dir = materialize_final_model(cfg, final_nr)
    topics_csv = final_dir / "topics_final.csv"
    doc_topics_csv = final_dir / "doc_topics_final.csv"
    review_df, post_diag, comment_samples = build_enhanced_topic_review_table(
        cfg, topics_csv=topics_csv, doc_topics_csv=doc_topics_csv
    )
    review_path = cfg.review_dir / f"topic_review_sheet_final_nr{final_nr}.csv"
    post_diag_path = cfg.review_dir / f"topic_post_diagnostics_final_nr{final_nr}.csv"
    samples_path = cfg.review_dir / f"topic_comment_samples_final_nr{final_nr}.csv"
    review_df.to_csv(review_path, index=False)
    post_diag.to_csv(post_diag_path, index=False)
    comment_samples.to_csv(samples_path, index=False)

    base_cols = [
        "topic_id",
        "raw_count",
        "assigned_count",
        "n_posts_raw",
        "top_post_share_raw",
        "level1_share_raw",
        "level2_share_raw",
        "top_terms",
        "representative_docs",
        "sample_comments_10",
    ]
    paths: dict[str, Path] = {
        "review": review_path,
        "post_diag": post_diag_path,
        "comment_samples": samples_path,
    }
    for coder in (1, 2):
        sheet = review_df[base_cols].copy()
        sheet["domain"] = ""
        sheet["label"] = ""
        sheet["notes"] = ""
        p = cfg.review_dir / f"coder{coder}_sheet_final_nr{final_nr}.csv"
        sheet.to_csv(p, index=False)
        paths[f"coder{coder}"] = p

    template = review_df[["topic_id", "raw_count", "top_terms", "top_post_share_raw"]].copy()
    for col in ("final_domain", "final_label", "adjudication_notes", "validation_flag"):
        template[col] = ""
    map_path = cfg.review_dir / "final_topic_map_template.csv"
    template.to_csv(map_path, index=False)
    paths["final_topic_map_template"] = map_path
    return paths


def compute_coder_agreement(cfg: TopicDiscoveryConfig, final_nr: int) -> pd.DataFrame | None:
    c1_path = cfg.review_dir / f"coder1_sheet_final_nr{final_nr}_done.csv"
    c2_path = cfg.review_dir / f"coder2_sheet_final_nr{final_nr}_done.csv"
    if not (c1_path.is_file() and c2_path.is_file()):
        c1_path = cfg.review_dir / f"coder1_sheet_final_nr{final_nr}.csv"
        c2_path = cfg.review_dir / f"coder2_sheet_final_nr{final_nr}.csv"
    c1 = pd.read_csv(c1_path)
    c2 = pd.read_csv(c2_path)
    for col in ("domain", "label"):
        c1[col] = c1[col].fillna("").astype(str).str.strip()
        c2[col] = c2[col].fillna("").astype(str).str.strip()
    if c1["domain"].eq("").all() or c2["domain"].eq("").all():
        return None
    merged = c1[["topic_id", "domain", "label", "notes"]].merge(
        c2[["topic_id", "domain", "label", "notes"]],
        on="topic_id",
        suffixes=("_c1", "_c2"),
    )
    domain_kappa = cohen_kappa_score(merged["domain_c1"], merged["domain_c2"])
    label_kappa = cohen_kappa_score(merged["label_c1"], merged["label_c2"])
    disagree = merged[merged["domain_c1"] != merged["domain_c2"] | (merged["label_c1"] != merged["label_c2"])].copy()
    summary = pd.DataFrame(
        [
            {"metric": "domain_cohen_kappa", "value": domain_kappa},
            {"metric": "label_cohen_kappa", "value": label_kappa},
            {"metric": "n_topics", "value": len(merged)},
            {"metric": "n_domain_disagreements", "value": int((merged["domain_c1"] != merged["domain_c2"]).sum())},
            {"metric": "n_label_disagreements", "value": int((merged["label_c1"] != merged["label_c2"]).sum())},
        ]
    )
    out_summary = cfg.review_dir / "coder_agreement_summary.csv"
    out_disagree = cfg.review_dir / "coder_disagreements.csv"
    summary.to_csv(out_summary, index=False)
    disagree.to_csv(out_disagree, index=False)
    return summary


def build_final_topic_map_from_adjudication(cfg: TopicDiscoveryConfig, final_nr: int) -> Path | None:
    adj_path = cfg.review_dir / "final_topic_map.csv"
    if not adj_path.is_file():
        return None
    return adj_path


def backfill_final_labels(cfg: TopicDiscoveryConfig, final_nr: int) -> Path | None:
    map_path = cfg.review_dir / "final_topic_map.csv"
    if not map_path.is_file():
        return None
    topic_map = pd.read_csv(map_path)
    if topic_map["final_domain"].astype(str).str.strip().eq("").any():
        return None
    final_doc = pd.read_csv(cfg.review_dir / "final_model" / "doc_topics_final.csv")
    topic_col = "topic_reduced"
    merged = final_doc.merge(
        topic_map[["topic_id", "final_domain", "final_label"]],
        left_on=topic_col,
        right_on="topic_id",
        how="left",
    )
    merged = merged[merged[topic_col] >= 0].copy()
    out = cfg.review_dir / "comments_with_final_domains.csv"
    merged.to_csv(out, index=False)

    stats_rows: list[dict[str, Any]] = []
    for (dom, lab), g in merged.groupby(["final_domain", "final_label"], dropna=False):
        stats_rows.append(
            {
                "final_domain": dom,
                "final_label": lab,
                "n_comments": len(g),
                "share_comments": len(g) / len(merged),
                "n_topics": g["topic_id"].nunique(),
                "n_posts": g["帖子id"].nunique(),
            }
        )
    pd.DataFrame(stats_rows).sort_values("n_comments", ascending=False).to_csv(
        cfg.review_dir / "final_domain_descriptive_stats.csv", index=False
    )

    if "robot_status" in merged.columns:
        cross = pd.crosstab(merged["final_domain"], merged["robot_status"], normalize="index")
        cross.to_csv(cfg.review_dir / "final_domain_by_robot_status.csv")
    return out


def sample_purity_validation(cfg: TopicDiscoveryConfig, final_nr: int, n_per_domain: int = 5, seed: int = 42) -> Path:
    map_path = cfg.review_dir / "final_topic_map.csv"
    comments_path = cfg.review_dir / "comments_with_final_domains.csv"
    if comments_path.is_file():
        df = pd.read_csv(comments_path)
    else:
        final_doc = pd.read_csv(cfg.review_dir / "final_model" / "doc_topics_final.csv")
        review = pd.read_csv(cfg.review_dir / f"topic_review_sheet_final_nr{final_nr}.csv")
        df = final_doc[final_doc["topic_reduced"] >= 0].merge(review[["topic_id", "top_terms"]], left_on="topic_reduced", right_on="topic_id")
        df["final_domain"] = ""
        df["final_label"] = ""
        if map_path.is_file():
            m = pd.read_csv(map_path)
            df = df.merge(m[["topic_id", "final_domain", "final_label"]], on="topic_id", how="left", suffixes=("", "_map"))
            df["final_domain"] = df["final_domain_map"].fillna(df["final_domain"])
            df["final_label"] = df["final_label_map"].fillna(df["final_label"])

    rng = np.random.default_rng(seed)
    samples: list[pd.DataFrame] = []
    labeled = df[df["final_domain"].astype(str).str.strip().ne("") & df["final_domain"].notna()]
    if labeled.empty:
        # Pre-coding: sample comments per machine topic for boundary review
        topic_col = "topic_reduced" if "topic_reduced" in df.columns else "topic_id"
        for tid, g in df.groupby(topic_col):
            if int(tid) < 0:
                continue
            k = min(n_per_domain, len(g))
            samples.append(g.sample(n=k, random_state=int(rng.integers(0, 1_000_000))))
    else:
        for dom, g in labeled.groupby("final_domain"):
            if str(dom).strip() == "" or pd.isna(dom):
                continue
            k = min(n_per_domain, len(g))
            samples.append(g.sample(n=k, random_state=int(rng.integers(0, 1_000_000))))
    out_df = pd.concat(samples, ignore_index=True) if samples else df.head(0)
    out_df["purity_check_pass"] = ""
    out_df["purity_notes"] = ""
    out_path = cfg.review_dir / "purity_validation_sample.csv"
    out_df.to_csv(out_path, index=False)
    return out_path


def run_sensitivity_analyses(cfg: TopicDiscoveryConfig, final_nr: int, curve_df: pd.DataFrame) -> None:
    sens_dir = cfg.review_dir / "sensitivity"
    sens_dir.mkdir(parents=True, exist_ok=True)
    neighbors = sorted({k for k in curve_df["target_nr_topics"] if abs(k - final_nr) <= 10 and k != final_nr})
    neighbor_rows = curve_df[curve_df["target_nr_topics"].isin(neighbors + [final_nr])]
    neighbor_rows.to_csv(sens_dir / "adjacent_topic_number_comparison.csv", index=False)

    base_doc = pd.read_csv(cfg.run_dir / f"bert_hdbscan_mcs{cfg.base_mcs}" / "doc_topics.csv")
    raw_valid = base_doc[base_doc["topic_raw"] >= 0]
    assigned_valid = base_doc[base_doc["topic_assigned"] >= 0]
    pd.DataFrame(
        [
            {
                "view": "topic_raw",
                "n_assigned": len(raw_valid),
                "n_topics": raw_valid["topic_raw"].nunique(),
                "outlier_rate": float((base_doc["topic_raw"] == -1).mean()),
            },
            {
                "view": "topic_assigned",
                "n_assigned": len(assigned_valid),
                "n_topics": assigned_valid["topic_assigned"].nunique(),
                "outlier_rate": float((base_doc["topic_assigned"] == -1).mean()),
            },
        ]
    ).to_csv(sens_dir / "outlier_raw_vs_assigned.csv", index=False)

    review = pd.read_csv(cfg.review_dir / f"topic_review_sheet_final_nr{final_nr}.csv")
    high_dom = review[review["top_post_share_raw"] >= 0.3].sort_values("top_post_share_raw", ascending=False)
    high_dom.to_csv(sens_dir / "high_post_dominance_topics.csv", index=False)

    mcs_rows = [summarize_hdbscan_candidate(m, cfg.run_dir) for m in cfg.hdbscan_candidate_mcs]
    pd.DataFrame(mcs_rows).to_csv(sens_dir / "hdbscan_mcs_sensitivity_summary.csv", index=False)


def write_codebook(cfg: TopicDiscoveryConfig, final_nr: int) -> Path:
    text = f"""# Topic Coding Codebook (final nr={final_nr})

## Analysis unit
- One row = one **comment** (`comment_id`), not post/user/thread.

## Machine vs human layers
- Machine `topic_id`: BERTopic+HDBSCAN candidate cluster after `reduce_topics(nr={final_nr})`.
- Coder `domain`: higher-level discourse domain (open inductive; merge synonyms after round 1).
- Coder `label`: specific theme name for the machine topic.
- `mixed/unclear`: allowed when evidence is insufficient.

## Evidence to use (in order)
1. `top_terms` + `representative_docs`
2. `sample_comments_10` (10 comments per topic; full fields in `topic_comment_samples_final_nr{final_nr}.csv`)
3. Legacy blocks `top_like_examples` / `post_diverse_examples` / `random_examples` remain in review sheet only

## Diagnostics
- `top_post_share_raw` > 0.30: check single-post dominance before naming.
- Compare `level1_share_raw` vs `level2_share_raw` for reply-structure bias.

## Agreement
- Two independent coders fill `coder1_sheet_final_nr{final_nr}.csv` and `coder2_sheet_final_nr{final_nr}.csv`.
- Rename completed files to `*_done.csv` before running agreement.
- Adjudicator fills `final_topic_map.csv` with `final_domain`, `final_label`, `adjudication_notes`.

## Primary analysis field
- Use raw/non-outlier topics for main human merge; `topic_assigned` is sensitivity only.
"""
    out = cfg.review_dir / "topic_coding_codebook.md"
    out.write_text(text, encoding="utf-8")
    return out


def export_high_risk_topic_audit(cfg: TopicDiscoveryConfig, final_nr: int) -> Path:
    """Pre-coding purity audit: flag topics with dominance or evidence mismatch risk."""
    review = pd.read_csv(cfg.review_dir / f"topic_review_sheet_final_nr{final_nr}.csv")
    review["risk_flags"] = ""
    flags: list[str] = []
    for _, row in review.iterrows():
        f: list[str] = []
        if float(row.get("top_post_share_raw", 0)) >= 0.30:
            f.append("high_post_dominance")
        if str(row.get("top_terms", "")).strip() == "":
            f.append("missing_top_terms")
        flags.append("|".join(f) if f else "")
    review["risk_flags"] = flags
    out = cfg.review_dir / f"high_risk_topics_final_nr{final_nr}.csv"
    review[review["risk_flags"] != ""].to_csv(out, index=False)
    return out


def write_output_manifest(cfg: TopicDiscoveryConfig, final_nr: int) -> Path:
    files = [
        "corpus_freeze.json",
        "hdbscan_candidate_summary.csv",
        "topic_number_cv_curve.csv",
        "topic_number_cv_curve.png",
        "topic_number_candidate_diagnostics.csv",
        "topic_number_selection_notes.md",
        "final_model_selection.json",
        f"topic_review_sheet_final_nr{final_nr}.csv",
        f"topic_post_diagnostics_final_nr{final_nr}.csv",
        f"coder1_sheet_final_nr{final_nr}.csv",
        f"coder2_sheet_final_nr{final_nr}.csv",
        f"topic_comment_samples_final_nr{final_nr}.csv",
        "topic_coding_codebook.md",
        "adjudication_guide.md",
        "final_topic_map_template.csv",
        "purity_validation_sample.csv",
        f"high_risk_topics_final_nr{final_nr}.csv",
        "METHODS.md",
        "REPRO.md",
        "sensitivity/adjacent_topic_number_comparison.csv",
        "sensitivity/outlier_raw_vs_assigned.csv",
        "sensitivity/high_post_dominance_topics.csv",
        "sensitivity/hdbscan_mcs_sensitivity_summary.csv",
        "final_model/topics_final.csv",
        "final_model/doc_topics_final.csv",
    ]
    rows = []
    for rel in files:
        p = cfg.review_dir / rel
        rows.append({"path": rel, "exists": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0})
    out = cfg.review_dir / "output_manifest.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def write_repro_documentation(cfg: TopicDiscoveryConfig, final_nr: int) -> Path:
    doc = f"""# Topic Discovery Reproducibility Pack

## Frozen inputs
- Run ID: `{cfg.run_id}`
- Analysis unit: `{cfg.analysis_unit}`
- Shared corpus: `{cfg.shared_corpus_path}`
- Corpus freeze: `topic_discovery_review/corpus_freeze.json`

## Pipeline commands

```bash
# Full pipeline (from repo root, venv python)
./.venv/bin/python -m phase1.run_topic_discovery --step all

# Individual steps
./.venv/bin/python -m phase1.run_topic_discovery --step freeze
./.venv/bin/python -m phase1.run_topic_discovery --step select
./.venv/bin/python -m phase1.run_topic_discovery --step review
./.venv/bin/python -m phase1.run_topic_discovery --step sensitivity
./.venv/bin/python -m phase1.run_topic_discovery --step agreement   # after coders finish
./.venv/bin/python -m phase1.run_topic_discovery --step backfill      # after adjudication
```

## Final model
- Base HDBSCAN: `mcs={cfg.base_mcs}`
- Selected `reduce_topics` target: **nr={final_nr}**
- Selection notes: `topic_number_selection_notes.md`
- Final topics: `final_model/topics_final.csv`
- Final assignments: `final_model/doc_topics_final.csv`

## Coder materials
- Review sheet: `topic_review_sheet_final_nr{final_nr}.csv`
- Coder sheets: `coder1_sheet_final_nr{final_nr}.csv`, `coder2_sheet_final_nr{final_nr}.csv`
- Codebook: `topic_coding_codebook.md`
- Adjudication template: `final_topic_map_template.csv` → fill as `final_topic_map.csv`

## Appendix tables
| File | Purpose |
|------|---------|
| `topic_number_cv_curve.csv` | C_V vs target nr_topics |
| `topic_number_cv_curve.png` | Coherence curve figure |
| `topic_number_candidate_diagnostics.csv` | Structural diagnostics per candidate |
| `hdbscan_candidate_summary.csv` | HDBSCAN mcs comparison |
| `topic_post_diagnostics_final_nr{final_nr}.csv` | Topic-by-post dominance |
| `sensitivity/*` | Model/outlier/post-dominance sensitivity |
| `coder_agreement_summary.csv` | Cohen's kappa (after coding) |
| `final_domain_descriptive_stats.csv` | Backfilled domain stats |
| `output_manifest.csv` | File existence checklist |
"""
    out = cfg.review_dir / "REPRO.md"
    out.write_text(doc, encoding="utf-8")
    return out


def run_pipeline(cfg: TopicDiscoveryConfig | None = None, *, steps: set[str] | None = None) -> dict[str, Any]:
    cfg = cfg or TopicDiscoveryConfig()
    cfg.review_dir.mkdir(parents=True, exist_ok=True)
    all_steps = steps or {"all"}
    if "all" in all_steps:
        all_steps = {"freeze", "select", "review", "codebook", "sensitivity", "validate", "document"}

    results: dict[str, Any] = {}
    if "freeze" in all_steps:
        results["corpus_freeze"] = str(freeze_corpus_snapshot(cfg))
        results["hdbscan_summary"] = str(write_hdbscan_candidate_summary(cfg))

    curve_df: pd.DataFrame | None = None
    final_nr: int | None = None
    if "select" in all_steps:
        curve_df, _ = scan_topic_numbers(cfg)
        final_nr, notes = select_final_topic_number(curve_df, cfg)
        results["final_nr"] = final_nr
        results["selection_notes"] = notes
    else:
        sel_path = cfg.review_dir / "final_model_selection.json"
        if sel_path.is_file():
            with open(sel_path, encoding="utf-8") as f:
                final_nr = int(json.load(f)["selected_target_nr_topics"])
        curve_path = cfg.review_dir / "topic_number_cv_curve.csv"
        if curve_path.is_file():
            curve_df = pd.read_csv(curve_path)

    if final_nr is None and any(s in all_steps for s in ("review", "codebook", "sensitivity", "validate", "agreement", "backfill", "document")):
        raise RuntimeError("final_nr unknown; run --step select first")

    if "review" in all_steps:
        paths = generate_final_review_materials(cfg, final_nr)
        results["review_paths"] = {k: str(v) for k, v in paths.items()}

    if "codebook" in all_steps:
        results["codebook"] = str(write_codebook(cfg, final_nr))

    if "sensitivity" in all_steps and curve_df is not None:
        run_sensitivity_analyses(cfg, final_nr, curve_df)
        results["sensitivity_dir"] = str(cfg.review_dir / "sensitivity")

    if "validate" in all_steps:
        results["purity_sample"] = str(sample_purity_validation(cfg, final_nr))
        results["high_risk_topics"] = str(export_high_risk_topic_audit(cfg, final_nr))

    if "agreement" in all_steps:
        summary = compute_coder_agreement(cfg, final_nr)
        if summary is not None:
            results["agreement"] = summary.to_dict("records")

    if "backfill" in all_steps:
        out = backfill_final_labels(cfg, final_nr)
        if out:
            results["backfill"] = str(out)

    if "document" in all_steps:
        if final_nr is None:
            raise RuntimeError("final_nr unknown; run --step select first")
        results["repro_doc"] = str(write_repro_documentation(cfg, final_nr))
        results["output_manifest"] = str(write_output_manifest(cfg, final_nr))

    return results
