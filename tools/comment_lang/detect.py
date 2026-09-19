"""Local language detection + is_mixed flag for comment text."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from phase1.preprocess import normalize_text

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "comment_lang.json"
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_LETTER_RE = re.compile(r"[a-z]{2,}")


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else CONFIG_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _lingua_detector(cfg_json: str):
    from lingua import Language, LanguageDetectorBuilder

    cfg = json.loads(cfg_json)
    lang_names = cfg.get("lingua_languages") or []
    langs = []
    for name in lang_names:
        key = str(name).upper().replace("-", "_").replace(" ", "_")
        try:
            langs.append(getattr(Language, key))
        except AttributeError:
            continue
    if not langs:
        langs = [Language.CHINESE, Language.ENGLISH]
    return LanguageDetectorBuilder.from_languages(*langs).build()


def _lingua_to_iso(lang_obj, cfg: dict[str, Any]) -> str:
    iso_map = cfg.get("lingua_to_iso") or {}
    name_key = lang_obj.name.title() if hasattr(lang_obj, "name") else str(lang_obj)
    if name_key in iso_map:
        return str(iso_map[name_key]).lower()
    # fallback: CHINESE -> Chinese in map
    for k, v in iso_map.items():
        if k.upper() == lang_obj.name:
            return str(v).lower()
    try:
        return lang_obj.iso_code_639_1.name.lower()
    except Exception:
        return "und"


def _letter_token_count(text: str) -> int:
    return len(_LETTER_RE.findall(normalize_text(text).casefold()))


def is_mixed(text: str, *, min_han: int = 1, min_letter_tokens: int = 2) -> bool:
    t = normalize_text(text)
    if not t:
        return False
    n_han = len(_HAN_RE.findall(t))
    n_letter = _letter_token_count(t)
    return n_han >= min_han and n_letter >= min_letter_tokens


def detect_language(text: str, cfg: dict[str, Any] | None = None) -> tuple[str, int]:
    """
    Returns (iso639-1 language code, is_mixed 0/1).
    Empty/too-short -> ('und', 0).
    """
    cfg = cfg or load_config()
    t = normalize_text(text)
    if not t or len(t) < 2:
        return "und", 0

    mixed_flag = 1 if is_mixed(
        t,
        min_han=int(cfg.get("mixed_min_han", 1)),
        min_letter_tokens=int(cfg.get("mixed_min_letter_tokens", 2)),
    ) else 0

    # Very short CJK-only or Latin-only: heuristic before lingua
    n_han = len(_HAN_RE.findall(t))
    n_letter = _letter_token_count(t)
    if n_han > 0 and n_letter == 0 and len(t) <= 4:
        return "zh", mixed_flag
    if n_letter > 0 and n_han == 0 and len(t) <= 6:
        return "en", mixed_flag

    try:
        detector = _lingua_detector(json.dumps(cfg, sort_keys=True))
        lang = detector.detect_language_of(t)
        if lang is None:
            if n_han > 0 and n_letter == 0:
                return "zh", mixed_flag
            if n_letter > 0 and n_han == 0:
                return "en", mixed_flag
            return "und", mixed_flag
        iso = _lingua_to_iso(lang, cfg)
        return iso[:2] if iso else "und", mixed_flag
    except Exception:
        if n_han > 0 and n_letter == 0:
            return "zh", mixed_flag
        if n_letter > 0:
            return "en", mixed_flag
        return "und", mixed_flag


def needs_translation(language: str, is_mixed_val: int) -> bool:
    return not (str(language).lower() == "en" and int(is_mixed_val) == 0)
