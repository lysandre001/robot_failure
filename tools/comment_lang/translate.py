"""SiliconFlow batch translation to English."""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

from tools.comment_lang.checkpoint import append_checkpoint, load_ok_checkpoint, purge_failed_checkpoint
from tools.comment_lang.detect import load_config, needs_translation

API_URL = "https://api.siliconflow.cn/v1/chat/completions"

SYS_PROMPT = """You translate social-media comments to English for academic analysis.
Rules:
- Output ONLY valid JSON: {"items": [{"id": "<comment_id>", "en": "<translation>"}, ...]}
- Use the exact id strings from the input; do not change id format.
- Preserve @mentions, numbers, emojis, and URLs unchanged.
- Escape backslashes and quotes inside en strings as valid JSON.
- Do not explain, summarize, or add content.
- One English translation per input id."""

SINGLE_SYS_PROMPT = """Translate the social-media comment to English for academic analysis.
Output ONLY the English translation text. No JSON, no quotes, no explanation."""


def _extract_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


def _items_from_data(data: Any) -> list[dict[str, str]]:
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("expected items list")
    out: list[dict[str, str]] = []
    for it in items:
        if isinstance(it, dict) and "id" in it and "en" in it:
            out.append({"id": str(it["id"]).strip(), "en": str(it["en"]).strip()})
    if not out:
        raise ValueError("no items parsed")
    return out


def _parse_json_items(raw: str) -> list[dict[str, str]]:
    block = _extract_json_block(raw)
    for payload in (block, raw):
        try:
            return _items_from_data(json.loads(payload))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    out: list[dict[str, str]] = []
    for m in re.finditer(
        r'"id"\s*:\s*"([^"]+)"\s*,\s*"en"\s*:\s*"((?:\\.|[^"\\])*)"',
        raw,
        flags=re.DOTALL,
    ):
        en = m.group(2).encode("utf-8").decode("unicode_escape", errors="replace")
        out.append({"id": m.group(1), "en": en.strip()})
    if out:
        return out
    raise ValueError(f"could not parse translation JSON: {raw[:200]}")


def system_prompt(cfg: dict[str, Any] | None = None) -> str:
    if cfg:
        custom = (cfg.get("translation") or {}).get("system_prompt")
        if custom and str(custom).strip():
            return str(custom).strip()
    return SYS_PROMPT


def _retryable_error(err: str) -> bool:
    e = err.lower()
    return any(k in e for k in ("rate_limit", "429", "timeout", "timed out", "connection"))


def _chat(
    api_key: str,
    model: str,
    user: str,
    *,
    sys_prompt: str = SYS_PROMPT,
    max_tokens: int = 4096,
    json_mode: bool = True,
    timeout_s: float = 180,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=(30, timeout_s),
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limit")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def translate_batch(
    batch: list[dict[str, str]],
    *,
    api_key: str,
    model: str,
    max_chars: int = 1500,
    sys_prompt: str = SYS_PROMPT,
    timeout_s: float = 180,
) -> dict[str, str]:
    if not batch:
        return {}
    payload_items = [{"id": str(it["id"]), "text": (it["text"] or "")[:max_chars]} for it in batch]
    user = json.dumps({"items": payload_items}, ensure_ascii=False)
    raw = _chat(api_key, model, user, sys_prompt=sys_prompt, json_mode=True, timeout_s=timeout_s)
    parsed = _parse_json_items(raw)
    out = {p["id"]: p["en"] for p in parsed}
    missing = [it["id"] for it in batch if it["id"] not in out]
    if missing:
        raise ValueError(f"missing ids in batch response: {missing[:5]}")
    return out


def translate_one_plain(
    api_key: str,
    model: str,
    text: str,
    max_chars: int,
    timeout_s: float = 180,
) -> str:
    user = (text or "")[:max_chars]
    raw = _chat(
        api_key,
        model,
        user,
        sys_prompt=SINGLE_SYS_PROMPT,
        max_tokens=512,
        json_mode=False,
        timeout_s=timeout_s,
    )
    return raw.strip()


