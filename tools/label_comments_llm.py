#!/usr/bin/env python3
"""[archived] Legacy LLM figure/stance/D 单文件 CLI。新跑请用 human_label_llm/run_experiment.py + config/codebook/。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import ROOT

DEFAULT_INPUT = ROOT / "data" / "clean" / "manual_label_l1_30perpost.csv"
DEFAULT_OUTPUT = ROOT / "data" / "clean" / "manual_label_l1_30perpost_llm.csv"
DEFAULT_CHECKPOINT = ROOT / "data" / "clean" / "label_checkpoint.jsonl"
DEFAULT_RELIC_ENV = Path("/Users/yilin/Desktop/project/relic3/relic_3.0_test")

FIGURE_CODES = frozenset(
    {
        "competitor",
        "threat",
        "pet_cute",
        "tool",
        "patient",
        "fraud_fake",
        "spectacle",
        "personified_peer",
        "other",
    }
)
STANCES = frozenset({"支持", "中立", "反对"})
VALENCES = frozenset({"positive", "negative", "mixed", "neutral"})
POLARITIES = frozenset({"Pos", "Neg", "N/A"})

LLM_COLS = [
    "llm_figure_code",
    "llm_figure_label",
    "llm_figure_reason",
    "llm_figure_display",
    "llm_stance",
    "llm_stance_reason",
    "llm_stance_display",
    "llm_emotion",
    "llm_emotion_valence",
    "llm_emotion_reason",
    "llm_emotion_display",
    "llm_d1",
    "llm_d1_reason",
    "llm_d2",
    "llm_d2_reason",
    "llm_d3",
    "llm_d3_reason",
    "llm_d4",
    "llm_d4_reason",
    "llm_dimensional_display",
    "llm_provider",
    "llm_model",
    "llm_labeled_at",
    "llm_parse_ok",
    "llm_error",
]

SYSTEM_PROMPT = """你是社交媒体评论编码员，研究「机器人马拉松/赛事」相关小红书一级评论。
根据评论正文与帖子语境，输出**仅一个 JSON 对象**（无 Markdown），字段如下：

{
  "figure_code": "<competitor|threat|pet_cute|tool|patient|fraud_fake|spectacle|personified_peer|other>",
  "figure_label": "<中文短标签，≤20字；other 时写你概括的关系想象>",
  "figure_reason": "<1-2句，引用评论线索>",
  "stance": "<支持|中立|反对>",
  "stance_reason": "<对机器人参赛/能力/主办方的态度原因>",
  "emotion": "<最贴切情感词/短语，可复合；基本情感与社会情感均可>",
  "emotion_valence": "<positive|negative|mixed|neutral>",
  "emotion_reason": "<情感判断原因>",
  "d1": "<Pos|Neg|N/A>",
  "d1_reason": "<D1 技术能力：速度、稳定性、工程；≤80字>",
  "d2": "<Pos|Neg|N/A>",
  "d2_reason": "<D2 情感卷入：可爱/好笑/可怜/喜爱/厌恶>",
  "d3": "<Pos|Neg|N/A>",
  "d3_reason": "<D3 社会价值：科技进步、意义、浪费、就业、伦理>",
  "d4": "<Pos|Neg|N/A>",
  "d4_reason": "<D4 人类影响：人类地位、替代、威胁、照护关系>"
}

figure_code 释义：
- competitor：竞争者/被超越对象（比速度、比人类）
- threat：威胁/不安（失业、取代人类、恐怖）
- pet_cute：可爱宠物/孩童式（萌、可怜、想养）
- tool：工具/道具/技术展品
- patient：照护/救助对象（摔倒、失败、加油）
- fraud_fake：造假/噱头/摆拍
- spectacle：奇观/节目/玩梗看热闹
- personified_peer：拟人同伴/当人对话
- other：以上都不贴切（figure_label 必填概括）

立场：支持=肯定能力/进步/可爱/辩护；反对=嘲讽/否定/质疑造假/排斥；中立=陈述提问调侃难判（reason 说明）。

