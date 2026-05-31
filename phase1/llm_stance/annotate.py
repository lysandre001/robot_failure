"""Annotate stance for all comments × all models, resume-safe.

Each model gets its own JSONL file at `<outdir>/<model_key>.jsonl`. Each line
is one comment's record:

    {"comment_id": "...", "model": "claude_4_7", "stance": "支持",
     "reason": "...", "raw": "...", "elapsed_s": 1.23, "ts": "..."}

Re-running the same command skips comment_ids already present in the JSONL.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from .openrouter_client import OpenRouterClient, DEFAULT_MODELS
from .prompts import build_messages


# --------------------------- Excel loader ----------------------------------- #

def load_comments(xlsx_path: str) -> pd.DataFrame:
    """Load the double-annotation Excel and return one row per comment.

    Columns returned: comment_id, post_id, post_category, post_title,
    post_body, content.
    """
    raw = pd.read_excel(xlsx_path, sheet_name=0, header=None)
    data = raw.iloc[2:].reset_index(drop=True)
    df = pd.DataFrame({
        "post_id":       data.iloc[:, 1].astype(str),
        "post_category": data.iloc[:, 3].astype(str),
        "post_title":    data.iloc[:, 4].astype(str),
        "post_body":     data.iloc[:, 5].astype(str),
        "comment_id":    data.iloc[:, 6].astype(str),
        "content":       data.iloc[:, 7].astype(str),
    })
    df = df[df["content"].str.strip().astype(bool) & (df["content"] != "nan")]
    df = df.drop_duplicates(subset=["comment_id"]).reset_index(drop=True)
    return df


# --------------------------- JSONL store ----------------------------------- #

class JsonlStore:
    """Append-only JSONL with O(1) duplicate check via an in-memory set."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[str] = set()
        self._lock = threading.Lock()
        if self.path.exists():
            with self.path.open() as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        cid = rec.get("comment_id")
                        if cid:
                            self._done.add(str(cid))
                    except json.JSONDecodeError:
                        continue

    def has(self, comment_id: str) -> bool:
        return str(comment_id) in self._done

    def append(self, rec: dict) -> None:
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            with self.path.open("a") as f:
                f.write(line + "\n")
            self._done.add(str(rec["comment_id"]))


# --------------------------- response parsing ------------------------------ #

_VALID_LABELS = {"支持", "中立", "反对"}
_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.S)


def parse_response(text: str) -> tuple[str, str]:
    """Parse model output into (stance, reason). Falls back to PARSE_ERROR."""
    if not text:
        return "PARSE_ERROR", ""
    # Try direct JSON load first
    candidates: list[str] = []
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.I | re.M)
    candidates.append(stripped)
    candidates.extend(_JSON_OBJ_RE.findall(text))
    for cand in candidates:
        try:
            obj = json.loads(cand)
            stance = str(obj.get("stance", "")).strip()
            reason = str(obj.get("reason", "")).strip()
            if stance in _VALID_LABELS:
                return stance, reason
        except json.JSONDecodeError:
            continue
    # Last-ditch: look for any of the three labels in raw text
    for lab in _VALID_LABELS:
        if lab in text:
            return lab, text.strip()[:200]
    return "PARSE_ERROR", text.strip()[:200]


# --------------------------- one call --------------------------------------- #

def annotate_one(
    client: OpenRouterClient,
    model_slug: str,
    row: pd.Series,
) -> dict:
    msgs = build_messages(
        post_title=row["post_title"],
        post_body=row["post_body"],
        post_category=row["post_category"],
        comment_text=row["content"],
    )
    t0 = time.time()
    try:
        resp = client.chat(model=model_slug, messages=msgs)
        text = OpenRouterClient.extract_text(resp)
        stance, reason = parse_response(text)
        if stance == "PARSE_ERROR":
            # one retry with a stricter reminder
            msgs2 = msgs + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "你的输出不符合 JSON 格式。请只输出 {\"stance\": ..., \"reason\": ...} 一个对象。"},
            ]
            resp = client.chat(model=model_slug, messages=msgs2)
            text = OpenRouterClient.extract_text(resp)
            stance, reason = parse_response(text)
        return {
            "comment_id": row["comment_id"],
            "stance": stance,
            "reason": reason,
            "raw": text,
            "elapsed_s": round(time.time() - t0, 3),
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "error": None,
        }
    except Exception as e:
        return {
            "comment_id": row["comment_id"],
            "stance": "API_ERROR",
            "reason": "",
            "raw": "",
            "elapsed_s": round(time.time() - t0, 3),
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "error": f"{type(e).__name__}: {e}",
        }


# --------------------------- main ------------------------------------------- #

def run(
    input_xlsx: str,
    outdir: str,
    model_map: dict[str, str],
    workers: int = 8,
    limit: int | None = None,
) -> None:
    df = load_comments(input_xlsx)
    if limit:
        df = df.head(limit)
    print(f"[load] {len(df)} comments from {input_xlsx}")

    client = OpenRouterClient()
    out_root = Path(outdir)
    out_root.mkdir(parents=True, exist_ok=True)

    for key, slug in model_map.items():
        store = JsonlStore(out_root / f"{key}.jsonl")
        pending = [r for _, r in df.iterrows() if not store.has(r["comment_id"])]
        print(f"[{key}] slug={slug}  pending={len(pending)}  done={len(df) - len(pending)}")
        if not pending:
            continue
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(annotate_one, client, slug, r): r["comment_id"] for r in pending}
            for fut in tqdm(as_completed(futs), total=len(futs), desc=key):
                rec = fut.result()
                rec["model"] = key
                store.append(rec)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Path to the annotation xlsx.")
    p.add_argument("--outdir", default="phase1/llm_stance/output")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", type=int, default=None, help="Smoke-test on first N.")
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help=(
            "Override model_key=slug pairs. "
            "Example: --models claude_4_7=anthropic/claude-sonnet-4.7 "
            "gpt_5_5=openai/gpt-5.5 gemini_3_1=google/gemini-3.1-pro"
        ),
    )
    return p.parse_args()


def main():
    args = parse_args()
    model_map = dict(DEFAULT_MODELS)
    if args.models:
        for kv in args.models:
            k, _, v = kv.partition("=")
            model_map[k] = v
    run(args.input, args.outdir, model_map, workers=args.workers, limit=args.limit)


if __name__ == "__main__":
    main()
