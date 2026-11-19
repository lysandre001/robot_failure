#!/usr/bin/env python3
"""English YouTube L1 subset: BERTopic + CardiffNLP RoBERTa sentiment.

Corpus gate (not topic labels): language==en and subject_labels intersects
{Robot, Imagination about Robots, Self}. Follows the HRI Companion 2026
pipeline shape (bottom-up BERTopic + RoBERTa sentiment).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "output/label_runs/20261116_youtube_l1_subject_topic9_kimi_k3"
    / "youtube_2events_clean_comments_with_subject_labels.csv"
)
DEFAULT_RUN_ID = "2026-11-16_youtube_en_robot_imagination_self_bertopic"
SUBJECT_KEEP = ("Robot", "Imagination about Robots", "Self")
MCS_GRID = (30, 50, 80, 100, 200)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"


def _split_labels(value: Any) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "nan":
        return []
    out: list[str] = []
    for part in re.split(r"[|,]", text):
        tok = part.strip()
        if tok and tok not in out:
            out.append(tok)
    return out


def filter_corpus(input_csv: Path, out_dir: Path) -> pd.DataFrame:
    usecols = [
        "comment_id",
        "帖子id",
        "comment_level",
        "language",
        "content",
        "content_en",
        "subject_labels",
        "subject_label_note",
        "platform",
        "source_batch",
        "like_count",
        "reply_count",
        "robot_status",
        "human_role",
        "post_category",
    ]
    df = pd.read_csv(
        input_csv,
        dtype={"comment_id": str, "帖子id": str},
        usecols=usecols,
        low_memory=False,
    )
    df["subject_label_list"] = df["subject_labels"].map(_split_labels)
    keep = set(SUBJECT_KEEP)
    mask_subject = df["subject_label_list"].map(lambda xs: bool(keep.intersection(xs)))
    mask_en = df["language"].fillna("").astype(str).str.lower().eq("en")
    mask_text = df["content"].fillna("").astype(str).str.strip().ne("")
    out = df[mask_subject & mask_en & mask_text].copy()
    out["has_robot"] = out["subject_label_list"].map(lambda xs: "Robot" in xs)
    out["has_imagination"] = out["subject_label_list"].map(
        lambda xs: "Imagination about Robots" in xs
    )
    out["has_self"] = out["subject_label_list"].map(lambda xs: "Self" in xs)
    out["doc_text"] = out["content"].astype(str).str.strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "analysis_corpus.csv"
    out.to_csv(path, index=False)
    summary = {
        "n": int(len(out)),
        "by_batch": out["source_batch"].value_counts().to_dict(),
        "n_robot": int(out["has_robot"].sum()),
        "n_imagination": int(out["has_imagination"].sum()),
        "n_self": int(out["has_self"].sum()),
        "comment_levels": out["comment_level"].value_counts().to_dict(),
    }
    (out_dir / "corpus_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return out


class _PassthroughUMAP:
    def __init__(self, reduced: np.ndarray):
        self.embedding_ = reduced

    def fit(self, X=None, y=None):
        return self

    def transform(self, X=None):
        return self.embedding_

    def fit_transform(self, X=None, y=None):
        return self.embedding_


def _select_mcs(rows: list[dict[str, Any]]) -> int:
    """Prefer manageable topic count and moderate outlier rate."""
    scored = []
    for r in rows:
        n_topics = int(r["n_topics"])
        out_rate = float(r["outlier_rate"])
        # Prefer 15–60 topics; outlier 0.15–0.45
        topic_pen = 0.0
        if n_topics < 10:
            topic_pen = (10 - n_topics) * 2
        elif n_topics > 80:
            topic_pen = (n_topics - 80) * 0.5
        elif 15 <= n_topics <= 60:
            topic_pen = 0.0
        else:
            topic_pen = abs(n_topics - 35) * 0.1
        out_pen = abs(out_rate - 0.30) * 10
        scored.append((topic_pen + out_pen, int(r["mcs"]), r))
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][1]


def run_bertopic(corpus: pd.DataFrame, out_dir: Path, *, device: str = "cpu") -> dict[str, Any]:
    from bertopic import BERTopic
    from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    docs = corpus["doc_text"].tolist()
    emb_path = out_dir / "embeddings.npy"
    if emb_path.is_file() and emb_path.stat().st_size > 0:
        embeddings = np.load(emb_path)
        if len(embeddings) != len(docs):
            embeddings = None
        else:
            print(f"[embed] loaded {emb_path} shape={embeddings.shape}")
    else:
        embeddings = None

    encoder = SentenceTransformer(EMBEDDING_MODEL, device=device)
    if embeddings is None:
        print(f"[embed] encoding {len(docs)} docs with {EMBEDDING_MODEL}…")
        embeddings = encoder.encode(
            docs,
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        np.save(emb_path, embeddings)
        print(f"[embed] saved {emb_path}")

    n_doc = len(docs)
    umap_n_neighbors = min(15, max(2, n_doc - 1))
    umap_path = out_dir / "umap_reduced.npy"
    if umap_path.is_file() and np.load(umap_path).shape[0] == n_doc:
        reduced = np.load(umap_path)
        print(f"[umap] loaded {umap_path}")
    else:
        print(f"[umap] fit n_neighbors={umap_n_neighbors}")
        reduced = UMAP(
            n_neighbors=umap_n_neighbors,
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=42,
        ).fit_transform(embeddings)
        np.save(umap_path, reduced)

    passthrough = _PassthroughUMAP(reduced)
    representation_model = [KeyBERTInspired(), MaximalMarginalRelevance(diversity=0.3)]

    sensitivity_rows: list[dict[str, Any]] = []
    for mcs in MCS_GRID:
        sub = out_dir / f"bert_hdbscan_mcs{mcs}"
        existing_topics = sub / "doc_topics.csv"
        existing_info = sub / "topics.csv"
        if existing_topics.is_file() and existing_info.is_file():
            topics = pd.read_csv(existing_topics)["topic"].to_numpy()
            n_topics = len({t for t in topics.tolist() if t != -1})
            outlier_rate = float(np.mean(topics == -1))
            sensitivity_rows.append(
                {
                    "mcs": mcs,
                    "n_topics": n_topics,
                    "outlier_rate": round(outlier_rate, 4),
                    "n_docs": n_doc,
                    "n_outliers": int(np.sum(topics == -1)),
                    "reused": True,
                }
            )
            print(f"[bertopic] mcs={mcs} reused topics={n_topics} outlier={outlier_rate:.3f}")
            continue

        print(f"[bertopic] mcs={mcs}")
        hdb = HDBSCAN(
            min_cluster_size=mcs,
            min_samples=mcs,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )
        # Fresh vectorizer each run; a fitted instance breaks the next MCS.
        vectorizer = CountVectorizer(
            stop_words="english",
            min_df=5,
            max_df=0.9,
            ngram_range=(1, 2),
            max_features=10000,
        )
        bt = BERTopic(
            embedding_model=encoder,
            umap_model=passthrough,
            hdbscan_model=hdb,
            vectorizer_model=vectorizer,
            representation_model=representation_model,
            calculate_probabilities=False,
            verbose=True,
        )
        try:
            topics, _ = bt.fit_transform(docs, embeddings)
        except ValueError as e:
            print(f"[bertopic] mcs={mcs} skipped: {e}")
            continue
        topics = np.asarray(topics)
        n_topics = len({t for t in topics.tolist() if t != -1})
        outlier_rate = float(np.mean(topics == -1))
        sub.mkdir(parents=True, exist_ok=True)
        info = bt.get_topic_info()
        info.to_csv(sub / "topics.csv", index=False)
        pd.DataFrame({"comment_id": corpus["comment_id"].values, "topic": topics}).to_csv(
            sub / "doc_topics.csv", index=False
        )
        try:
            bt.save(
                str(sub / "model"),
                serialization="safetensors",
                save_ctfidf=True,
                save_embedding_model=False,
            )
        except Exception as e:
            print(f"[warn] safetensors save failed ({e}); pickle")
            bt.save(
                str(sub / "model.pkl"),
                serialization="pickle",
                save_ctfidf=True,
                save_embedding_model=False,
            )
        sensitivity_rows.append(
            {
                "mcs": mcs,
                "n_topics": n_topics,
                "outlier_rate": round(outlier_rate, 4),
                "n_docs": n_doc,
                "n_outliers": int(np.sum(topics == -1)),
                "reused": False,
            }
        )
        del bt

    sens = pd.DataFrame(sensitivity_rows)
    sens.to_csv(out_dir / "hdbscan_sensitivity.csv", index=False)
    selected = _select_mcs(sensitivity_rows)
    meta = {
        "embedding_model": EMBEDDING_MODEL,
        "mcs_grid": list(MCS_GRID),
        "selected_mcs": selected,
        "sensitivity": sensitivity_rows,
        "selection_rule": "minimize |out_rate-0.30| + topic-count penalty; prefer 15-60 topics",
    }
    (out_dir / "bertopic_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def run_sentiment(corpus: pd.DataFrame, out_dir: Path, *, device: str = "cpu", batch_size: int = 32) -> pd.DataFrame:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = corpus["doc_text"].tolist()
    cache = out_dir / "sentiment_scores.csv"
    if cache.is_file():
        scored = pd.read_csv(cache, dtype={"comment_id": str})
        if len(scored) == len(corpus) and set(scored["comment_id"]) == set(corpus["comment_id"].astype(str)):
            print(f"[sentiment] loaded {cache}")
            return scored

    tok = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
    model.eval()
    if device.startswith("cuda") and torch.cuda.is_available():
        model = model.to("cuda")
        torch_device = "cuda"
    elif device == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        model = model.to("mps")
        torch_device = "mps"
    else:
        torch_device = "cpu"
        model = model.to("cpu")

    id2label = {int(k): v for k, v in model.config.id2label.items()}
    # normalize labels
    def norm_label(lab: str) -> str:
        s = lab.lower()
        if "neg" in s:
            return "negative"
        if "neu" in s:
            return "neutral"
        if "pos" in s:
            return "positive"
        return s

    labels: list[str] = []
    probs_neg: list[float] = []
    probs_neu: list[float] = []
    probs_pos: list[float] = []
    print(f"[sentiment] scoring {len(texts)} on {torch_device}…")
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tok(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            enc = {k: v.to(torch_device) for k, v in enc.items()}
            logits = model(**enc).logits
            prob = torch.softmax(logits, dim=-1).cpu().numpy()
            pred = prob.argmax(axis=-1)
            for j, pidx in enumerate(pred):
                labels.append(norm_label(str(id2label[int(pidx)])))
                # map columns by id2label order
                row = {norm_label(str(id2label[k])): float(prob[j, k]) for k in range(prob.shape[1])}
                probs_neg.append(row.get("negative", 0.0))
                probs_neu.append(row.get("neutral", 0.0))
                probs_pos.append(row.get("positive", 0.0))
            if (i // batch_size) % 20 == 0:
                print(f"[sentiment] {min(i + batch_size, len(texts))}/{len(texts)}")

    scored = pd.DataFrame(
        {
            "comment_id": corpus["comment_id"].astype(str).values,
            "sentiment": labels,
            "p_negative": probs_neg,
            "p_neutral": probs_neu,
            "p_positive": probs_pos,
        }
    )
    scored.to_csv(cache, index=False)
    print(f"[sentiment] wrote {cache}")
    return scored


def _topic_terms(info: pd.DataFrame, topic_id: int, k: int = 10) -> str:
    row = info[info["Topic"] == topic_id]
    if row.empty:
        return ""
    name = str(row.iloc[0].get("Name", "") or "")
    # Name often like "0_robot_human_..."
    parts = name.split("_")[1:]
    return ", ".join(parts[:k])


def build_outputs(corpus: pd.DataFrame, out_dir: Path, selected_mcs: int, sentiment: pd.DataFrame) -> None:
    sub = out_dir / f"bert_hdbscan_mcs{selected_mcs}"
    doc_topics = pd.read_csv(sub / "doc_topics.csv", dtype={"comment_id": str})
    info = pd.read_csv(sub / "topics.csv")
    base = corpus.copy()
    base["comment_id"] = base["comment_id"].astype(str)
    merged = base.merge(doc_topics, on="comment_id", how="left")
    merged = merged.merge(sentiment, on="comment_id", how="left")
    merged.to_csv(out_dir / "comment_assignments.csv", index=False)

    # topic x sentiment
    ct = (
        merged[merged["topic"] != -1]
        .groupby(["topic", "sentiment"])
        .size()
        .unstack(fill_value=0)
    )
    for col in ("negative", "neutral", "positive"):
        if col not in ct.columns:
            ct[col] = 0
    ct = ct[["negative", "neutral", "positive"]]
    ct["n"] = ct.sum(axis=1)
    for col in ("negative", "neutral", "positive"):
        ct[f"pct_{col}"] = (ct[col] / ct["n"]).round(4)
    ct.to_csv(out_dir / "topic_sentiment_crosstab.csv")

    # subject label presence x topic
    rows = []
    for label, col in (
        ("Robot", "has_robot"),
        ("Imagination about Robots", "has_imagination"),
        ("Self", "has_self"),
    ):
        sub_df = merged[merged[col]]
        vc = sub_df["topic"].value_counts()
        for topic_id, n in vc.items():
            rows.append({"subject_label": label, "topic": int(topic_id), "n": int(n)})
    pd.DataFrame(rows).to_csv(out_dir / "subject_label_topic_counts.csv", index=False)

    # review sheet
    review_rows = []
    topic_sizes = merged["topic"].value_counts().to_dict()
    for topic_id in sorted(t for t in topic_sizes if t != -1):
        part = merged[merged["topic"] == topic_id]
        n = len(part)
        sent = part["sentiment"].value_counts(normalize=True)
        # representative: prefer higher like_count then shorter
        reps = part.sort_values(["like_count", "doc_text"], ascending=[False, True]).head(5)
        review_rows.append(
            {
                "topic": topic_id,
                "n": n,
                "share": round(n / len(merged), 4),
                "top_terms": _topic_terms(info, topic_id),
                "pct_negative": round(float(sent.get("negative", 0.0)), 4),
                "pct_neutral": round(float(sent.get("neutral", 0.0)), 4),
                "pct_positive": round(float(sent.get("positive", 0.0)), 4),
                "pct_robot": round(float(part["has_robot"].mean()), 4),
                "pct_imagination": round(float(part["has_imagination"].mean()), 4),
                "pct_self": round(float(part["has_self"].mean()), 4),
                "example_1": reps.iloc[0]["doc_text"][:240] if len(reps) > 0 else "",
                "example_2": reps.iloc[1]["doc_text"][:240] if len(reps) > 1 else "",
                "example_3": reps.iloc[2]["doc_text"][:240] if len(reps) > 2 else "",
            }
        )
    review = pd.DataFrame(review_rows).sort_values("n", ascending=False)
    review.to_csv(out_dir / "topic_review_sheet.csv", index=False)

    # provisional mega-topic grouping (analyst, not dual-coded)
    provisional = _provisional_group(review)
    provisional.to_csv(out_dir / "provisional_mega_topics.csv", index=False)

    # short report
    outlier_n = int((merged["topic"] == -1).sum())
    sent_all = merged["sentiment"].value_counts(normalize=True)
    lines = [
        f"# YouTube EN subset BERTopic + RoBERTa ({out_dir.name})",
        "",
        "## Corpus",
        f"- Source: labeled Phase1 clean comments (two YouTube batches).",
        f"- Gate: `language==en` and `subject_labels` intersects "
        f"`{{Robot, Imagination about Robots, Self}}`.",
        f"- N={len(merged):,} L1 English comments "
        f"(Robot={int(merged['has_robot'].sum()):,}, "
        f"Imagination={int(merged['has_imagination'].sum()):,}, "
        f"Self={int(merged['has_self'].sum()):,}; overlapping).",
        "",
        "## Method",
        f"- Embedding: `{EMBEDDING_MODEL}`",
        f"- Clustering: UMAP(5D) + HDBSCAN; sensitivity MCS={list(MCS_GRID)}; "
        f"**selected MCS={selected_mcs}**",
        f"- Outliers kept as topic `-1` (n={outlier_n:,}, "
        f"{outlier_n / len(merged):.1%}); not force-assigned.",
        f"- Sentiment: `{SENTIMENT_MODEL}` → negative/neutral/positive.",
        "- Subject labels above are corpus gates only; topics are induced bottom-up.",
        "",
        "## Overall sentiment",
        f"- negative={sent_all.get('negative', 0):.1%}, "
        f"neutral={sent_all.get('neutral', 0):.1%}, "
        f"positive={sent_all.get('positive', 0):.1%}",
        "",
        f"## Selected solution (MCS={selected_mcs})",
        f"- Topics (excl. -1): {len(review)}",
        "",
        "| topic | n | terms | neg | neu | pos | robot% | imag% | self% |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in review.head(25).iterrows():
        lines.append(
            f"| {int(r['topic'])} | {int(r['n'])} | {r['top_terms'][:60]} | "
            f"{r['pct_negative']:.2f} | {r['pct_neutral']:.2f} | {r['pct_positive']:.2f} | "
            f"{r['pct_robot']:.2f} | {r['pct_imagination']:.2f} | {r['pct_self']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Provisional mega-topic grouping",
            "Analyst merge from keywords + examples. Not dual-coded; no Cohen's κ.",
            "",
        ]
    )
    for mega, g in provisional.groupby("mega_topic"):
        tids = ", ".join(str(int(x)) for x in g["topic"].tolist())
        lines.append(f"- **{mega}** (topics {tids}; n={int(g['n'].sum()):,})")
    lines.append("")
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] wrote {out_dir / 'REPORT.md'}")


def _provisional_group(review: pd.DataFrame) -> pd.DataFrame:
    """Heuristic analyst labels from top terms; transparent and revisable."""
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("Jobs_Labor_Displacement", ("job", "jobs", "work", "replace", "unemploy", "labor", "labour", "wage")),
        ("Creepy_Uncanny", ("creepy", "uncanny", "scary", "horror", "nightmare", "terrifying", "eerie")),
        ("Control_Program_Surveillance", ("control", "program", "hack", "code", "surveil", "remote", "puppet")),
        ("Religion_God", ("god", "jesus", "bible", "religion", "soul", "satan", "church")),
        ("Gender_Body_Identity", ("woman", "women", "girl", "sexy", "gender", "female", "male", "sex")),
        ("War_Military_Weapon", ("war", "military", "weapon", "army", "soldier", "kill", "china", "usa", "america")),
        ("Performance_Race_Ability", ("run", "race", "fast", "speed", "fall", "balance", "olympic", "marathon")),
        ("Awe_Reaction", ("wow", "omg", "amazing", "cool", "awesome", "wtf", "holy", "lol")),
        ("Future_Imagination", ("future", "human", "ai", "replace", "imagination", "terminator", "skynet")),
        ("Self_Personal_Stance", ("i ", "i'm", "me ", "my ", "we ", "us ")),
    ]
    rows = []
    for _, r in review.iterrows():
        terms = str(r["top_terms"]).lower()
        ex = " ".join(
            [
                str(r.get("example_1", "")),
                str(r.get("example_2", "")),
                str(r.get("example_3", "")),
            ]
        ).lower()
        blob = terms + " " + ex
        mega = "Robot_General_Other"
        for name, keys in rules:
            if any(k in blob for k in keys):
                mega = name
                break
        rows.append(
            {
                "topic": int(r["topic"]),
                "n": int(r["n"]),
                "top_terms": r["top_terms"],
                "mega_topic": mega,
                "grouping_basis": "analyst_heuristic_from_terms_and_examples",
            }
        )
    return pd.DataFrame(rows)


def register_run(run_id: str, out_dir: Path, selected_mcs: int, n: int) -> None:
    reg = ROOT / "output/experiments/registry.csv"
    row = {
        "run_id": run_id,
        "date": "2026-11-16",
        "task": "youtube_en_subject_subset_bertopic_sentiment",
        "hypothesis": "HRI Companion 2026-style bottom-up BERTopic + RoBERTa on EN Robot/Imagination/Self gate",
        "input_data": str(
            ROOT
            / "output/label_runs/20261116_youtube_l1_subject_topic9_kimi_k3"
            / "youtube_2events_clean_comments_with_subject_labels.csv"
        ),
        "method": f"{EMBEDDING_MODEL}+HDBSCAN+{SENTIMENT_MODEL}",
        "key_params": f"mcs_grid={list(MCS_GRID)};selected_mcs={selected_mcs};n={n};outliers_kept",
        "output_dir": str(out_dir),
        "status": "complete",
        "decision": "secondary_en_youtube; does_not_replace_xhs_current",
    }
    if reg.is_file():
        df = pd.read_csv(reg)
        df = df[df["run_id"] != run_id]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_csv(reg, index=False)
    print(f"[registry] appended {run_id}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--run-id", default=DEFAULT_RUN_ID)
    ap.add_argument("--device", default="cpu")
    ap.add_argument(
        "--step",
        choices=("all", "filter", "bertopic", "sentiment", "report"),
        default="all",
    )
    args = ap.parse_args()
    out_dir = ROOT / "output/experiments" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.step in ("all", "filter"):
        corpus = filter_corpus(args.input_csv, out_dir)
    else:
        corpus = pd.read_csv(out_dir / "analysis_corpus.csv", dtype={"comment_id": str})

    if args.step == "filter":
        return

    if args.step in ("all", "bertopic"):
        meta = run_bertopic(corpus, out_dir, device=args.device)
    else:
        meta = json.loads((out_dir / "bertopic_meta.json").read_text(encoding="utf-8"))

    if args.step == "bertopic":
        return

    if args.step in ("all", "sentiment"):
        sentiment = run_sentiment(corpus, out_dir, device=args.device)
    else:
        sentiment = pd.read_csv(out_dir / "sentiment_scores.csv", dtype={"comment_id": str})

    if args.step == "sentiment":
        return

    selected = int(meta["selected_mcs"])
    build_outputs(corpus, out_dir, selected, sentiment)
    register_run(args.run_id, out_dir, selected, len(corpus))


if __name__ == "__main__":
    main()