def _translate_chunk(
    chunk: list[dict[str, Any]],
    *,
    api_key: str,
    model: str,
    max_chars: int,
    max_retries: int,
    sleep_s: float,
    prompt: str,
    timeout_s: float,
    rate_limit_lock: threading.Lock,
) -> list[dict[str, Any]]:
    """Translate one batch; fall back to single-item calls. Returns rows to checkpoint."""
    batch_in = [{"id": r["comment_id"], "text": r["content"]} for r in chunk]
    for attempt in range(1, max_retries + 1):
        try:
            translations = translate_batch(
                batch_in,
                api_key=api_key,
                model=model,
                max_chars=max_chars,
                sys_prompt=prompt,
                timeout_s=timeout_s,
            )
            return [{
                "comment_id": r["comment_id"],
                "language": r["language"],
                "is_mixed": r["is_mixed"],
                "content_en": translations[r["comment_id"]],
                "status": "ok",
                "translated": 1,
            } for r in chunk]
        except Exception as e:
            err = str(e)
            if _retryable_error(err):
                with rate_limit_lock:
                    time.sleep(sleep_s * (2 ** attempt) + random.uniform(0, 1))
            else:
                time.sleep(sleep_s)

    out: list[dict[str, Any]] = []
    for r in chunk:
        cid = r["comment_id"]
        ok = False
        last_err = ""
        for attempt in range(1, max_retries + 1):
            try:
                en = translate_one_plain(
                    api_key, model, r["content"], max_chars, timeout_s=timeout_s,
                )
                out.append({
                    "comment_id": cid,
                    "language": r["language"],
                    "is_mixed": r["is_mixed"],
                    "content_en": en,
                    "status": "ok",
                    "translated": 1,
                })
                ok = True
                break
            except Exception as e:
                last_err = str(e)[:200]
                if _retryable_error(last_err) and attempt < max_retries:
                    time.sleep(sleep_s * (2 ** attempt) + random.uniform(0, 0.5))
        if not ok:
            print(f"  [translate-fail] {cid}: {last_err}")
            out.append({
                "comment_id": cid,
                "language": r["language"],
                "is_mixed": r["is_mixed"],
                "content_en": "",
                "status": "fail",
                "error": last_err,
            })
    return out


def translate_records(
    records: list[dict[str, Any]],
    *,
    cfg: dict[str, Any] | None = None,
    checkpoint_path: Path | None = None,
    workers: int | None = None,
    limit: int | None = None,
) -> dict[str, dict[str, Any]]:
    cfg = cfg or load_config()
    tcfg = cfg.get("translation") or {}
    prompt = system_prompt(cfg)
    model = str(tcfg.get("model", "Qwen/Qwen2.5-7B-Instruct"))
    batch_size = int(tcfg.get("batch_size", 10))
    max_workers = int(workers if workers is not None else tcfg.get("max_workers", 4))
    max_workers = max(1, max_workers)
    max_chars = int(tcfg.get("max_text_chars", 1500))
    max_retries = int(tcfg.get("max_retries", 4))
    sleep_s = float(tcfg.get("sleep_seconds", 0.5))
    timeout_s = float(tcfg.get("request_timeout_seconds", 180))

    api_key = (os.environ.get("SILICONFLOW_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("SILICONFLOW_API_KEY 未设置")

    if checkpoint_path:
        n_ok, n_removed = purge_failed_checkpoint(checkpoint_path)
        if n_removed:
            print(f"  checkpoint: kept ok={n_ok}, removed fail/other={n_removed}")

    done = load_ok_checkpoint(checkpoint_path)
    state_lock = threading.Lock()
    rate_limit_lock = threading.Lock()

    pending: list[dict[str, Any]] = []
    for rec in records:
        cid = str(rec["comment_id"])
        if cid in done:
            continue
        lang = str(rec.get("language", "und"))
        mixed = int(rec.get("is_mixed", 0))
        content = str(rec.get("content", "") or "")
        if not content.strip():
            row = {
                "comment_id": cid,
                "language": lang,
                "is_mixed": mixed,
                "content_en": "",
                "status": "empty",
            }
            done[cid] = row
            if checkpoint_path:
                append_checkpoint(checkpoint_path, row)
            continue
        if not needs_translation(lang, mixed):
            row = {
                "comment_id": cid,
                "language": lang,
                "is_mixed": mixed,
                "content_en": content,
                "status": "ok",
                "translated": 0,
            }
            done[cid] = row
            if checkpoint_path:
                append_checkpoint(checkpoint_path, row)
            continue
        pending.append({**rec, "comment_id": cid})

    if limit is not None:
        pending = pending[:limit]

    llm_pending = len(pending)
    if llm_pending:
        n_chunks = (llm_pending + batch_size - 1) // batch_size
        print(f"  translate: {llm_pending} items, batch_size={batch_size}, workers={max_workers}, chunks={n_chunks}")

    def _persist(rows: list[dict[str, Any]]) -> None:
        with state_lock:
            for row in rows:
                done[row["comment_id"]] = row
                if checkpoint_path:
                    append_checkpoint(checkpoint_path, row)

    chunks = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    completed_chunks = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _translate_chunk,
                chunk,
                api_key=api_key,
                model=model,
                max_chars=max_chars,
                max_retries=max_retries,
                sleep_s=sleep_s,
                prompt=prompt,
                timeout_s=timeout_s,
                rate_limit_lock=rate_limit_lock,
            ): len(chunk)
            for chunk in chunks
        }
        for fut in as_completed(futures):
            n_items = futures[fut]
            rows = fut.result()
            _persist(rows)
            completed_chunks += 1
            if completed_chunks % max(1, max_workers) == 0 or completed_chunks == len(chunks):
                ok_n = sum(1 for r in rows if r.get("status") == "ok")
                print(f"  translate progress: chunks {completed_chunks}/{len(chunks)}, last_batch ok={ok_n}/{n_items}")

    return done
