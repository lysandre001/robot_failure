"""§5 — hierarchical merge candidates from topic c-TF-IDF linkage."""
from __future__ import annotations

import ast
from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import pdist

from .paths import EXP, PRIMARY_MCS, validity_dir


def _patch_pickle_umap() -> None:
    import sys

    import tools.youtube_en_subject_bertopic_sentiment as bert_run

    sys.modules.setdefault("__main__", sys.modules[__name__])
    setattr(sys.modules["__main__"], "_PassthroughUMAP", bert_run._PassthroughUMAP)


def _parse_words(cell: Any) -> str:
    if isinstance(cell, list):
        return ", ".join(str(x) for x in cell[:8])
    try:
        parsed = ast.literal_eval(str(cell))
        if isinstance(parsed, list):
            return ", ".join(str(x) for x in parsed[:8])
    except (SyntaxError, ValueError):
        pass
    return str(cell)[:120]


def run_hierarchy() -> None:
    out = validity_dir()
    sub = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}"
    model_path = sub / "model.pkl"
    if not model_path.is_file():
        (out / "hierarchy_merge_candidates.csv").write_text("error,model_missing\n", encoding="utf-8")
        return

    from bertopic import BERTopic

    _patch_pickle_umap()
    bt = BERTopic.load(str(model_path))

    topics = pd.read_csv(sub / "topics.csv")
    word_by_topic = {
        int(r["Topic"]): _parse_words(r.get("Representation"))
        for _, r in topics.iterrows()
        if int(r["Topic"]) != -1
    }
    topic_ids = sorted(word_by_topic.keys())
    if not topic_ids:
        pd.DataFrame().to_csv(out / "hierarchy_merge_candidates.csv", index=False)
        return

    ctfidf = bt.c_tf_idf_
    dense = ctfidf.toarray() if hasattr(ctfidf, "toarray") else np.asarray(ctfidf)
    topic_to_row = {t: i for i, t in enumerate(sorted(bt.get_topics().keys())) if t != -1}
    rows = np.vstack([dense[topic_to_row[t]] for t in topic_ids if t in topic_to_row])
    if len(rows) < 2:
        pd.DataFrame().to_csv(out / "hierarchy_merge_candidates.csv", index=False)
        return

    dist = pdist(rows, metric="cosine")
    Z = linkage(dist, method="average")
    hier_df = pd.DataFrame(
        Z,
        columns=["Child_Left_ID", "Child_Right_ID", "Distance", "n_points"],
    )
    hier_df.insert(0, "merge_step", range(1, len(hier_df) + 1))
    hier_df.to_csv(out / "hierarchical_linkage.csv", index=False)

    n_leaves = len(topic_ids)
    merge_rows: list[dict] = []
    for i, row in enumerate(Z):
        left = int(row[0])
        right = int(row[1])
        merge_rows.append(
            {
                "merge_step": i + 1,
                "child_left_index": left,
                "child_right_index": right,
                "child_left_topic_id": topic_ids[left] if left < n_leaves else "",
                "child_right_topic_id": topic_ids[right] if right < n_leaves else "",
                "distance": row[2],
                "keywords_left": word_by_topic.get(topic_ids[left], "") if left < n_leaves else "",
                "keywords_right": word_by_topic.get(topic_ids[right], "") if right < n_leaves else "",
                "decision": "",
                "rationale": "",
            }
        )
    pd.DataFrame(merge_rows).to_csv(out / "hierarchy_merge_candidates.csv", index=False)

    thr = float(np.quantile(Z[:, 2], 0.25))
    map_rows = [
        {
            "topic_id": tid,
            "upper_narrative_id": f"cluster_at_dist<={thr:.4f}",
            "notes": "Manual map: cut linkage at 25th pct distance",
        }
        for tid in topic_ids
    ]
    pd.DataFrame(map_rows).to_csv(out / "topic_to_upper_map_draft.csv", index=False)