#!/usr/bin/env python3
"""Two-round canonical consolidation of open codes (batch size ≤200).

Not axial / selective coding — synonym / near-duplicate merge only.

Example smoke:
  .venv/bin/python -m human_label_llm.run_concept_merge \\
    --concepts-long output/concept_extract/.../concepts_long.csv \\
    --limit-batches 1 --rounds 1

Full two rounds:
  .venv/bin/python -m human_label_llm.run_concept_merge \\
    --concepts-long output/concept_extract/.../concepts_long.csv
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from human_label_llm.format import fill_prompt
from human_label_llm.llm_client import ChatClient, ModelSpec, ProviderChain
from human_label_llm.prompts import load_spec
from human_label_llm.run import reload_project_api_keys

DEFAULT_CONCEPTS_LONG = (
    ROOT
    / "output/concept_extract/20261119_youtube_l1_open_concepts_v3_robot_imagination_self"
    / "concepts_long.csv"
)
SEED_R1 = 20261120
SEED_R2 = 20261121
BATCH_SIZE = 200
PROMPT_ID = "20261120_concept_merge_v1"

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_json_obj(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty model content")
    m = _JSON_FENCE_RE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in: {raw[:200]!r}")
    obj = json.loads(raw[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON is not an object")
    return obj


def load_unique_concepts(concepts_long: Path) -> tuple[list[str], dict[str, list[str]], dict[str, int]]:
    df = pd.read_csv(concepts_long, dtype={"comment_id": str})
    if "concept_raw" not in df.columns:
        raise ValueError(f"Missing concept_raw in {concepts_long}")
    df["concept_raw"] = df["concept_raw"].map(lambda x: str(x).strip() if pd.notna(x) else "")
    df = df[df["concept_raw"].ne("")]
    support: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for concept, grp in df.groupby("concept_raw", sort=False):
        ids = sorted({str(c) for c in grp["comment_id"].tolist() if str(c).strip()})
        support[str(concept)] = ids
        counts[str(concept)] = int(len(grp))
    # Stable unique list before shuffle: sort for determinism of the set
    unique = sorted(support.keys())
    return unique, support, counts


def shuffle_batches(items: list[str], *, seed: int, batch_size: int) -> list[list[str]]:
    rng = np.random.default_rng(seed)
    arr = np.array(items, dtype=object)
    rng.shuffle(arr)
    shuffled = [str(x) for x in arr.tolist()]
    batches: list[list[str]] = []
    for i in range(0, len(shuffled), batch_size):
        batches.append(shuffled[i : i + batch_size])
    return batches


def write_batch_inputs(round_dir: Path, batches: list[list[str]], seed: int) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "seed.txt").write_text(f"{seed}\n", encoding="utf-8")
    for i, chunk in enumerate(batches):
        path = round_dir / f"batch_{i:03d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_clusters(raw_clusters: Any, batch_items: list[str]) -> list[dict[str, Any]]:
    """Validate members ⊆ batch; fill missing as singletons; drop unknown members."""
    batch_set = set(batch_items)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    if not isinstance(raw_clusters, list):
        raw_clusters = []
    for cl in raw_clusters:
        if not isinstance(cl, dict):
            continue
        canonical = str(cl.get("canonical") or "").strip()
        members_raw = cl.get("members") or []
        if not isinstance(members_raw, list):
            continue
        members: list[str] = []
        for m in members_raw:
            s = str(m).strip()
            if s in batch_set and s not in seen:
                members.append(s)
                seen.add(s)
        if not members:
            continue
        if not canonical:
            canonical = members[0]
        out.append({"canonical": canonical, "members": members})
    for s in batch_items:
        if s not in seen:
            out.append({"canonical": s, "members": [s]})
            seen.add(s)
    return out


class BatchLogStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[str] = set()
        self._ok_parsed: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    bid = str(rec.get("batch_id") or "")
                    if not bid:
                        continue
                    self._done.add(bid)
                    if rec.get("status") == "ok" and isinstance(rec.get("clusters"), list):
                        self._ok_parsed[bid] = rec["clusters"]

    def has_ok(self, batch_id: str) -> bool:
        return batch_id in self._ok_parsed

    def get_ok(self, batch_id: str) -> list[dict[str, Any]] | None:
        return self._ok_parsed.get(batch_id)

    def append(self, rec: dict[str, Any]) -> None:
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            bid = str(rec.get("batch_id") or "")
            if bid and rec.get("status") == "ok" and isinstance(rec.get("clusters"), list):
                self._ok_parsed[bid] = rec["clusters"]
                self._done.add(bid)


def build_merge_messages(concepts: list[str]) -> list[dict[str, str]]:
    spec = load_spec(PROMPT_ID)
    concepts_json = json.dumps(concepts, ensure_ascii=False, indent=2)
    values = {"concepts_json": concepts_json}
    user = fill_prompt(spec.template, values, active_slots=["concepts_json"])
    system = fill_prompt(spec.system, {}, active_slots=[]) if spec.system else ""
    if system:
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return [{"role": "user", "content": user}]


def _repair_json_text(text: str) -> str:
    """Best-effort fixes for common LLM JSON glitches."""
    s = text.strip()
    # Trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def merge_one_batch(
    chain: ProviderChain,
    batch_id: str,
    concepts: list[str],
    *,
    temperature: float,
    max_tokens: int,
    round_dir: Path,
) -> dict[str, Any]:
    messages = build_merge_messages(concepts)
    t0 = time.time()
    provider = ""
    model = ""
    content = ""
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            if attempt == 1:
                messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            'Your previous reply was invalid JSON. Return ONLY valid JSON: '
                            '{"clusters":[{"canonical":"...","members":["..."]}]} '
                            "with every input string in exactly one members list."
                        ),
                    }
                ]
            resp, provider, model = chain.chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )
            content = ChatClient.extract_text(resp)
            (round_dir / f"{batch_id}.response.json").write_text(
                json.dumps(
                    {
                        "provider": provider,
                        "model": model,
                        "attempt": attempt,
                        "content": content,
                        "raw_resp": resp,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            try:
                obj = _extract_json_obj(content)
            except (json.JSONDecodeError, ValueError):
                obj = _extract_json_obj(_repair_json_text(content))
            clusters = normalize_clusters(obj.get("clusters"), concepts)
            return {
                "batch_id": batch_id,
                "status": "ok",
                "provider": provider,
                "model": model,
                "n_input": len(concepts),
                "n_clusters": len(clusters),
                "clusters": clusters,
                "elapsed_s": round(time.time() - t0, 3),
                "ts": _utc_now(),
                "error": "",
            }
        except Exception as e:
            last_err = e
            continue
    return {
        "batch_id": batch_id,
        "status": "api_error",
        "provider": provider,
        "model": model,
        "n_input": len(concepts),
        "n_clusters": 0,
        "clusters": [],
        "elapsed_s": round(time.time() - t0, 3),
        "ts": _utc_now(),
        "error": f"{type(last_err).__name__}: {last_err}",
    }


def run_round_llm(
    batches: list[list[str]],
    round_dir: Path,
    *,
    concurrency: int,
    temperature: float,
    max_tokens: int,
    timeout: int,
    limit_batches: int | None,
) -> list[dict[str, Any]]:
    reload_project_api_keys()
    # Prefer Moonshot direct when OpenRouter kimi-k3 returns credit/402; same model family.
    chain = ProviderChain(
        ModelSpec(
            key="kimi_k3_or",
            chain=[
                ("moonshot", "kimi-k3"),
                ("openrouter", "moonshotai/kimi-k3"),
            ],
            reasoning_mode="off",
        ),
        timeout=timeout,
    )
    store = BatchLogStore(round_dir / "log.jsonl")
    n = len(batches) if limit_batches is None else min(len(batches), limit_batches)
    jobs: list[tuple[str, list[str]]] = []
    for i in range(n):
        batch_id = f"batch_{i:03d}"
        if store.has_ok(batch_id):
            continue
        jobs.append((batch_id, batches[i]))

    print(f"[merge] pending={len(jobs)} / {n}  log={round_dir / 'log.jsonl'}")
    results_by_id: dict[str, list[dict[str, Any]]] = {
        f"batch_{i:03d}": store.get_ok(f"batch_{i:03d}") or []
        for i in range(n)
        if store.has_ok(f"batch_{i:03d}")
    }

    if jobs:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {
                ex.submit(
                    merge_one_batch,
                    chain,
                    bid,
                    concepts,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    round_dir=round_dir,
                ): bid
                for bid, concepts in jobs
            }
            for fut in tqdm(as_completed(futs), total=len(futs), desc="merge"):
                rec = fut.result()
                store.append(rec)
                if rec["status"] == "ok":
                    results_by_id[rec["batch_id"]] = rec["clusters"]
                else:
                    print(f"[WARN] {rec['batch_id']}: {rec['error'][:200]}")

    # Fail hard if any pending batch still missing ok
    missing = [f"batch_{i:03d}" for i in range(n) if f"batch_{i:03d}" not in results_by_id]
    if missing:
        raise RuntimeError(
            f"{len(missing)} batches failed or incomplete (e.g. {missing[:5]}). "
            "Re-run to resume after fixing API issues."
        )

    ordered: list[dict[str, Any]] = []
    for i in range(n):
        bid = f"batch_{i:03d}"
        for cl in results_by_id[bid]:
            ordered.append({**cl, "batch_id": bid})
    return ordered


def assign_ids(
    clusters: list[dict[str, Any]], *, prefix: str
) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]]:
    """Return clusters_df, member->canon_id, member->canonical label."""
    rows = []
    member_to_id: dict[str, str] = {}
    member_to_label: dict[str, str] = {}
    for idx, cl in enumerate(clusters, start=1):
        cid = f"{prefix}_{idx:05d}"
        members = list(cl["members"])
        canonical = str(cl["canonical"])
        rows.append(
            {
                "canon_id": cid,
                "canonical": canonical,
                "members_json": json.dumps(members, ensure_ascii=False),
                "n_members": len(members),
                "batch_id": cl.get("batch_id", ""),
            }
        )
        for m in members:
            member_to_id[m] = cid
            member_to_label[m] = canonical
    return pd.DataFrame(rows), member_to_id, member_to_label


def export_mapping(
    *,
    merge_root: Path,
    support: dict[str, list[str]],
    counts: dict[str, int],
    raw_to_c1_id: dict[str, str],
    raw_to_c1_label: dict[str, str],
    c1_label_to_c2_id: dict[str, str],
    c1_label_to_c2_label: dict[str, str],
    c1_clusters: pd.DataFrame,
    c2_clusters: pd.DataFrame | None,
) -> Path:
    # Build peer maps for merged_with
    c1_peers: dict[str, list[str]] = {}
    for _, row in c1_clusters.iterrows():
        members = json.loads(row["members_json"])
        for m in members:
            c1_peers[m] = [x for x in members if x != m]

    c2_peers_by_c1_label: dict[str, list[str]] = {}
    if c2_clusters is not None:
        for _, row in c2_clusters.iterrows():
            members = json.loads(row["members_json"])  # these are C1 canonical labels
            for m in members:
                c2_peers_by_c1_label[m] = [x for x in members if x != m]

    rows = []
    for raw in sorted(support.keys()):
        c1_id = raw_to_c1_id.get(raw, "")
        c1_lab = raw_to_c1_label.get(raw, "")
        c2_id = c1_label_to_c2_id.get(c1_lab, "") if c2_clusters is not None else ""
        c2_lab = c1_label_to_c2_label.get(c1_lab, "") if c2_clusters is not None else ""
        rows.append(
            {
                "concept_raw": raw,
                "n_mentions": counts.get(raw, 0),
                "comment_ids": json.dumps(support.get(raw, []), ensure_ascii=False),
                "canon_id_r1": c1_id,
                "canonical_r1": c1_lab,
                "canon_id_r2": c2_id,
                "canonical_r2": c2_lab,
                "merged_with_r1": json.dumps(c1_peers.get(raw, []), ensure_ascii=False),
                "merged_with_r2": json.dumps(
                    c2_peers_by_c1_label.get(c1_lab, []), ensure_ascii=False
                ),
            }
        )
    out = merge_root / "concept_mapping.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def write_readme(merge_root: Path) -> None:
    text = """# Concept canonical consolidation (not axial coding)

