"""Checkpoint jsonl helpers for comment translation."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_append_lock = threading.Lock()


def load_ok_checkpoint(path: Path | None) -> dict[str, dict[str, Any]]:
    """Load only successful rows; ignore fail/empty checkpoint lines."""
    out: dict[str, dict[str, Any]] = {}
    if not path or not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") != "ok":
            continue
        cid = str(row.get("comment_id", "")).strip()
        if cid:
            out[cid] = row
    return out


def purge_failed_checkpoint(path: Path | None) -> tuple[int, int]:
    """Rewrite checkpoint keeping only status=ok rows. Returns (n_ok, n_removed)."""
    if not path or not path.is_file():
        return 0, 0
    ok_rows: list[dict[str, Any]] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            removed += 1
            continue
        if row.get("status") == "ok":
            ok_rows.append(row)
        else:
            removed += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    if ok_rows:
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in ok_rows) + "\n",
            encoding="utf-8",
        )
    else:
        path.unlink(missing_ok=True)
    return len(ok_rows), removed


def append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with _append_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
