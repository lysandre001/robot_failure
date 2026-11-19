#!/usr/bin/env python3
"""Ask OpenRouter GPT-6 Astra to revise a topic-9 labeling prompt.

Writes a new prompt markdown file. Refuses when the destination already exists.
The request and raw reply go to output/label_runs/<opt_run_id>/ as jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import yaml

from human_label_llm.llm_client import PROVIDER_CONFIGS, ChatClient
from human_label_llm.prompts import parse_prompt_md
from human_label_llm.run import _load_project_env

_load_project_env()

REQUIRED_LABELS = [
    "Robot",
    "Event or Competition",
    "Imagination about Robots",
    "Other People in Videos",
    "Other People in Comments",
    "Self",
    "Video or Media",
    "Affiliated Organization or Country",
    "No Clear Subject",
]

OPTIMIZER_MODEL = "openai/gpt-6-astra"

FIXED_NCS_RULE = (
    "No Clear Subject cannot appear together with any other category. "
    "It means the comment has no topic that fits the other eight categories. "
    "If one of those eight applies, do not also assign No Clear Subject. "
    "If none of them applies, assign No Clear Subject alone."
)


def split_labels(value: object) -> list[str]:
    return [part.strip() for part in str(value).replace(",", "|").split("|") if part.strip()]


def jaccard(human: list[str], pred: list[str]) -> float:
    gold, model = set(human), set(pred)
    if not gold and not model:
        return 1.0
    if not gold or not model:
        return 0.0
    return len(gold & model) / len(gold | model)


def metrics_table(wide_path: Path) -> str:
    df = pd.read_csv(wide_path, dtype=str, keep_default_na=False)
    pred_col, hit_col, _reason = _pred_columns(df)
    pred = df[pred_col].map(split_labels)
    gold = df["对象"].map(split_labels)
    any_hit = float(df[hit_col].map(_is_hit).mean()) if len(df) else 0.0
    mean_j = float(sum(jaccard(a, b) for a, b in zip(gold, pred)) / len(df)) if len(df) else 0.0
    mean_n = float(pred.map(len).mean()) if len(df) else 0.0
    combined = sum(1 for labels in pred if "No Clear Subject" in labels and len(labels) > 1)
    lines = [
        f"n={len(df)}  any-hit={any_hit:.4f}  mean_jaccard={mean_j:.4f}  "
        f"mean_predicted_labels={mean_n:.2f}  "
        f"no_clear_subject_combined_with_another={combined}",
        "label | n_gold | n_pred | recall | gold_share | pred_share",
    ]
    n = len(df) or 1
    for name in REQUIRED_LABELS:
        n_gold = sum(name in labels for labels in gold)
        n_pred = sum(name in labels for labels in pred)
        n_hit = sum(name in g and name in p for g, p in zip(gold, pred))
        recall = n_hit / n_gold if n_gold else 0.0
        lines.append(
            f"{name} | {n_gold} | {n_pred} | {recall:.3f} | {n_gold / n:.3f} | {n_pred / n:.3f}"
        )
    return "\n".join(lines)


def _pred_columns(df: pd.DataFrame) -> tuple[str, str, str]:
    hits = [c for c in df.columns if c.endswith("_any_hit")]
    if len(hits) != 1:
        raise SystemExit(f"expected one *_any_hit column, found {hits}")
    pred = hits[0][: -len("_any_hit")]
    return pred, hits[0], pred + "_reason"


def _is_hit(value: object) -> bool:
    return str(value).strip() in {"1", "1.0"}


def load_misses(wide_path: Path) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(wide_path, dtype=str, keep_default_na=False)
    pred, hit, reason = _pred_columns(df)
    miss = df[~df[hit].map(_is_hit)].copy()
    miss = miss.rename(columns={pred: "model_labels", reason: "model_note", "对象": "human_labels"})
    return miss, pred


def confusion_block(miss: pd.DataFrame) -> str:
    if miss.empty:
        return "(no misses)"
    counts = (
        miss.groupby(["human_labels", "model_labels"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
    )
    lines = [f"{int(r.n):4d}  human={r.human_labels}  model={r.model_labels}" for r in counts.itertuples()]
    return "\n".join(lines)


def example_block(miss: pd.DataFrame) -> str:
    rows = []
    for i, r in enumerate(miss.itertuples(), start=1):
        text = str(r.content_en).replace("\n", " ").strip()
        note = str(getattr(r, "model_note", "")).replace("\n", " ").strip()
        rows.append(
            f"{i}. comment: {text}\n"
            f"   human: {r.human_labels}\n"
            f"   model: {r.model_labels}\n"
            f"   note: {note}"
        )
    return "\n".join(rows)


def build_user_message(
    *,
    round_n: int,
    current_prompt: str,
    previous_prompt: str | None,
    misses: pd.DataFrame,
    prompt_id: str,
    purpose: str,
    metrics_text: str,
    base_metrics_text: str | None,
) -> str:
    if round_n == 1:
        edit_rule = (
            "This is revision round 1. Change category definitions, judgment rules, "
            "and examples. Do not paste specific comments from the bad cases into the "
            "new prompt unless a general rule cannot be stated without one short example."
        )
        before_after = ""
    else:
        edit_rule = (
            "This is revision round 2. You are shown the prompt before the last edit "
            "and the prompt after it, plus the bad cases that are still wrong. "
            "You may add at most 5 typical comments as positive or negative examples. "
            "Do not add more than 5 quoted comments."
        )
        before_after = (
            "\n\n# PROMPT BEFORE THE LAST EDIT\n"
            + (previous_prompt or "")
            + "\n\n# PROMPT AFTER THE LAST EDIT\n"
            + current_prompt
        )
    base_block = ""
    if base_metrics_text:
        base_block = f"\n\n# FULL-SET DISTRIBUTION FROM THE STARTING RUN\n{base_metrics_text}"
    return f"""Revise the labeling prompt so predicted labels match the human labels.
