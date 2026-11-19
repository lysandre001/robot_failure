"""Build Drive-ready exports: original vs reduce_topics + typical comment cases."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pandas as pd

from .paths import EXP, PRIMARY_MCS

RUN_TAG = "20261119_youtube_en_robot_imagination_self_N28096"
SELECTED_NR = 35
EXAMPLES_PER_TOPIC = 5
EXCERPT_CHARS = 480


def _parse_repr(cell) -> str:
    if isinstance(cell, list):
        return ", ".join(str(x) for x in cell[:12])
    s = str(cell)
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return ", ".join(str(x) for x in parsed[:12])
    except (SyntaxError, ValueError):
        pass
    return s[:500]


def _excerpt(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text)).strip()
    if len(t) <= EXCERPT_CHARS:
        return t
    return t[: EXCERPT_CHARS - 1] + "…"


def _topic_words_row(topics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in topics.iterrows():
        tid = int(r["Topic"])
        rows.append(
            {
                "topic_id": tid,
                "count": int(r["Count"]),
                "label_auto": str(r.get("Name", "")),
                "top_words": _parse_repr(r.get("Representation")),
            }
        )
    return pd.DataFrame(rows).sort_values("topic_id")


def _typical_comments(
    doc_col: str,
    topics_df: pd.DataFrame,
    *,
    layer: str,
) -> pd.DataFrame:
    corpus = pd.read_csv(
        EXP / "analysis_corpus.csv",
        dtype={"comment_id": str},
        usecols=[
            "comment_id",
            "doc_text",
            "like_count",
            "source_batch",
            "subject_labels",
            "has_robot",
            "has_imagination",
            "has_self",
        ],
    )
    docs = pd.read_csv(
        EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "topic_reduce" / "doc_topics_reduced_selected.csv",
        dtype={"comment_id": str},
    )
    if doc_col == "topic":
        docs = pd.read_csv(
            EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "doc_topics.csv",
            dtype={"comment_id": str},
        )
        key = "topic"
    else:
        key = "topic_reduced"

    merged = docs.merge(corpus, on="comment_id", how="left")
    merged["like_count"] = pd.to_numeric(merged["like_count"], errors="coerce").fillna(0)

    word_by_tid = {
        int(r["topic_id"]): r["top_words"]
        for _, r in topics_df.iterrows()
        if int(r["topic_id"]) != -1 or layer == "outlier_included"
    }
    # include -1 in topics_df always
    out_rows: list[dict] = []
    topic_ids = sorted(merged[key].unique(), key=lambda x: (x == -1, x))
    for tid in topic_ids:
        sub = merged[merged[key] == tid].sort_values("like_count", ascending=False)
        n_take = 3 if tid == -1 else EXAMPLES_PER_TOPIC
        for rank, (_, row) in enumerate(sub.head(n_take).iterrows(), start=1):
            out_rows.append(
                {
                    "layer": layer,
                    "topic_id": int(tid),
                    "top_words": word_by_tid.get(int(tid), ""),
                    "example_rank": rank,
                    "comment_id": row["comment_id"],
                    "like_count": float(row["like_count"]),
                    "source_batch": row.get("source_batch", ""),
                    "subject_labels": row.get("subject_labels", ""),
                    "has_robot": row.get("has_robot"),
                    "has_imagination": row.get("has_imagination"),
                    "has_self": row.get("has_self"),
                    "comment_text": str(row["doc_text"]).strip(),
                    "comment_excerpt": _excerpt(row["doc_text"]),
                }
            )
    return pd.DataFrame(out_rows)


def _mapping_table() -> pd.DataFrame:
    doc = pd.read_csv(
        EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "topic_reduce" / "doc_topics_reduced_selected.csv",
        dtype={"comment_id": str},
    )
    g = (
        doc.groupby(["topic_reduced", "topic"], as_index=False)
        .size()
        .rename(columns={"size": "n_comments"})
    )
    g["topic_hdbscan_original"] = g["topic"]
    g["topic_reduce_nr35"] = g["topic_reduced"]
    g = g.drop(columns=["topic", "topic_reduced"])
    return g.sort_values(["topic_reduce_nr35", "n_comments"], ascending=[True, False])


def _rationale_path() -> Path:
    p = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "topic_reduce" / "WHY_nr35_drive.md"
    if not p.is_file():
        raise FileNotFoundError(f"Missing {p}")
    return p


def build_slim(out_dir: Path) -> list[Path]:
    """Four files for Drive: why + topwords + mapping + typical comments."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}"
    red = base / "topic_reduce"

    orig = _topic_words_row(pd.read_csv(base / "topics.csv"))
    merged = _topic_words_row(pd.read_csv(red / "topics_reduced_selected.csv"))
    orig.insert(0, "analysis_tier", f"hdbscan_mcs{PRIMARY_MCS}")
    merged.insert(0, "analysis_tier", f"reduce_topics_nr{SELECTED_NR}")
    topwords = pd.concat([orig, merged], ignore_index=True)

    mapping = _mapping_table()
    ex = pd.concat(
        [
            _typical_comments("topic", orig, layer=f"hdbscan_mcs{PRIMARY_MCS}"),
            _typical_comments("topic_reduced", merged, layer=f"reduce_topics_nr{SELECTED_NR}"),
        ],
        ignore_index=True,
    )

    tag = RUN_TAG
    paths = [
        out_dir / f"{tag}_WHY_nr35.md",
        out_dir / f"{tag}_topics_topwords_original60_reduced34_nr35.csv",
        out_dir / f"{tag}_topic_mapping_hdbscan60_to_reduced_nr35.csv",
        out_dir / f"{tag}_typical_comments_original_and_reduced_nr35.csv",
    ]
    paths[0].write_text(_rationale_path().read_text(encoding="utf-8"), encoding="utf-8")
    topwords.to_csv(paths[1], index=False)
    mapping.to_csv(paths[2], index=False)
    ex.to_csv(paths[3], index=False)
    return paths


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}"
    red = base / "topic_reduce"

    orig_topics = _topic_words_row(pd.read_csv(base / "topics.csv"))
    red_topics = _topic_words_row(pd.read_csv(red / "topics_reduced_selected.csv"))

    p_orig = out_dir / f"{RUN_TAG}_hdbscan_mcs{PRIMARY_MCS}_topics_original_60count_topwords.csv"
    p_red = out_dir / f"{RUN_TAG}_reduce_topics_nr{SELECTED_NR}_merged_34count_topwords.csv"
    orig_topics.to_csv(p_orig, index=False)
    red_topics.to_csv(p_red, index=False)

    mapping = _mapping_table()
    p_map = out_dir / f"{RUN_TAG}_hdbscan60_to_reduced_nr{SELECTED_NR}_topic_mapping.csv"
    mapping.to_csv(p_map, index=False)

    ex_orig = _typical_comments("topic", orig_topics, layer=f"hdbscan_mcs{PRIMARY_MCS}")
    ex_red = _typical_comments("topic_reduced", red_topics, layer=f"reduce_topics_nr{SELECTED_NR}")
    p_ex_o = out_dir / f"{RUN_TAG}_hdbscan_mcs{PRIMARY_MCS}_typical_comments_by_topic.csv"
    p_ex_r = out_dir / f"{RUN_TAG}_reduce_topics_nr{SELECTED_NR}_typical_comments_by_topic.csv"
    ex_orig.to_csv(p_ex_o, index=False)
    ex_red.to_csv(p_ex_r, index=False)

    curve_src = red / "topic_number_curve.csv"
    if curve_src.is_file():
        pd.read_csv(curve_src).to_csv(
            out_dir / f"{RUN_TAG}_reduce_topics_scan_curve_nr10-55.csv", index=False
        )

    rationale_src = Path(__file__).resolve().parents[2] / "output" / "experiments" / (
        "2026-11-16_youtube_en_robot_imagination_self_bertopic/drive_export/"
        f"{RUN_TAG}/{RUN_TAG}_why_nr35_and_what_to_read.md"
    )
    if not rationale_src.is_file():
        rationale_src = out_dir / f"{RUN_TAG}_why_nr35_and_what_to_read.md"

    notes = (red / "topic_number_selection_notes.md").read_text(encoding="utf-8")
    readme = f"""YouTube EN L1 topic export ({RUN_TAG})
Corpus: Robot | Imagination about Robots | Self, language=en, N=28096
Embedding: all-MiniLM-L6-v2; HDBSCAN min_cluster_size={PRIMARY_MCS}

Files:
- *_hdbscan_mcs{PRIMARY_MCS}_topics_original_* : 60 HDBSCAN topics (+ outlier -1 in examples)
- *_reduce_topics_nr{SELECTED_NR}_* : BERTopic reduce_topics (c-TF-IDF merge), 34 non-outlier topics
- *_topic_mapping.csv : which original topic ids contribute to each reduced topic (by comment count)
- *_typical_comments_* : up to {EXAMPLES_PER_TOPIC} comments per topic (by like_count); outlier -1 has 3
- *_why_nr35_and_what_to_read.md : 哪些文件必读 / 为何选 nr=35（方法说明，建议先看）

Optional (can ignore): manifest.json only; mega-themes not in this package.

Selection notes:
{notes}
"""
    (out_dir / f"{RUN_TAG}_README.txt").write_text(readme, encoding="utf-8")

    manifest = {
        "run_tag": RUN_TAG,
        "n_corpus": 28096,
        "primary_mcs": PRIMARY_MCS,
        "n_topics_original_non_outlier": int((orig_topics["topic_id"] != -1).sum()),
        "reduce_nr_target": SELECTED_NR,
        "n_topics_reduced_non_outlier": int((red_topics["topic_id"] != -1).sum()),
        "files": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
    }
    (out_dir / f"{RUN_TAG}_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return out_dir


def main() -> None:
    import argparse
    import tempfile

    ap = argparse.ArgumentParser()
    ap.add_argument("--slim", action="store_true", help="4-file bundle only (for Drive)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.slim:
        out = args.out or Path(tempfile.mkdtemp(prefix="topic_drive_slim_"))
        paths = build_slim(out)
        print("\n".join(str(p) for p in paths))
        return
    build(args.out or EXP / "drive_export" / RUN_TAG)


if __name__ == "__main__":
    main()