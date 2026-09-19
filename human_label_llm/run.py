#!/usr/bin/env python3
"""Human vs LLM label comparison: dryrun | infer | compare."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, classification_report, cohen_kappa_score
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
LABEL_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    """Parse KEY=VALUE .env (no python-dotenv required)."""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key and not (os.environ.get(key) or "").strip():
            os.environ[key] = val


def _load_project_env() -> None:
    for path in (LABEL_DIR / ".env", ROOT / ".env", ROOT / "phase1" / "llm_stance" / ".env"):
        _load_env_file(path)
    try:
        from dotenv import load_dotenv

        for path in (LABEL_DIR / ".env", ROOT / ".env", ROOT / "phase1" / "llm_stance" / ".env"):
            load_dotenv(path, override=False)
    except ImportError:
        pass


_load_project_env()

from human_label_llm.llm_client import ChatClient, ProviderChain, resolve_models
from human_label_llm.prompts import (
    build_messages,
    dryrun_slot_report,
    load_spec,
    parse_response,
    resolve_scope_slots,
    resolve_scopes,
)

DEFAULT_INPUT = (
    LABEL_DIR
    / "label_data"
    / "clean_comments_robot_human_filtered_sample10_per_post(labelled) - "
    "clean_comments_robot_human_filtered_sample10_per_post(labelled).csv"
)

DEFAULT_COLUMNS: dict[str, str] = {
    "comment_id": "comment_id",
    "comment": "content",
    "title": "帖子标题",
    "caption": "post_caption",
    "gold": "评估对象",
}

DEFAULT_POSTS_JOIN: dict[str, str] = {
    "post_id": "帖子id",
    "caption_from": "帖子正文",
}


def resolve_columns(cfg: dict[str, Any]) -> dict[str, str]:
    from human_label_llm.labeling_paths import apply_labeling_columns

    cols = dict(DEFAULT_COLUMNS)
    user = cfg.get("columns")
    if isinstance(user, dict):
        cols.update({k: str(v) for k, v in user.items() if v is not None and str(v).strip()})
    return apply_labeling_columns(cols, cfg)


def resolve_gold_column(cfg: dict[str, Any], override: str | None = None) -> str:
    if override:
        return override
    if cfg.get("gold_column"):
        return str(cfg["gold_column"])
    return resolve_columns(cfg)["gold"]


def _data_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    data = cfg.get("data")
    return data if isinstance(data, dict) else {}


def resolve_input_csv(cfg: dict[str, Any]) -> Path:
    data = _data_cfg(cfg)
    raw = data.get("input_csv") or cfg.get("input_csv") or DEFAULT_INPUT
    return _resolve_path(raw)


def resolve_posts_csv(cfg: dict[str, Any]) -> Path | None:
    data = _data_cfg(cfg)
    raw = data.get("posts_csv") or cfg.get("posts_csv")
    return _resolve_path(raw) if raw else None


def resolve_posts_join(cfg: dict[str, Any]) -> dict[str, str] | None:
    if cfg.get("posts_join") is False:
        return None
    if resolve_posts_csv(cfg) is None:
        return None
    pj = dict(DEFAULT_POSTS_JOIN)
    user = cfg.get("posts_join")
    if isinstance(user, dict):
        pj.update({k: str(v) for k, v in user.items() if v is not None and str(v).strip()})
    return pj


def _resolve_path(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, val in override.items():
        if key == "extends":
            continue
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def _finalize_models(cfg: dict[str, Any]) -> dict[str, Any]:
    """model_catalog + model_keys → models（供 resolve_models 使用）。"""
    if cfg.get("models"):
        return cfg
    catalog = cfg.get("model_catalog")
    if not isinstance(catalog, dict) or not catalog:
        return cfg
    keys = cfg.get("model_keys")
    if keys is None:
        keys = list(catalog.keys())
    if not isinstance(keys, list) or not keys:
        raise ValueError("model_keys must be a non-empty list when model_catalog is set")
    missing = [k for k in keys if k not in catalog]
    if missing:
        raise ValueError(f"model_keys not in model_catalog: {missing}")
    out = dict(cfg)
    out["models"] = {k: catalog[k] for k in keys}
    return out


def resolve_config_path(
    name_or_path: str | Path,
    *,
    experiment_dir: Path | None = None,
    aliases: dict[str, str] | None = None,
) -> Path:
    """别名 / 文件名 / 相对路径 → 绝对 experiment yaml 路径。"""
    raw = str(name_or_path).strip()
    if not raw:
        raise ValueError("Empty experiment config path")

    path = Path(raw)
    if path.is_file():
        return path.resolve()

    exp_dir = experiment_dir or (LABEL_DIR / "experiment")
    alias_map = aliases or {}
    if raw in alias_map:
        candidate = exp_dir / alias_map[raw]
        if candidate.is_file():
            return candidate.resolve()
        raise FileNotFoundError(f"Aliased experiment config not found: {candidate}")

    for name in (raw, f"{raw}.yaml"):
        candidate = exp_dir / name
        if candidate.is_file():
            return candidate.resolve()

    resolved = _resolve_path(raw)
    if resolved.is_file():
        return resolved
    raise FileNotFoundError(f"Experiment config not found: {raw}")


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")

    extends = cfg.get("extends")
    if extends:
        base_path = path.parent / str(extends)
        if not base_path.is_file():
            raise FileNotFoundError(f"extends base not found: {base_path} (from {path})")
        base = load_config(base_path.resolve())
        cfg = _deep_merge(base, cfg)

    cfg = _finalize_models(cfg)
    for drop_key in ("extends", "model_catalog", "model_keys"):
        cfg.pop(drop_key, None)
    return cfg


def run_dir(cfg: dict[str, Any]) -> Path:
    from human_label_llm.labeling_paths import resolve_output_root

    run_id = cfg.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return resolve_output_root(cfg) / str(run_id)


def resolve_prompt_id(cfg: dict[str, Any]) -> str:
    from human_label_llm.labeling_paths import resolve_default_prompt_id

    return resolve_default_prompt_id(cfg)


def _merge_video_captions(cfg: dict[str, Any], df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
    """按帖子 id 合并 dense video caption（如 config_captions.jsonl 的 overview）。"""
    data = _data_cfg(cfg)
    raw = data.get("captions_jsonl")
    if not raw:
        return df
    path = _resolve_path(raw)
    if not path.is_file():
        raise FileNotFoundError(f"captions_jsonl not found: {path}")

    join = data.get("caption_join")
    if not isinstance(join, dict):
        join = {"post_id": "帖子id", "caption_id": "id"}
    post_col = str(join["post_id"])
    cap_id_col = str(join["caption_id"])
    caption_field = str(data.get("caption_field", "overview"))
    cap_slot_col = cols.get("caption", "post_caption")

    cap_rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get(caption_field) or rec.get("overview") or ""
            if not str(text).strip() and rec.get("raw"):
                text = str(rec["raw"])[:2000]
            cap_rows.append({post_col: str(rec.get(cap_id_col, "")), cap_slot_col: str(text).strip()})

    if not cap_rows:
        raise ValueError(f"No records in captions_jsonl: {path}")

    caps = pd.DataFrame(cap_rows).drop_duplicates(subset=[post_col], keep="first")
    out = df.merge(caps, on=post_col, how="left")
    out[cap_slot_col] = out[cap_slot_col].fillna("").astype(str).str.strip()
    return out


def load_dataframe(cfg: dict[str, Any], *, apply_limit: bool = True) -> pd.DataFrame:
    """直接读 experiment yaml 里的 data.input_csv（可选 merge posts / video captions）。"""
    input_csv = resolve_input_csv(cfg)
    cols = resolve_columns(cfg)
    df = pd.read_csv(input_csv)
    pj = resolve_posts_join(cfg)
    if pj:
        posts_csv = resolve_posts_csv(cfg)
        assert posts_csv is not None
        cap_col = cols["caption"]
        posts = pd.read_csv(posts_csv)[[pj["post_id"], pj["caption_from"]]].rename(
            columns={pj["caption_from"]: cap_col}
        )
        df = df.merge(posts, on=pj["post_id"], how="left")
        df[cap_col] = df[cap_col].fillna("").astype(str).str.strip()
    df = _merge_video_captions(cfg, df, cols)
    if apply_limit and cfg.get("limit") is not None:
        df = df.head(int(cfg["limit"]))
    return df


def cmd_dryrun(cfg: dict[str, Any], *, n: int = 2) -> None:
    """不调 API：打印填槽绑定 + 渲染后的 prompt，检查 scope/columns 是否生效。"""
    df = load_dataframe(cfg, apply_limit=False)
    cols = resolve_columns(cfg)
    spec = load_spec(resolve_prompt_id(cfg))
    scope_slots = resolve_scope_slots(cfg)
    scopes = resolve_scopes(cfg)
    prompt_id = resolve_prompt_id(cfg)

    print(f"[dryrun] prompt={prompt_id!r}  file={spec.prompt_file.name}  version={spec.version!r}")
    if spec.description:
        print(f"[dryrun] description (not sent to model):\n{spec.description}\n")
    print(f"[dryrun] input_csv={resolve_input_csv(cfg)}")
    print(f"[dryrun] columns (slot → csv): {cols}")
    print(f"[dryrun] scopes={scopes}\n")

    ok = True
    for idx, row in df.head(n).iterrows():
        for sid in scopes:
            rep = dryrun_slot_report(row, sid, cols, spec, scope_slots)
            print("=" * 60)
            print(f"row={idx}  scope={sid}")
            print("-" * 60)
            print("active_slots:", rep["active_slots"])
            for slot in rep["active_slots"]:
                csv_col = rep["columns_map"].get(slot, "?")
                val = rep["slot_values"].get(slot, "")
                preview = val[:80] + ("…" if len(val) > 80 else "")
                flag = "OK" if val else "EMPTY"
                print(f"  {{{slot}}} ← column[{csv_col!r}]  [{flag}]  {preview!r}")
            if rep["empty_slots"]:
                print(f"  WARN empty active slots: {rep['empty_slots']}")
                ok = False
            if rep["missing_column_keys"]:
                print(f"  ERROR missing columns keys: {rep['missing_column_keys']}")
                ok = False
            user = rep["messages"][-1]["content"]
            if "{comment}" in user or "{title}" in user:
                print("  ERROR unreplaced placeholders in prompt")
                ok = False
            if spec.description and spec.description.splitlines()[0] in user:
                print("  ERROR frontmatter description leaked into model prompt")
                ok = False
            print("-" * 60)
            print(user[:2500])
            if len(user) > 2500:
                print(f"... ({len(user)} chars total)")
            print()

    if ok:
        print("[dryrun] OK — active slots filled, placeholders replaced.")
    else:
        print("[dryrun] FAILED — fix columns / scope_slots / prompt template.", file=sys.stderr)
        sys.exit(1)


class JsonlStore:
    """Append-only JSONL; duplicate key = comment_id|model_key|scope_id."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[str] = set()
        self._lock = threading.Lock()
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        k = _record_key(rec)
                        if k:
                            self._done.add(k)
                    except json.JSONDecodeError:
                        continue

    def has(self, key: str) -> bool:
        return key in self._done

    def append(self, rec: dict) -> None:
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            k = _record_key(rec)
            if k:
                self._done.add(k)


