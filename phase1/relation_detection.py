"""relation_v1 baseline detection with lightweight experiment tracking."""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class RelationExperimentConfig:
    run_id: str
    input_comments_csv: Path
    relation_lexicon_csv: Path
    experiments_root: Path
    phase1_data_dir: Path
    random_seed: int = 42
    topic_k: int = 12
    topic_sample_n: int = 12000
    min_df: int = 8
    max_df: float = 0.6
    max_features: int = 8000
    mirror_to_phase1_data: bool = False


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


_ZH_RE = re.compile(r"[\u4e00-\u9fff]+")
_EN_RE = re.compile(r"[a-zA-Z0-9]{2,}")


def _bigram_tokenize(text: str) -> list[str]:
    toks: list[str] = []
    s = str(text)
    for seq in _ZH_RE.findall(s):
        if len(seq) <= 2:
            toks.append(seq)
        else:
            toks.extend(seq[i : i + 2] for i in range(len(seq) - 1))
    toks.extend(w.lower() for w in _EN_RE.findall(s))
    return toks


def _build_topic_cluster(df: pd.DataFrame, cfg: RelationExperimentConfig) -> pd.Series:
    docs = df["content"].fillna("").astype(str)
    work = df.copy()
    if len(work) > cfg.topic_sample_n:
        work = work.sample(n=cfg.topic_sample_n, random_state=cfg.random_seed).copy()
    work = work.reset_index().rename(columns={"index": "_orig_idx"})

    vec = TfidfVectorizer(
        tokenizer=_bigram_tokenize,
        token_pattern=None,
        min_df=cfg.min_df,
        max_df=cfg.max_df,
        max_features=cfg.max_features,
    )
    X = vec.fit_transform(work["content"].tolist())
    km = MiniBatchKMeans(
        n_clusters=cfg.topic_k,
        random_state=cfg.random_seed,
        batch_size=512,
        n_init="auto",
    )
    labels = km.fit_predict(X)
    work["topic_cluster"] = labels

    out = pd.Series(data=-1, index=df.index, dtype=int)
    out.loc[work["_orig_idx"].values] = work["topic_cluster"].values
    return out