Judge every candidate by both of these, and by the category distribution:
- any-hit: the predicted set and the human set share at least one label
- Jaccard: intersection size divided by union size. An extra wrong label lowers Jaccard
Do not raise any-hit by assigning several frequent categories to the same comment.
Keep each category's predicted share close to its human share.

{edit_rule}

This rule is fixed. Copy it verbatim into the prompt and do not weaken, delete, or contradict it:
{FIXED_NCS_RULE}

Keep these exactly:
- The nine category names: {", ".join(REQUIRED_LABELS)}
- The input slot written as {{comment}} inside <comment> tags
- JSON output with fields labels (array) and note (string)
- Literal braces in the OUTPUT example must be doubled, like {{{{ and }}}}, because the file is later filled with str.format

Return only the complete markdown file, starting with YAML frontmatter.
Set id to {prompt_id}.
Set date to 2026-10-12.
Set purpose to: {purpose}

# CURRENT PROMPT
{current_prompt}
{before_after}

# METRICS AND CATEGORY DISTRIBUTION
{metrics_text}
{base_block}

# CONFUSION COUNTS (human -> model) ON THE MISSES
{confusion_block(misses)}

# BAD CASES
{example_block(misses)}
"""


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, count=1, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip() + "\n"


def enforce_exclusive_ncs(body: str) -> str:
    """Keep the exclusivity rule, and drop lines that tell the model to combine it."""
    kept: list[str] = []
    for line in body.splitlines():
        low = line.lower()
        mentions = "no clear subject" in low
        combines = any(
            phrase in low
            for phrase in (
                "as well",
                "together with",
                "along with",
                "also assign no clear",
                "also include no clear",
                "and no clear subject",
                ", no clear subject",
            )
        )
        protects = any(phrase in low for phrase in ("cannot", "do not", "alone", "not also"))
        if mentions and combines and not protects:
            continue
        kept.append(line)
    body = "\n".join(kept)
    if FIXED_NCS_RULE not in body:
        block = "# FIXED RULE\n" + FIXED_NCS_RULE + "\n\n"
        marker = "# JUDGMENT RULES"
        if marker in body:
            body = body.replace(marker, block + marker, 1)
        else:
            body = block + body
    return body


def ensure_format_slot(body: str) -> str:
    """Keep {comment} and double every other brace so str.format can fill the prompt."""
    try:
        body.format(comment="X")
        return body
    except (KeyError, ValueError, IndexError):
        token = "\x00COMMENT\x00"
        tmp = body.replace("{comment}", token).replace("{", "{{").replace("}", "}}")
        tmp = tmp.replace(token, "{comment}")
        tmp.format(comment="X")
        return tmp


def normalize_prompt(text: str, *, prompt_id: str, purpose: str) -> str:
    raw = _strip_fence(text)
    start = raw.find("\n---")
    if not raw.startswith("---") and start != -1:
        raw = raw[start + 1 :]
    meta, body = parse_prompt_md(raw)
    labels = [str(k) for k in (meta.get("label_map") or {})]
    missing = [name for name in REQUIRED_LABELS if name not in labels]
    if missing:
        raise SystemExit(f"optimizer dropped labels: {missing}")
    body = enforce_exclusive_ncs(body)
    body = ensure_format_slot(body)
    if "{comment}" not in body:
        raise SystemExit("optimizer dropped the {comment} slot")
    if FIXED_NCS_RULE not in body:
        raise SystemExit("optimizer dropped the No Clear Subject exclusivity rule")
    meta["id"] = prompt_id
    meta["version"] = str(meta.get("version") or "1.0.0")
    meta["date"] = "2026-10-12"
    meta["purpose"] = purpose
    dumped = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{dumped}\n---\n\n{body.strip()}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True, help="Prompt to revise, or the after-edit prompt on round 2")
    parser.add_argument("--previous-prompt", type=Path, default=None, help="Prompt before the last edit (round 2)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--opt-run-id", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--round", type=int, choices=(1, 2), required=True)
    parser.add_argument(
        "--base-wide",
        type=Path,
        default=None,
        help="Starting full-run comparison, used for the category distribution",
    )
    args = parser.parse_args()

    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    if args.round == 2 and args.previous_prompt is None:
        raise SystemExit("round 2 requires --previous-prompt")

    wide_path = args.wide if args.wide.is_absolute() else ROOT / args.wide
    misses, _pred = load_misses(wide_path)
    metrics_text = metrics_table(wide_path)
    base_metrics = None
    if args.base_wide is not None:
        base_path = args.base_wide if args.base_wide.is_absolute() else ROOT / args.base_wide
        base_metrics = metrics_table(base_path)
    current = (args.prompt if args.prompt.is_absolute() else ROOT / args.prompt).read_text(encoding="utf-8")
    previous = None
    if args.previous_prompt is not None:
        prev_path = args.previous_prompt if args.previous_prompt.is_absolute() else ROOT / args.previous_prompt
        previous = prev_path.read_text(encoding="utf-8")

    prompt_id = out.stem
    user = build_user_message(
        round_n=args.round,
        current_prompt=current,
        previous_prompt=previous,
        misses=misses,
        prompt_id=prompt_id,
        purpose=args.purpose,
        metrics_text=metrics_text,
        base_metrics_text=base_metrics,
    )
    log_dir = ROOT / "output" / "label_runs" / args.opt_run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    request_path = log_dir / "optimizer_request.jsonl"
    response_path = log_dir / "optimizer_response.jsonl"
    if response_path.exists():
        raise SystemExit(f"refusing to overwrite {response_path}")
    request_path.write_text(
        json.dumps(
            {
                "model": OPTIMIZER_MODEL,
                "round": args.round,
                "prompt_id": prompt_id,
                "n_miss": int(len(misses)),
                "user": user,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    client = ChatClient(PROVIDER_CONFIGS["openrouter"], timeout=300)
    resp = client.chat(
        OPTIMIZER_MODEL,
        [{"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=12000,
        reasoning_mode="on",
        reasoning_effort="medium",
    )
    content, reasoning = ChatClient.extract_message(resp)
    (log_dir / "optimizer_response.jsonl").write_text(
        json.dumps(
            {"content": content, "reasoning": reasoning},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    written = normalize_prompt(content, prompt_id=prompt_id, purpose=args.purpose)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(written, encoding="utf-8")
    print(f"wrote {out}  misses={len(misses)}")


if __name__ == "__main__":
    main()
