"""Single .md prompt file (YAML frontmatter + body) → messages for the API."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from human_label_llm.format import fill_prompt, row_slot_values, template_placeholders

PROMPT_DIR = Path(__file__).resolve().parent / "prompt"
_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.S)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

DEFAULT_SCOPE_SLOTS: dict[str, list[str]] = {
    "scope_comment_only": ["comment"],
    "scope_comment_title": ["comment", "title"],
    "scope_comment_title_caption": ["comment", "title", "caption"],
}


@dataclass(frozen=True)
class OutputSpec:
    json_field: str
    reason_field: str
    retry_hint: str


@dataclass(frozen=True)
class PromptSpec:
    id: str
    version: str
    description: str
    prompt_file: Path
    template: str
    label_map: dict[str, str]
    output: OutputSpec
    system: str = ""

    @property
    def valid_labels(self) -> frozenset[str]:
        return frozenset(self.label_map.keys())


def parse_prompt_md(text: str, *, path: Path | None = None) -> tuple[dict[str, Any], str]:
    """拆成 frontmatter（不发给模型）与正文模板。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        hint = f" ({path})" if path else ""
        raise ValueError(
            f"Prompt .md must start with YAML frontmatter --- ... ---{hint}"
        )
    meta = yaml.safe_load(m.group(1))
    if not isinstance(meta, dict):
        raise ValueError(f"Invalid frontmatter{hint if path else ''}")
    body = text[m.end() :]
    return meta, body


def resolve_scope_slots(cfg: dict[str, Any]) -> dict[str, list[str]]:
    user = cfg.get("scope_slots")
    if isinstance(user, dict) and user:
        return {k: list(v) for k, v in user.items()}
    return dict(DEFAULT_SCOPE_SLOTS)


def resolve_scopes(cfg: dict[str, Any]) -> list[str]:
    slots = resolve_scope_slots(cfg)
    selected = cfg.get("scopes")
    if selected:
        unknown = [s for s in selected if s not in slots]
        if unknown:
            raise ValueError(f"Unknown scopes {unknown}; defined: {list(slots)}")
        return list(selected)
    return list(slots.keys())


@lru_cache(maxsize=16)
def load_spec(prompt_id: str) -> PromptSpec:
    prompt_file = PROMPT_DIR / f"{prompt_id}.md"
    if not prompt_file.is_file():
        raise FileNotFoundError(
            f"Prompt not found: {prompt_file} (one file per prompt: {{id}}.md with frontmatter)"
        )
    raw_text = prompt_file.read_text(encoding="utf-8")
    meta, template = parse_prompt_md(raw_text, path=prompt_file)

    out = meta.get("output") or {}
    output = OutputSpec(
        json_field=str(out.get("json_field", "category")),
        reason_field=str(out.get("reason_field", "reason")),
        retry_hint=str(out.get("retry_hint", "")),
    )
    label_map = meta.get("label_map") or {}

    return PromptSpec(
        id=str(meta.get("id", prompt_id)),
        version=str(meta.get("version", "")),
        description=str(meta.get("description", "")).strip(),
        prompt_file=prompt_file,
        template=template,
        label_map={str(k): str(v) for k, v in label_map.items()},
        output=output,
        system=str(meta.get("system", "")).strip(),
    )


def build_messages(
    row: Any,
    scope_id: str,
    columns: dict[str, str],
    spec: PromptSpec,
    scope_slots: dict[str, list[str]],
) -> list[dict[str, str]]:
    if scope_id not in scope_slots:
        raise ValueError(f"Unknown scope_id: {scope_id!r}. Defined: {list(scope_slots)}")

    active = scope_slots[scope_id]
    values = row_slot_values(row, columns, active)
    user = fill_prompt(spec.template, values, active_slots=active)

    if spec.system:
        return [{"role": "system", "content": spec.system}, {"role": "user", "content": user}]
    return [{"role": "user", "content": user}]


def dryrun_slot_report(
    row: Any,
    scope_id: str,
    columns: dict[str, str],
    spec: PromptSpec,
    scope_slots: dict[str, list[str]],
) -> dict[str, Any]:
    """返回填槽绑定与渲染结果，供 dryrun 校验。"""
    active = scope_slots[scope_id]
    values = row_slot_values(row, columns, active)
    needed = template_placeholders(spec.template)
    missing_cols = [s for s in active if s not in columns]
    empty_active = [s for s in active if not values.get(s)]
    unused_in_template = sorted(needed - set(columns.keys()))
    return {
        "scope_id": scope_id,
        "active_slots": active,
        "columns_map": {s: columns.get(s) for s in active},
        "slot_values": values,
        "empty_slots": empty_active,
        "missing_column_keys": missing_cols,
        "template_placeholders": sorted(needed),
        "unused_placeholders": unused_in_template,
        "messages": build_messages(row, scope_id, columns, spec, scope_slots),
    }


def parse_response(text: str, spec: PromptSpec) -> tuple[str, str, str, str]:
    """Returns (label_en, label_cn, reason, status). status: ok | parse_error."""
    if not text:
        return "", "", "", "parse_error"

    field = spec.output.json_field
    reason_field = spec.output.reason_field
    valid = spec.valid_labels

    def to_en(raw: str) -> str | None:
        s = raw.strip()
        if s in valid:
            return s
        lower = s.lower()
        for k in valid:
            if k.lower() == lower:
                return k
        return None

    candidates = [text.strip()]
    if candidates[0].startswith("```"):
        candidates[0] = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidates[0], flags=re.I | re.M)
    candidates.extend(_JSON_OBJ_RE.findall(text))

    for cand in candidates:
        try:
            obj = json.loads(cand)
            label_en = to_en(str(obj.get(field, "")))
            if label_en:
                reason = str(obj.get(reason_field, "")).strip()
                return label_en, spec.label_map.get(label_en, ""), reason, "ok"
        except json.JSONDecodeError:
            continue

    for k in valid:
        if k in text:
            return k, spec.label_map.get(k, ""), text.strip()[:200], "ok"
    return "", "", text.strip()[:200], "parse_error"