def run_relation_v1_experiment(cfg: RelationExperimentConfig) -> Path:
    run_dir = cfg.experiments_root / cfg.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    comments = pd.read_csv(cfg.input_comments_csv)
    comments["content"] = comments["content"].fillna("").astype(str)
    comments["like_count"] = pd.to_numeric(comments.get("like_count", 0), errors="coerce").fillna(0)
    comments["comment_level"] = pd.to_numeric(comments["comment_level"], errors="coerce")
    comments = comments[comments["content"].str.len() > 0].copy()

    lex = pd.read_csv(cfg.relation_lexicon_csv)
    rel_terms = {
        rel: sorted(set(g["term"].dropna().astype(str).str.strip()))
        for rel, g in lex.groupby("relation_type")
    }

    for rel, terms in rel_terms.items():
        hit_col = f"relation_{rel}_hits"
        flag_col = f"relation_{rel}_flag"
        comments[hit_col] = comments["content"].map(lambda t: sum(1 for w in terms if w and w in t))
        comments[flag_col] = (comments[hit_col] > 0).astype(int)

    flag_cols = [c for c in comments.columns if c.endswith("_flag") and c.startswith("relation_")]
    comments["relation_any_flag"] = (comments[flag_cols].sum(axis=1) > 0).astype(int)

    comments["topic_cluster"] = _build_topic_cluster(comments, cfg)

    # Core outputs
    comments.to_csv(run_dir / "relation_v1_comment_labels.csv", index=False)

    # Overall summary
    overall_rows = []
    n_total = len(comments)
    for rel in sorted(rel_terms.keys()):
        fcol = f"relation_{rel}_flag"
        hcol = f"relation_{rel}_hits"
        sub = comments[comments[fcol] == 1]
        overall_rows.append(
            {
                "relation_type": rel,
                "n_hit_comments": int(len(sub)),
                "hit_rate": float(len(sub) / n_total) if n_total else 0,
                "avg_hits_per_hit_comment": float(sub[hcol].mean()) if len(sub) else 0,
                "median_like_when_hit": float(sub["like_count"].median()) if len(sub) else 0,
            }
        )
    overall = pd.DataFrame(overall_rows).sort_values("n_hit_comments", ascending=False)
    overall.to_csv(run_dir / "relation_v1_overall.csv", index=False)

    # By post category
    by_pc_rows = []
    for pc, g in comments.groupby("post_category"):
        g_n = len(g)
        for rel in sorted(rel_terms.keys()):
            fcol = f"relation_{rel}_flag"
            sub = g[g[fcol] == 1]
            by_pc_rows.append(
                {
                    "post_category": pc,
                    "relation_type": rel,
                    "n_comments": int(g_n),
                    "n_hit_comments": int(len(sub)),
                    "hit_rate": float(len(sub) / g_n) if g_n else 0,
                }
            )
    by_pc = pd.DataFrame(by_pc_rows)
    by_pc.to_csv(run_dir / "relation_v1_by_post_category.csv", index=False)

    # By comment level
    by_lv_rows = []
    for lv, g in comments.groupby("comment_level"):
        g_n = len(g)
        for rel in sorted(rel_terms.keys()):
            fcol = f"relation_{rel}_flag"
            sub = g[g[fcol] == 1]
            by_lv_rows.append(
                {
                    "comment_level": int(lv) if pd.notna(lv) else lv,
                    "relation_type": rel,
                    "n_comments": int(g_n),
                    "n_hit_comments": int(len(sub)),
                    "hit_rate": float(len(sub) / g_n) if g_n else 0,
                }
            )
    by_lv = pd.DataFrame(by_lv_rows)
    by_lv.to_csv(run_dir / "relation_v1_by_comment_level.csv", index=False)

    # Top terms
    term_rows = []
    for rel, terms in rel_terms.items():
        for term in terms:
            mask = comments["content"].str.contains(term, regex=False)
            n = int(mask.sum())
            if n == 0:
                continue
            term_rows.append(
                {
                    "relation_type": rel,
                    "term": term,
                    "n_comments": n,
                    "share_in_all_comments": float(n / n_total) if n_total else 0,
                    "median_like": float(comments.loc[mask, "like_count"].median()),
                }
            )
    top_terms = pd.DataFrame(term_rows).sort_values(["relation_type", "n_comments"], ascending=[True, False])
    top_terms.to_csv(run_dir / "relation_v1_top_terms.csv", index=False)

    # Relation x topic cluster
    by_topic_rows = []
    for tc, g in comments[comments["topic_cluster"] >= 0].groupby("topic_cluster"):
        g_n = len(g)
        for rel in sorted(rel_terms.keys()):
            fcol = f"relation_{rel}_flag"
            n_hit = int(g[fcol].sum())
            by_topic_rows.append(
                {
                    "topic_cluster": int(tc),
                    "relation_type": rel,
                    "n_comments": int(g_n),
                    "n_hit_comments": n_hit,
                    "hit_rate": float(n_hit / g_n) if g_n else 0,
                }
            )
    by_topic = pd.DataFrame(by_topic_rows)
    by_topic.to_csv(run_dir / "relation_v1_by_topic_cluster.csv", index=False)

    # Relation x topic x post_category cube
    cube_rows = []
    topic_df = comments[comments["topic_cluster"] >= 0]
    for (tc, pc), g in topic_df.groupby(["topic_cluster", "post_category"]):
        g_n = len(g)
        for rel in sorted(rel_terms.keys()):
            fcol = f"relation_{rel}_flag"
            n_hit = int(g[fcol].sum())
            cube_rows.append(
                {
                    "topic_cluster": int(tc),
                    "post_category": pc,
                    "relation_type": rel,
                    "n_comments": int(g_n),
                    "n_hit_comments": n_hit,
                    "hit_rate": float(n_hit / g_n) if g_n else 0,
                }
            )
    cube = pd.DataFrame(cube_rows)
    cube.to_csv(run_dir / "relation_v1_topic_postcategory_cube.csv", index=False)

    # Minimal audit sample: 50 per relation (25 high-like + 25 boundary)
    audit_rows = []
    for rel in sorted(rel_terms.keys()):
        fcol = f"relation_{rel}_flag"
        sub = comments[comments[fcol] == 1].copy()
        if sub.empty:
            continue
        high = sub.sort_values("like_count", ascending=False).head(25)
        boundary = sub.sort_values(f"relation_{rel}_hits", ascending=True).head(25)
        sampled = pd.concat([high, boundary]).drop_duplicates(subset=["comment_id"]).head(50)
        sampled = sampled.assign(
            relation_type=rel,
            audit_label="",
            audit_note="",
        )
        audit_rows.append(
            sampled[
                [
                    "relation_type",
                    "comment_id",
                    "post_category",
                    "comment_level",
                    "like_count",
                    f"relation_{rel}_hits",
                    "content",
                    "audit_label",
                    "audit_note",
                ]
            ].rename(columns={f"relation_{rel}_hits": "hit_count"})
        )
    if audit_rows:
        audit = pd.concat(audit_rows, ignore_index=True)
    else:
        audit = pd.DataFrame(
            columns=[
                "relation_type",
                "comment_id",
                "post_category",
                "comment_level",
                "like_count",
                "hit_count",
                "content",
                "audit_label",
                "audit_note",
            ]
        )
    audit.to_csv(run_dir / "relation_v1_error_audit.csv", index=False)

    # metrics.csv
    metrics = pd.DataFrame(
        [
            {"metric": "n_comments", "value": float(n_total)},
            {"metric": "relation_any_coverage", "value": float(comments["relation_any_flag"].mean())},
            {
                "metric": "avg_relation_labels_per_comment",
                "value": float(comments[[c for c in flag_cols]].sum(axis=1).mean()),
            },
            {"metric": "n_topic_clustered_comments", "value": float((comments["topic_cluster"] >= 0).sum())},
        ]
    )
    metrics.to_csv(run_dir / "metrics.csv", index=False)

    config_payload = {
        "run_id": cfg.run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_data": str(cfg.input_comments_csv),
        "input_hash": _file_hash(cfg.input_comments_csv),
        "lexicon": str(cfg.relation_lexicon_csv),
        "lexicon_hash": _file_hash(cfg.relation_lexicon_csv),
        "method": "relation_v1_lexicon + tfidf_bigram_kmeans_topic_link",
        "params": {
            "random_seed": cfg.random_seed,
            "topic_k": cfg.topic_k,
            "topic_sample_n": cfg.topic_sample_n,
            "min_df": cfg.min_df,
            "max_df": cfg.max_df,
            "max_features": cfg.max_features,
            "mirror_to_phase1_data": cfg.mirror_to_phase1_data,
        },
    }
    (run_dir / "config.json").write_text(
        json.dumps(config_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_md = [
        "# relation_v1 experiment summary",
        "",
        f"- run_id: `{cfg.run_id}`",
        f"- input: `{cfg.input_comments_csv}`",
        f"- lexicon: `{cfg.relation_lexicon_csv}`",
        f"- coverage(any relation): `{comments['relation_any_flag'].mean():.2%}`",
        "",
        "## Top relation types by hit comments",
        "```",
        overall.head(6).to_string(index=False),
        "```",
        "",
        "## Notes",
        "- Baseline is lexicon matching; implicit metaphors are not fully captured.",
        "- Topic linking uses TF-IDF bigram + KMeans for lightweight comparability.",
    ]
    (run_dir / "summary.md").write_text("\n".join(summary_md), encoding="utf-8")

    if cfg.mirror_to_phase1_data:
        cfg.phase1_data_dir.mkdir(parents=True, exist_ok=True)
        mirrors = [
            "relation_v1_overall.csv",
            "relation_v1_by_post_category.csv",
            "relation_v1_by_comment_level.csv",
            "relation_v1_top_terms.csv",
            "relation_v1_by_topic_cluster.csv",
            "relation_v1_topic_postcategory_cube.csv",
            "relation_v1_error_audit.csv",
        ]
        for name in mirrors:
            (cfg.phase1_data_dir / name).write_bytes((run_dir / name).read_bytes())

    # Update registry
    registry = cfg.experiments_root / "registry.csv"
    with registry.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                cfg.run_id,
                datetime.now().strftime("%Y-%m-%d"),
                "relation_detection_v1",
                "关系范畴可形成稳定且可解释分布",
                str(cfg.input_comments_csv),
                "lexicon_baseline+topic_link",
                json.dumps({"topic_k": cfg.topic_k, "seed": cfg.random_seed}, ensure_ascii=False),
                str(run_dir),
                "done",
                "keep_as_v1_baseline",
            ]
        )
    return run_dir


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    run_id = f"{datetime.now().strftime('%Y-%m-%d')}_relation_detect_v1_lexicon"
    out = root / "output" / "phase1"
    unified = out / "clean_comments_unified.csv"
    if not unified.is_file():
        alt = out / "data" / "clean_comments_unified.csv"
        if alt.is_file():
            unified = alt
    cfg = RelationExperimentConfig(
        run_id=run_id,
        input_comments_csv=unified,
        relation_lexicon_csv=root / "config" / "relation_lexicon_v1.csv",
        experiments_root=root / "output" / "experiments",
        phase1_data_dir=root / "output" / "phase1" / "data",
        mirror_to_phase1_data=False,
    )
    run_dir = run_relation_v1_experiment(cfg)
    print("run_dir", run_dir)


if __name__ == "__main__":
    main()