每维 Pos=积极评价该维，Neg=消极，N/A=未涉及。各维独立，可同时 D2=Pos 且 D4=Neg。
禁止输出 schema 外的键。"""


@dataclass(frozen=True)
class ApiTarget:
    provider: str
    base_url: str
    api_key: str
    model: str


def _load_dotenv_file(path: Path) -> None:
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
        if key and key not in os.environ:
            os.environ[key] = val


def load_relic_env(relic_env_dir: Path) -> None:
    for path in (relic_env_dir / ".env", relic_env_dir / "scripts" / ".env"):
        _load_dotenv_file(path)


def _get_env(*keys: str) -> str | None:
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v.strip()
    return None


def resolve_api_target() -> ApiTarget:
    ds_key = _get_env("DEEPSEEK_API_KEY")
    if ds_key:
        return ApiTarget("deepseek", "https://api.deepseek.com", ds_key, "deepseek-v4-pro")
    or_key = _get_env("OPENROUTER_API_KEY")
    if or_key:
        return ApiTarget(
            "openrouter",
            "https://openrouter.ai/api/v1",
            or_key,
            "deepseek/deepseek-v4-pro",
        )
    sf_key = _get_env("SILICONFLOW_API_KEY", "SILICONFLOW_api_key")
    if sf_key:
        print(
            "警告: 未找到 DEEPSEEK/OPENROUTER 密钥，SiliconFlow 无 V4-Pro，降级为 deepseek-ai/DeepSeek-V3",
            file=sys.stderr,
        )
        return ApiTarget(
            "siliconflow",
            "https://api.siliconflow.cn/v1",
            sf_key,
            "deepseek-ai/DeepSeek-V3",
        )
    raise RuntimeError(
        "未找到 API 密钥。请在 relic3 .env 中配置 DEEPSEEK_API_KEY（首选）或 OPENROUTER_API_KEY。"
    )


def _truncate(s: str, n: int, suffix: str = "[truncated]") -> str:
    if not isinstance(s, str) or pd.isna(s):
        return ""
    s = str(s).strip()
    if len(s) <= n:
        return s
    return s[: n - len(suffix)] + suffix


def build_user_message(row: pd.Series) -> str:
    content = _truncate(row.get("content", ""), 1500)
    parts = [
        f"post_category: {row.get('post_category', '')}",
        f"帖子标题: {_truncate(row.get('帖子标题', ''), 200)}",
        f"帖子正文: {_truncate(row.get('帖子正文', ''), 300)}",
        f"comment_id: {row.get('comment_id', '')}",
        f"content: {content}",
    ]
    return "\n".join(parts)


def _norm_polarity(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    mapping = {
        "pos": "Pos",
        "positive": "Pos",
        "积极": "Pos",
        "neg": "Neg",
        "negative": "Neg",
        "消极": "Neg",
        "n/a": "N/A",
        "na": "N/A",
        "none": "N/A",
        "无关": "N/A",
    }
    low = s.lower()
    if low in mapping:
        return mapping[low]
    if s in POLARITIES:
        return s
    return None


def validate_labels(data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    required = [
        "figure_code",
        "figure_label",
        "figure_reason",
        "stance",
        "stance_reason",
        "emotion",
        "emotion_valence",
        "emotion_reason",
        "d1",
        "d1_reason",
        "d2",
        "d2_reason",
        "d3",
        "d3_reason",
        "d4",
        "d4_reason",
    ]
    for k in required:
        if k not in data or data[k] is None or str(data[k]).strip() == "":
            return None, f"missing:{k}"

    fc = str(data["figure_code"]).strip()
    if fc not in FIGURE_CODES:
        return None, f"invalid figure_code:{fc}"
    fl = str(data["figure_label"]).strip()
    if fc == "other" and not fl:
        return None, "other_requires_figure_label"

    stance = str(data["stance"]).strip()
    if stance not in STANCES:
        return None, f"invalid stance:{stance}"

    ev = str(data["emotion_valence"]).strip().lower()
    if ev not in VALENCES:
        return None, f"invalid emotion_valence:{ev}"

    out: dict[str, Any] = {
        "llm_figure_code": fc,
        "llm_figure_label": fl[:20],
        "llm_figure_reason": str(data["figure_reason"]).strip(),
        "llm_stance": stance,
        "llm_stance_reason": str(data["stance_reason"]).strip(),
        "llm_emotion": str(data["emotion"]).strip(),
        "llm_emotion_valence": ev,
        "llm_emotion_reason": str(data["emotion_reason"]).strip(),
    }
    for i in range(1, 5):
        pol = _norm_polarity(data[f"d{i}"])
        if pol not in POLARITIES:
            return None, f"invalid d{i}:{data[f'd{i}']}"
        out[f"llm_d{i}"] = pol
        out[f"llm_d{i}_reason"] = str(data[f"d{i}_reason"]).strip()[:80]

    return out, None


def _reason_snip(s: str, n: int = 40) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def build_displays(labels: dict[str, Any]) -> dict[str, str]:
    return {
        "llm_figure_display": f"【{labels['llm_figure_label']}】{labels['llm_figure_reason']}",
        "llm_stance_display": f"【{labels['llm_stance']}】{labels['llm_stance_reason']}",
        "llm_emotion_display": f"【{labels['llm_emotion']}】{labels['llm_emotion_reason']}",
        "llm_dimensional_display": (
            f"D1:{labels['llm_d1']}|{_reason_snip(labels['llm_d1_reason'])}；"
            f"D2:{labels['llm_d2']}|{_reason_snip(labels['llm_d2_reason'])}；"
            f"D3:{labels['llm_d3']}|{_reason_snip(labels['llm_d3_reason'])}；"
            f"D4:{labels['llm_d4']}|{_reason_snip(labels['llm_d4_reason'])}"
        ),
    }


def empty_llm_row() -> dict[str, Any]:
    return {c: "" for c in LLM_COLS}


def load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    """comment_id -> merged labels + meta from last successful line."""
    done: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return done
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = str(rec.get("comment_id", ""))
            if not cid:
                continue
            if rec.get("error"):
                continue
            labels = rec.get("labels")
            if labels and rec.get("parse_ok"):
                done[cid] = labels
    return done


def append_checkpoint(
    path: Path,
    comment_id: str,
    *,
    raw_json: str | None,
    provider: str,
    model: str,
    parse_ok: bool,
    labels: dict[str, Any] | None,
    error: str | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "comment_id": comment_id,
        "raw_json": raw_json,
        "provider": provider,
        "model": model,
        "ts": datetime.now(timezone.utc).isoformat(),
        "parse_ok": parse_ok,
        "labels": labels,
        "error": error,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


async def call_llm(
    client: Any,
    target: ApiTarget,
    user_msg: str,
    temperature: float,
    max_retries: int,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Returns (labels, raw_content, error)."""
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": target.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
            if target.provider == "deepseek":
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            if target.provider == "siliconflow":
                kwargs["extra_body"] = {"enable_thinking": False}
            resp = await client.chat.completions.create(**kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            labels, verr = validate_labels(data)
            if verr:
                last_err = verr
                continue
            assert labels is not None
            labels.update(build_displays(labels))
            return labels, raw, None
        except json.JSONDecodeError as e:
            last_err = f"json_decode:{e}"
        except Exception as e:
            last_err = f"api:{type(e).__name__}:{e}"
        if attempt < max_retries:
            await asyncio.sleep(1.5 * (attempt + 1))
    return None, None, last_err


async def label_batch(
    rows: list[tuple[str, pd.Series]],
    target: ApiTarget,
    checkpoint_path: Path,
    concurrency: int,
    temperature: float,
    done: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[float]]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=target.api_key, base_url=target.base_url)
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict[str, Any]] = dict(done)
    latencies: list[float] = []

    async def one(cid: str, row: pd.Series) -> None:
        if cid in results:
            return
        async with sem:
            t0 = time.perf_counter()
            user_msg = build_user_message(row)
            labels, raw, err = await call_llm(
                client, target, user_msg, temperature, max_retries=2
            )
            latencies.append(time.perf_counter() - t0)
            ts = datetime.now(timezone.utc).isoformat()
            if labels:
                full = {**labels}
                full.update(
                    {
                        "llm_provider": target.provider,
                        "llm_model": target.model,
                        "llm_labeled_at": ts,
                        "llm_parse_ok": "1",
                        "llm_error": "",
                    }
                )
                results[cid] = full
                append_checkpoint(
                    checkpoint_path,
                    cid,
                    raw_json=raw,
                    provider=target.provider,
                    model=target.model,
                    parse_ok=True,
                    labels=full,
                    error=None,
                )
            else:
                fail = empty_llm_row()
                fail.update(
                    {
                        "llm_provider": target.provider,
                        "llm_model": target.model,
                        "llm_labeled_at": ts,
                        "llm_parse_ok": "0",
                        "llm_error": err or "unknown",
                    }
                )
                results[cid] = fail
                append_checkpoint(
                    checkpoint_path,
                    cid,
                    raw_json=raw,
                    provider=target.provider,
                    model=target.model,
                    parse_ok=False,
                    labels=None,
                    error=err,
                )

    await asyncio.gather(*[one(cid, row) for cid, row in rows])
    return results, latencies


