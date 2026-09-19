"""评论打标：平台 → 文本列 / prompt 语言（与 config/codebook/label_map.yaml 一致）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from phase1.config import ROOT

_LABEL_MAP_PATH = ROOT / "config" / "codebook" / "label_map.yaml"


def _load_label_map() -> dict[str, Any]:
    if not _LABEL_MAP_PATH.is_file():
        return {}
    with _LABEL_MAP_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_platform(cfg: dict[str, Any]) -> str:
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    raw = cfg.get("platform") or data.get("platform") or ""
    return str(raw).strip().lower()


def resolve_text_column(cfg: dict[str, Any]) -> str:
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    if cfg.get("text_column"):
        return str(cfg["text_column"])
    if data.get("text_column"):
        return str(data["text_column"])
    plat = resolve_platform(cfg)
    lm = _load_label_map()
    for block in (lm.get("platform_text") or {}).values():
        if plat in {str(p).lower() for p in block.get("platforms", [])}:
            return str(block.get("text_column", "content"))
    if plat in {"tiktok", "youtube"}:
        return "content_en"
    return "content"


def resolve_prompt_lang(cfg: dict[str, Any]) -> str:
    if cfg.get("prompt_lang"):
        return str(cfg["prompt_lang"]).lower()
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    if data.get("prompt_lang"):
        return str(data["prompt_lang"]).lower()
    plat = resolve_platform(cfg)
    lm = _load_label_map()
    for block in (lm.get("platform_text") or {}).values():
        if plat in {str(p).lower() for p in block.get("platforms", [])}:
            return str(block.get("prompt_lang", "zh")).lower()
    if plat in {"tiktok", "youtube"}:
        return "en"
    return "zh"


def apply_labeling_columns(columns: dict[str, str], cfg: dict[str, Any]) -> dict[str, str]:
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    if cfg.get("text_column") or data.get("text_column"):
        return dict(columns)
    out = dict(columns)
    if resolve_platform(cfg) or cfg.get("prompt_lang") or data.get("prompt_lang"):
        out["comment"] = resolve_text_column(cfg)
    return out


def normalize_gold_column_name(name: str) -> str:
    """将 gold CSV 表头规范为 canonical 列名（若可识别）。"""
    s = str(name).strip()
    lm = _load_label_map()
    layers = lm.get("layers") or {}
    sub = layers.get("subject") or {}
    if s in sub.get("aliases", []) or s == sub.get("canonical_column"):
        return str(sub.get("canonical_column", "主体"))
    emo = layers.get("emotion") or {}
    if s in emo.get("aliases", []) or s == emo.get("canonical_column"):
        return str(emo.get("canonical_column", "情感"))
    if s == "评估对象":
        return "主体"
    if s.startswith("情感"):
        return "情感"
    return s


_PROMPT_DIR = ROOT / "human_label_llm" / "prompt"
_LAYER_FOR_GOLD = {
    "主体": "subject",
    "评估对象": "subject",
    "情感": "emotion",
    "stance": "stance",
    "立场": "stance",
}


def resolve_default_prompt_id(cfg: dict[str, Any]) -> str:
    """``{layer}_{zh|en}.md`` when present; else legacy eval_* default."""
    if cfg.get("prompt"):
        return str(cfg["prompt"])
    layer = cfg.get("layer") or cfg.get("label_layer")
    if not layer:
        gc = str(cfg.get("gold_column") or "").strip()
        layer = _LAYER_FOR_GOLD.get(gc)
    if layer:
        lang = resolve_prompt_lang(cfg)
        pid = f"{str(layer).strip().lower()}_{lang}"
        if (_PROMPT_DIR / f"{pid}.md").is_file():
            return pid
    return "eval_object_v1_comment_only"


def resolve_output_root(cfg: dict[str, Any]) -> Path:
    """显式 ``output_root`` → 如 ``output/label_runs``；否则 ``human_label_llm/output``（兼容旧 yaml）。"""
    raw = cfg.get("output_root") or (cfg.get("data") or {}).get("output_root")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else ROOT / p
    return Path(__file__).resolve().parent / "output"