def _record_key(rec: dict) -> str:
    cid = rec.get("comment_id")
    mk = rec.get("model_key")
    sid = rec.get("scope_id")
    if cid and mk and sid:
        return f"{cid}|{mk}|{sid}"
    return ""


def _safe_col(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name).strip("_")


def annotate_one(
    chain: ProviderChain,
    model_key: str,
    scope_id: str,
    row: pd.Series,
    cols: dict[str, str],
    spec,
    scope_slots: dict[str, list[str]],
    prompt_id: str,
    *,
    temperature: float,
    max_tokens: int,
) -> dict:
    msgs = build_messages(row, scope_id, cols, spec, scope_slots)
    cid = str(row[cols["comment_id"]])
    t0 = time.time()
    try:
        resp, provider_used, model_used = chain.chat(
            msgs,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text, reasoning_raw = ChatClient.extract_message(resp)
        label_en, label_cn, reason, status = parse_response(text, spec)
        if status == "parse_error":
            msgs2 = msgs + [
                ChatClient.assistant_message_from_response(resp),
                {"role": "user", "content": spec.output.retry_hint},
            ]
            resp, provider_used, model_used = chain.chat(
                msgs2,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text, reasoning_raw = ChatClient.extract_message(resp)
            label_en, label_cn, reason, status = parse_response(text, spec)
        return {
            "comment_id": cid,
            "prompt_id": prompt_id,
            "prompt_version": spec.version,
            "model_key": model_key,
            "scope_id": scope_id,
            "provider": provider_used,
            "model": model_used,
            "reasoning_mode": chain.reasoning_mode,
            "label_en": label_en,
            "label_cn": label_cn,
            "reason": reason,
            "reasoning_raw": reasoning_raw[:2000] if reasoning_raw else "",
            "raw": text,
            "status": status if status == "ok" else "parse_error",
            "elapsed_s": round(time.time() - t0, 3),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": None,
        }
    except Exception as e:
        return {
            "comment_id": cid,
            "prompt_id": prompt_id,
            "prompt_version": spec.version,
            "model_key": model_key,
            "scope_id": scope_id,
            "provider": "",
            "model": "",
            "label_en": "",
            "label_cn": "",
            "reason": "",
            "raw": "",
            "status": "api_error",
            "elapsed_s": round(time.time() - t0, 3),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": f"{type(e).__name__}: {e}",
        }


def cmd_infer(cfg: dict[str, Any], config_path: Path) -> Path:
    out = run_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    cols = resolve_columns(cfg)
    prompt_id = resolve_prompt_id(cfg)
    spec = load_spec(prompt_id)
    scope_slots = resolve_scope_slots(cfg)
    df = load_dataframe(cfg)
    print(f"[infer] input={resolve_input_csv(cfg)}  rows={len(df)}")

    model_specs = resolve_models(cfg)
    if not model_specs:
        raise ValueError("config.models must list at least one model")

    scopes = resolve_scopes(cfg)
    temperature = float(cfg.get("temperature", 0.0))
    max_tokens = int(cfg.get("max_tokens", 512))
    concurrency = int(cfg.get("concurrency", 4))
    timeout = int(cfg.get("timeout", 120))

    shutil.copy2(config_path, out / "run.yaml")

    log_path = out / "log.jsonl"
    store = JsonlStore(log_path)
    chains = {
        mk: ProviderChain(spec, timeout=timeout)
        for mk, spec in model_specs.items()
    }

    id_col = cols["comment_id"]
    jobs: list[tuple[str, str, pd.Series]] = []
    for model_key in model_specs:
        for scope_id in scopes:
            for _, row in df.iterrows():
                key = f"{row[id_col]}|{model_key}|{scope_id}"
                if not store.has(key):
                    jobs.append((model_key, scope_id, row))

    print(f"[infer] pending={len(jobs)}  log={log_path}")
    if not jobs:
        return log_path

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {
            ex.submit(
                annotate_one,
                chains[model_key],
                model_key,
                scope_id,
                row,
                cols,
                spec,
                scope_slots,
                prompt_id,
                temperature=temperature,
                max_tokens=max_tokens,
            ): (model_key, scope_id, row[id_col])
            for model_key, scope_id, row in jobs
        }
        for fut in tqdm(as_completed(futs), total=len(futs), desc="infer"):
            rec = fut.result()
            if rec.get("status") == "ok":
                store.append(rec)
            else:
                store.append(rec)

    return log_path


def per_category_metrics(y_true: pd.Series, y_pred: pd.Series) -> pd.DataFrame:
    """Per gold category: recall (=类内准确率), precision, f1, one-vs-rest Cohen's kappa."""
    yt = y_true.astype(str).str.strip()
    yp = y_pred.astype(str).str.strip()
    report = classification_report(yt, yp, output_dict=True, zero_division=0)
    categories = sorted(set(yt) | set(yp))
    rows: list[dict] = []
    for cat in categories:
        m = yt == cat
        n_gold = int(m.sum())
        n_correct = int((yt[m] == yp[m]).sum()) if n_gold else 0
        recall = n_correct / n_gold if n_gold else float("nan")
        r = report.get(cat, {}) if isinstance(report.get(cat), dict) else {}
        yt_bin = (yt == cat).astype(int)
        yp_bin = (yp == cat).astype(int)
        if n_gold >= 2 and len(set(yt_bin) | set(yp_bin)) > 1:
            kappa_ovr = float(cohen_kappa_score(yt_bin, yp_bin))
        else:
            kappa_ovr = float("nan")
        rows.append({
            "category": cat,
            "n_gold": n_gold,
            "n_correct": n_correct,
            "recall": round(recall, 4) if n_gold else None,
            "precision": round(float(r.get("precision", 0)), 4) if cat in report else None,
            "f1": round(float(r.get("f1-score", 0)), 4) if cat in report else None,
            "kappa_ovr": round(kappa_ovr, 4) if kappa_ovr == kappa_ovr else None,
        })
    return pd.DataFrame(rows)


def gap_misclassification_pairs(y_true: pd.Series, y_pred: pd.Series) -> pd.DataFrame:
    """Off-diagonal (human, llm) counts; pct_of_human = n / 该类人工总数."""
    yt = y_true.astype(str).str.strip()
    yp = y_pred.astype(str).str.strip()
    mask = yt.ne("") & yp.ne("") & (yt != yp)
    if not mask.any():
        return pd.DataFrame(columns=["human", "llm", "n", "pct_of_human"])
    sub = pd.DataFrame({"human": yt[mask], "llm": yp[mask]})
    pairs = sub.groupby(["human", "llm"], as_index=False).size().rename(columns={"size": "n"})
    human_totals = yt.groupby(yt).size()
    pairs["pct_of_human"] = pairs.apply(
        lambda r: round(100 * r["n"] / human_totals[r["human"]], 1),
        axis=1,
    )
    return pairs.sort_values("n", ascending=False).reset_index(drop=True)


def gap_summary_metrics(y_true: pd.Series, y_pred: pd.Series, by_cat: pd.DataFrame) -> dict[str, Any]:
    """Macro/micro style gaps vs human-as-gold."""
    yt = y_true.astype(str).str.strip()
    yp = y_pred.astype(str).str.strip()
    n = len(yt)
    n_agree = int((yt == yp).sum())
    bc = by_cat[by_cat["category"].astype(str) != "All"] if "category" in by_cat.columns else by_cat
    macro_recall = float(bc["recall"].mean()) if len(bc) else float("nan")
    macro_precision = float(bc["precision"].mean()) if len(bc) and bc["precision"].notna().any() else float("nan")
    macro_f1 = float(bc["f1"].mean()) if len(bc) and bc["f1"].notna().any() else float("nan")
    return {
        "n": n,
        "n_agree": n_agree,
        "n_disagree": n - n_agree,
        "agreement_rate": round(n_agree / n, 4) if n else None,
        "disagreement_rate": round((n - n_agree) / n, 4) if n else None,
        "macro_recall": round(macro_recall, 4) if macro_recall == macro_recall else None,
        "macro_precision": round(macro_precision, 4) if macro_precision == macro_precision else None,
        "macro_f1": round(macro_f1, 4) if macro_f1 == macro_f1 else None,
    }


def per_class_gap_table(by_cat: pd.DataFrame) -> pd.DataFrame:
    """Per human category: recall, miss rate, main wrong LLM label."""
    rows = []
    for _, r in by_cat.iterrows():
        cat = str(r["category"])
        n_gold = int(r["n_gold"])
        n_correct = int(r["n_correct"])
        n_miss = n_gold - n_correct
        rows.append({
            "category": cat,
            "n_human": n_gold,
            "n_correct": n_correct,
            "n_miss": n_miss,
            "recall": r["recall"],
            "miss_rate": round(n_miss / n_gold, 4) if n_gold else None,
            "gap_recall": round(1 - float(r["recall"]), 4) if n_gold and r["recall"] == r["recall"] else None,
        })
    return pd.DataFrame(rows).sort_values("gap_recall", ascending=False, na_position="last")


def _load_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def cmd_compare(cfg: dict[str, Any], *, gold_override: str | None = None) -> tuple[Path, Path]:
    out = run_dir(cfg)
    log_path = out / "log.jsonl"
    if not log_path.is_file():
        raise FileNotFoundError(f"Missing {log_path}; run infer first.")

    gold_col = resolve_gold_column(cfg, gold_override)
    gold = load_dataframe(cfg)
    input_csv = resolve_input_csv(cfg)
    if gold_col not in gold.columns:
        raise ValueError(
            f"gold column {gold_col!r} not in {input_csv} (see columns.gold / gold_column)"
        )
    print(f"[compare] input={input_csv}  rows={len(gold)}")

    logs = _load_jsonl(log_path)
    wide = gold.copy()
    cols = resolve_columns(cfg)
    id_col = cols["comment_id"]

    summary_rows: list[dict] = []
    by_cat_frames: list[pd.DataFrame] = []
    gap_pair_frames: list[pd.DataFrame] = []
    gap_class_frames: list[pd.DataFrame] = []

    for (model_key, scope_id), grp in logs.groupby(["model_key", "scope_id"]):
        col = f"llm_{_safe_col(model_key)}_{scope_id}"
        reason_col = f"{col}_reason"
        status_col = f"{col}_status"
        cat_map = grp.set_index("comment_id")["label_cn"].astype(str).to_dict()
        reason_map = grp.set_index("comment_id")["reason"].astype(str).to_dict()
        status_map = grp.set_index("comment_id")["status"].astype(str).to_dict()
        cids = wide[id_col].astype(str)
        wide[col] = cids.map(lambda c: cat_map.get(c, ""))
        wide[reason_col] = cids.map(lambda c: reason_map.get(c, ""))
        wide[status_col] = cids.map(lambda c: status_map.get(c, ""))

        ev = wide[wide[status_col] == "ok"].copy()
        n_parse_error = int((wide[status_col] == "parse_error").sum())
        n_api_error = int((wide[status_col] == "api_error").sum())
        y_true = ev[gold_col].astype(str)
        y_pred = ev[col].astype(str)
        mask = (y_true.str.len() > 0) & (y_pred.str.len() > 0)
        y_true = y_true[mask]
        y_pred = y_pred[mask]
        n = len(y_true)
        if n == 0:
            acc, kappa = float("nan"), float("nan")
        else:
            acc = float(accuracy_score(y_true, y_pred))
            labels = sorted(set(y_true) | set(y_pred))
            kappa = float(cohen_kappa_score(y_true, y_pred, labels=labels)) if len(labels) > 1 else float("nan")

        summary_rows.append({
            "model_key": model_key,
            "scope_id": scope_id,
            "gold_column": gold_col,
            "pred_column": col,
            "n": n,
            "accuracy": round(acc, 4) if n else None,
            "kappa": round(kappa, 4) if n and kappa == kappa else None,
            "n_parse_error": n_parse_error,
            "n_api_error": n_api_error,
        })

        cat_df = per_category_metrics(y_true, y_pred)
        cat_df.insert(0, "scope_id", scope_id)
        cat_df.insert(0, "model_key", model_key)
        by_cat_frames.append(cat_df)

        gap_m = gap_summary_metrics(y_true, y_pred, cat_df)
        gap_m.update({"model_key": model_key, "scope_id": scope_id})
        summary_rows[-1].update(gap_m)

        pairs_df = gap_misclassification_pairs(y_true, y_pred)
        pairs_df.insert(0, "scope_id", scope_id)
        pairs_df.insert(0, "model_key", model_key)
        gap_pair_frames.append(pairs_df)

        pg = per_class_gap_table(cat_df)
        pg.insert(0, "scope_id", scope_id)
        pg.insert(0, "model_key", model_key)
        gap_class_frames.append(pg)

    wide_path = out / "comparison_wide.csv"
    summary_path = out / "eval_summary.csv"
    by_cat_path = out / "eval_by_category.csv"
    gap_pairs_path = out / "eval_gap_pairs.csv"
    gap_class_path = out / "eval_gap_by_class.csv"
    wide.to_csv(wide_path, index=False, encoding="utf-8-sig")
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    by_cat = pd.concat(by_cat_frames, ignore_index=True) if by_cat_frames else pd.DataFrame()
    by_cat.to_csv(by_cat_path, index=False, encoding="utf-8-sig")
    gap_pairs = pd.concat(gap_pair_frames, ignore_index=True) if gap_pair_frames else pd.DataFrame()
    gap_pairs.to_csv(gap_pairs_path, index=False, encoding="utf-8-sig")
    gap_class = pd.concat(gap_class_frames, ignore_index=True) if gap_class_frames else pd.DataFrame()
    gap_class.to_csv(gap_class_path, index=False, encoding="utf-8-sig")
    print(f"[compare] wrote {wide_path}")
    print(f"[compare] wrote {summary_path}")
    print(f"[compare] wrote {by_cat_path}")
    print(f"[compare] wrote {gap_pairs_path}")
    print(f"[compare] wrote {gap_class_path}")
    print(summary_df.to_string(index=False))
    if not by_cat.empty:
        print("\n[compare] per-category (recall=该类人工标注下的准确率, kappa_ovr=one-vs-rest):")
        print(by_cat.to_string(index=False))
    if not gap_pairs.empty:
        print("\n[compare] top misclassification pairs (human → llm):")
        print(gap_pairs.head(12).to_string(index=False))
    return wide_path, summary_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=LABEL_DIR / "run.yaml",
        help="Path to run.yaml",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inf = sub.add_parser("infer", help="LLM inference → log.jsonl")
    p_inf.add_argument("-c", "--config", type=Path, default=None)

    p_cmp = sub.add_parser("compare", help="Wide table + accuracy/kappa")
    p_cmp.add_argument("-c", "--config", type=Path, default=None)
    p_cmp.add_argument(
        "--gold",
        default=None,
        help="Override gold column (default: run.yaml gold_column)",
    )

    p_dry = sub.add_parser("dryrun", help="Check slot fill + rendered prompt (no API)")
    p_dry.add_argument("-c", "--config", type=Path, default=None)
    p_dry.add_argument("-n", type=int, default=2, help="Sample rows per scope")

    args = parser.parse_args(argv)
    cfg_path = _resolve_path(args.config or LABEL_DIR / "run.yaml")
    if not cfg_path.is_file():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        print("Copy run.example.yaml → run.yaml and edit models.", file=sys.stderr)
        sys.exit(1)
    cfg = load_config(cfg_path)

    if args.command == "infer":
        cmd_infer(cfg, cfg_path)
    elif args.command == "compare":
        cmd_compare(cfg, gold_override=args.gold)
    elif args.command == "dryrun":
        cmd_dryrun(cfg, n=args.n)


if __name__ == "__main__":
    main()