Two rounds of synonym / near-duplicate merge on kimi-k3 open codes.
Method framing: **canonical consolidation of open codes** — not Strauss–Corbin
axial coding (no coding paradigm) and not selective coding (no core category).

- Round1 seed: 20261120; Round2 seed: 20261121
- Batch size ≤ 200; residual tail batches kept
- Singletons retained
- Prompt: `human_label_llm/prompt/20261120_concept_merge_v1.md`
- Model: kimi-k3 via Moonshot (`api.moonshot.cn`) with OpenRouter fallback; reasoning off

Main deliverable: `concept_mapping.csv` (concept_raw → C1 → C2 + comment supports).
"""
    (merge_root / "merge_README.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--concepts-long", type=Path, default=DEFAULT_CONCEPTS_LONG)
    p.add_argument("--merge-root", type=Path, default=None)
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    p.add_argument("--seed-r1", type=int, default=SEED_R1)
    p.add_argument("--seed-r2", type=int, default=SEED_R2)
    p.add_argument("--rounds", type=int, choices=(1, 2), default=2)
    p.add_argument("--limit-batches", type=int, default=None, help="Smoke: only first N batches")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Completion budget (lower if OpenRouter returns HTTP 402 credit errors)",
    )
    p.add_argument("--timeout", type=int, default=300)
    args = p.parse_args(argv)

    concepts_long = args.concepts_long.resolve()
    merge_root = (args.merge_root or concepts_long.parent / "merge").resolve()
    merge_root.mkdir(parents=True, exist_ok=True)
    write_readme(merge_root)

    unique, support, counts = load_unique_concepts(concepts_long)
    print(f"[merge] unique={len(unique)} mentions_tracked={sum(counts.values())}")

    # --- Round 1 ---
    r1_dir = merge_root / "round1"
    batches1 = shuffle_batches(unique, seed=args.seed_r1, batch_size=args.batch_size)
    write_batch_inputs(r1_dir, batches1, args.seed_r1)
    print(f"[merge] round1 batches={len(batches1)}")
    clusters1 = run_round_llm(
        batches1,
        r1_dir,
        concurrency=args.concurrency,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        limit_batches=args.limit_batches,
    )
    c1_df, raw_to_c1_id, raw_to_c1_label = assign_ids(clusters1, prefix="C1")
    c1_df.to_csv(r1_dir / "clusters.csv", index=False)
    c1_df.to_csv(merge_root / "clusters_r1.csv", index=False)
    print(f"[merge] round1 clusters={len(c1_df)}")

    c2_df: pd.DataFrame | None = None
    c1_label_to_c2_id: dict[str, str] = {}
    c1_label_to_c2_label: dict[str, str] = {}

    if args.rounds == 2:
        # Round2 input = unique C1 canonical labels (one per C1 cluster)
        c1_labels = c1_df["canonical"].astype(str).tolist()
        # If duplicate canonical strings across C1 ids, keep distinct labels for merge input
        # but map via label; rare. Prefer unique labels list in cluster order.
        r2_dir = merge_root / "round2"
        batches2 = shuffle_batches(c1_labels, seed=args.seed_r2, batch_size=args.batch_size)
        write_batch_inputs(r2_dir, batches2, args.seed_r2)
        print(f"[merge] round2 batches={len(batches2)}")
        clusters2 = run_round_llm(
            batches2,
            r2_dir,
            concurrency=args.concurrency,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            limit_batches=args.limit_batches,
        )
        c2_df, c1_label_to_c2_id, c1_label_to_c2_label = assign_ids(clusters2, prefix="C2")
        c2_df.to_csv(r2_dir / "clusters.csv", index=False)
        c2_df.to_csv(merge_root / "clusters_r2.csv", index=False)
        print(f"[merge] round2 clusters={len(c2_df)}")

    # If smoke with limit_batches, mapping only covers raws that appeared in those batches
    if args.limit_batches is not None:
        covered_raw = set(raw_to_c1_id.keys())
        support = {k: v for k, v in support.items() if k in covered_raw}
        counts = {k: v for k, v in counts.items() if k in covered_raw}

    out = export_mapping(
        merge_root=merge_root,
        support=support,
        counts=counts,
        raw_to_c1_id=raw_to_c1_id,
        raw_to_c1_label=raw_to_c1_label,
        c1_label_to_c2_id=c1_label_to_c2_id,
        c1_label_to_c2_label=c1_label_to_c2_label,
        c1_clusters=c1_df,
        c2_clusters=c2_df,
    )
    print(f"[merge] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
