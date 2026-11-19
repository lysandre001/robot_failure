"""Scan BERTopic reduce_topics(nr) on the EN mcs=80 base model (numeric merge)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .paths import EXP, PRIMARY_MCS


def _patch_pickle_umap() -> None:
    import tools.youtube_en_subject_bertopic_sentiment as bert_run

    sys.modules.setdefault("__main__", sys.modules[__name__])
    setattr(sys.modules["__main__"], "_PassthroughUMAP", bert_run._PassthroughUMAP)


def _tokenize_en(texts: list[str]) -> list[list[str]]:
    pat = re.compile(r"\b[a-z]{2,}\b", re.I)
    return [pat.findall(str(t).lower()) for t in texts]


def _topic_word_lists(bt: Any, *, top_n: int = 10) -> list[list[str]]:
    out: list[list[str]] = []
    for tid in sorted(t for t in bt.get_topics().keys() if t != -1):
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
    filtered: list[list[str]] = []
    for words in topic_word_lists:
        kept = [w for w in words if w in dictionary.token2id]
        if len(kept) >= 2:
            filtered.append(kept)
    if not filtered:
        return float("nan")
    cm = CoherenceModel(
        topics=filtered,
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
    return {
        "n_topics_final": n_topics,
        "raw_outlier_rate": raw_outlier_rate,
        "valid_docs": valid_docs,
        "largest_topic_size": int(sizes.max()) if len(sizes) else 0,
        "largest_share_valid": largest_share_valid,
        "median_topic_size": float(sizes.median()) if len(sizes) else np.nan,
    }


def _load_base_model() -> Any:
    from bertopic import BERTopic

    _patch_pickle_umap()
    sub = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}"
    for rel in ("model", "model.pkl"):
        p = sub / rel
        if p.exists():
            return BERTopic.load(str(p)), sub
    raise FileNotFoundError(f"No BERTopic model under {sub}")


def scan(nr_list: list[int], out_dir: Path) -> pd.DataFrame:
    corpus = pd.read_csv(EXP / "analysis_corpus.csv")
    docs = corpus["doc_text"].astype(str).tolist()
    tokenized = _tokenize_en(docs)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for nr in nr_list:
        print(f"[reduce_scan] nr_topics={nr} …", flush=True)
        bt, sub = _load_base_model()
        try:
            bt.reduce_topics(docs, nr_topics=nr)
        except Exception as e:
            print(f"[WARN] reduce_topics({nr}) failed: {e}", flush=True)
            continue
        topics_arr = np.asarray(bt.topics_, dtype=int)
        cv = compute_cv_coherence(_topic_word_lists(bt), tokenized)
        diag = _structural_diagnostics(topics_arr)
        info = bt.get_topic_info()
        info.to_csv(out_dir / f"topics_nr{nr}.csv", index=False)
        base_doc = pd.read_csv(sub / "doc_topics.csv")
        out_doc = base_doc.copy()
        out_doc["topic_reduced"] = topics_arr
        out_doc.to_csv(out_dir / f"doc_topics_nr{nr}.csv", index=False)
        rows.append(
            {
                "target_nr_topics": nr,
                "c_v_coherence": cv,
                **diag,
                "report_tier_ok": bool(12 <= diag["n_topics_final"] <= 35),
                "max_cluster_ok": bool(diag["largest_share_valid"] <= 0.12),
            }
        )

    curve = pd.DataFrame(rows).sort_values("target_nr_topics").reset_index(drop=True)
    curve.to_csv(out_dir / "topic_number_curve.csv", index=False)
    return curve


def select_k(curve: pd.DataFrame) -> tuple[int, str]:
    """Pick report-tier K: prefer 12–35 topics, max C_V (12% max-cluster is advisory)."""
    notes: list[str] = [
        f"Base: bert_hdbscan_mcs{PRIMARY_MCS} (~60 HDBSCAN topics).",
        "Merge method: BERTopic reduce_topics (c-TF-IDF cosine), not keyword mega.",
        "Outlier rate unchanged by reduce_topics (~41.5% at -1).",
    ]
    tier = curve[curve["report_tier_ok"]].copy()
    if not tier.empty:
        pick = tier.loc[tier["c_v_coherence"].idxmax()]
        k = int(pick["target_nr_topics"])
        notes.append(
            f"Recommended report merge: nr={k} → {int(pick['n_topics_final'])} topics, "
            f"C_V={float(pick['c_v_coherence']):.4f}, "
            f"largest_share={float(pick['largest_share_valid']):.3f} "
            f"(no scanned nr≤35 met 12% max-cluster; pick by C_V within 12–35)."
        )
        if tier["max_cluster_ok"].any():
            best_struct = tier[tier["max_cluster_ok"]].loc[tier[tier["max_cluster_ok"]]["c_v_coherence"].idxmax()]
            notes.append(
                f"Structural alt (max_share≤12%): nr={int(best_struct['target_nr_topics'])} "
                f"if you need a flatter occupancy."
            )
        return k, "\n".join(notes)

    pick = curve.loc[curve["c_v_coherence"].idxmax()]
    k = int(pick["target_nr_topics"])
    notes.append(f"Fallback: max C_V at nr={k}.")
    return k, "\n".join(notes)


def materialize_selected(k: int, out_dir: Path) -> None:
    """Copy selected nr artifacts to stable names + save reduced model."""
    from bertopic import BERTopic
    from shutil import copy2

    src_topics = out_dir / f"topics_nr{k}.csv"
    src_docs = out_dir / f"doc_topics_nr{k}.csv"
    if not src_topics.is_file():
        raise FileNotFoundError(src_topics)
    copy2(src_topics, out_dir / "topics_reduced_selected.csv")
    copy2(src_docs, out_dir / "doc_topics_reduced_selected.csv")

    corpus = pd.read_csv(EXP / "analysis_corpus.csv")
    docs = corpus["doc_text"].astype(str).tolist()
    bt, sub = _load_base_model()
    bt.reduce_topics(docs, nr_topics=k)
    reduced_dir = sub / "model_reduced"
    reduced_dir.mkdir(parents=True, exist_ok=True)
    bt.save(str(reduced_dir), serialization="safetensors", save_ctfidf=True, save_embedding_model=False)
    print(f"[reduce_scan] saved model → {reduced_dir}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--nr",
        type=int,
        nargs="*",
        default=list(range(10, 56, 5)),
        help="target nr_topics values to scan (default 10,15,…,55)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "topic_reduce",
    )
    p.add_argument("--select-only", type=int, default=None, help="skip scan; materialize this nr")
    args = p.parse_args()
    out_dir = args.out

    if args.select_only is not None:
        materialize_selected(args.select_only, out_dir)
        return

    curve = scan(args.nr, out_dir)
    k, notes = select_k(curve)
    (out_dir / "topic_number_selection_notes.md").write_text(notes + "\n", encoding="utf-8")
    print(notes, flush=True)
    materialize_selected(k, out_dir)
    (out_dir / "selected_nr.txt").write_text(str(k) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()