def print_qc(df: pd.DataFrame, seed: int = 42) -> None:
    labeled = df[df["llm_parse_ok"] == "1"]
    n_ok = len(labeled)
    n_all = len(df)
    print(f"\n=== QC 摘要 ===")
    print(f"总行数: {n_all}  成功打标: {n_ok}  成功率: {n_ok / max(n_all, 1):.1%}")

    for col in ["llm_stance", "llm_figure_code", "llm_d1", "llm_d2", "llm_d3", "llm_d4"]:
        if col in labeled.columns and n_ok:
            print(f"\n{col} 分布:")
            print(labeled[col].value_counts().to_string())

    if n_ok >= 5:
        sample = labeled.sample(n=min(5, n_ok), random_state=seed)
        print("\n--- 随机 5 条 spot-check ---")
        for _, r in sample.iterrows():
            print(f"\ncomment_id: {r.get('comment_id')}")
            c = str(r.get("content", ""))[:120]
            print(f"content: {c}{'…' if len(str(r.get('content',''))) > 120 else ''}")
            for dcol in [
                "llm_figure_display",
                "llm_stance_display",
                "llm_emotion_display",
                "llm_dimensional_display",
            ]:
                print(f"  {dcol}: {r.get(dcol, '')}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="LLM 四维评论打标")
    p.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--relic-env-dir", type=Path, default=DEFAULT_RELIC_ENV)
    p.add_argument("--limit", type=int, default=100, help="0=全量")
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    load_relic_env(args.relic_env_dir)
    target = resolve_api_target()
    print(f"API: provider={target.provider} model={target.model}")

    df = pd.read_csv(args.input_csv, encoding="utf-8-sig")
    if "comment_id" not in df.columns:
        raise ValueError("输入 CSV 缺少 comment_id 列")

    work = df.copy()
    if args.limit > 0:
        work = work.head(args.limit)

    done = load_checkpoint(args.checkpoint) if args.resume else {}
    if args.resume and done:
        print(f"resume: 已跳过 {len(done)} 条成功记录")

    pending: list[tuple[str, pd.Series]] = []
    for _, row in work.iterrows():
        cid = str(row["comment_id"])
        if cid not in done:
            pending.append((cid, row))

    print(f"待打标: {len(pending)} / {len(work)}")
    latencies: list[float] = []
    if pending:
        done, latencies = asyncio.run(
            label_batch(
                pending,
                target,
                args.checkpoint,
                args.concurrency,
                args.temperature,
                done,
            )
        )
        if latencies:
            print(f"平均延迟: {sum(latencies) / len(latencies):.2f}s (n={len(latencies)})")

    out_rows = []
    for _, row in work.iterrows():
        cid = str(row["comment_id"])
        base = row.to_dict()
        labels = done.get(cid, empty_llm_row())
        for c in LLM_COLS:
            base[c] = labels.get(c, "")
        out_rows.append(base)

    out_df = pd.DataFrame(out_rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
    print(f"已写入: {args.output_csv}")

    print_qc(out_df, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
