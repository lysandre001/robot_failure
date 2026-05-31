"""Template render: row + column map → filled prompt markdown."""
from __future__ import annotations

import re
from typing import Any

_SLOT_RE = re.compile(r"\{(\w+)\}")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# scope slot 名 → INPUT 区 XML 标签名
SLOT_TO_TAG = {"comment": "comment", "title": "post_title", "caption": "post_caption"}


def _cell(row: Any, col: str) -> str:
    v = row.get(col, "") if hasattr(row, "get") else getattr(row, col, "")
    if v is None or (isinstance(v, float) and str(v) == "nan"):
        return ""
    s = str(v).strip()
    return "" if not s or s.lower() == "nan" else s


def row_slot_values(row: Any, columns: dict[str, str], active_slots: list[str]) -> dict[str, str]:
    """填槽名 → 单元格文本（columns 的 key 即 prompt 里的 {name}）。"""
    return {slot: _cell(row, columns[slot]) for slot in active_slots if slot in columns}


def strip_ignored_markdown(text: str) -> str:
    """去掉 <!-- ... -->（仅给人类/dryrun 看的注释，不发给模型）。"""
    return _HTML_COMMENT_RE.sub("", text)


def strip_empty_input_tags(text: str, active_slots: list[str]) -> str:
    """未纳入当前 scope 的 INPUT 标签整段删除。"""
    out = text
    for slot, tag in SLOT_TO_TAG.items():
        if slot not in active_slots:
            out = re.sub(rf"<{tag}>.*?</{tag}>\s*", "", out, flags=re.S)
    return out


def template_placeholders(template: str) -> set[str]:
    return set(_SLOT_RE.findall(template))


def fill_prompt(
    template: str,
    values: dict[str, str],
    *,
    active_slots: list[str] | None = None,
) -> str:
    """用 str.format 填槽；模板里字面量花括号须写成 {{ }}。"""
    keys = template_placeholders(template)
    kwargs = {k: values.get(k, "") for k in keys}
    text = template.format(**kwargs)
    text = strip_ignored_markdown(text)
    if active_slots is not None:
        text = strip_empty_input_tags(text, active_slots)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
