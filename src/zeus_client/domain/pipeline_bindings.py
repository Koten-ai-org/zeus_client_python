"""FTS pipeline bindings.

@step.ids is node ids only. An fts search leaves that list empty, so a
later project of @step.ids returns no rows. The hit list is @step.doc_keys.

order by id copies source-key tokens onto doc_keys and leaves node_ids
empty. A field or created_at ranker fetches and fills both lists, so
@ranked.ids stays a node-id bind. set copies onto the list named by
id_kind, so only id_kind doc_keys carries those keys. The rewrite follows
the keys through project, order, and enrich. get, traverse, and narrow_to
reject doc keys and keep the node-id binding.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Verbs that accept either a node-id list or a doc-key list.
_REWRITE_VERBS = frozenset({"project", "order", "enrich"})

_ORDER_IDENT = re.compile(r"^[A-Za-z0-9_]+$")
_BINDING = re.compile(r"@([^\s@.]+)\.(ids|doc_keys|scored|node_ids|entity_ids|edge_ids)\b")
_CARRY_KINDS = frozenset({"ids", "doc_keys", "scored"})


def _verb(step: Mapping[str, Any]) -> str:
    verb = str(step.get("verb") or "").strip()
    if not verb:
        verb = str(step.get("tool") or "").strip()
    return verb.lower()


def _name(step: Mapping[str, Any]) -> str:
    name = str(step.get("as") or "").strip()
    if not name:
        name = str(step.get("name") or "").strip()
    return name


def _param(step: Mapping[str, Any], key: str) -> Any:
    """Value Zeus reads. A present params bag wins, then args, then a flat key."""
    params = step.get("params")
    if isinstance(params, Mapping):
        return params.get(key)
    args = step.get("args")
    if isinstance(args, Mapping):
        return args.get(key)
    return step.get(key)


def _strategy(step: Mapping[str, Any]) -> str:
    return str(_param(step, "strategy") or "").strip().lower()


def _normalize_order_by(raw: Any) -> str:
    by = str(raw or "").strip()
    if by in ("", "id", "created_at") or by.startswith("field:"):
        return by
    if _ORDER_IDENT.fullmatch(by):
        return "field:" + by
    return by


def _fts_names(steps: list[Any]) -> set[str]:
    names: set[str] = set()
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        if _verb(step) != "search" or _strategy(step) != "fts":
            continue
        name = _name(step)
        if name:
            names.add(name)
    return names


def _ids_pattern(names: set[str]) -> re.Pattern[str] | None:
    if not names:
        return None
    ordered = sorted(names, key=len, reverse=True)
    alt = "|".join(re.escape(name) for name in ordered)
    return re.compile(rf"@({alt})\.ids\b")


def _iter_strings(value: Any) -> list[str]:
    found: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)

    walk(value)
    return found


def _has_carry(value: Any, producers: set[str]) -> bool:
    for text in _iter_strings(value):
        for match in _BINDING.finditer(text):
            if match.group(1) in producers and match.group(2) in _CARRY_KINDS:
                return True
    return False


def _inputs_are_doc_keys(inputs: Any, producers: set[str]) -> bool:
    """True when every inputs string is only a doc-key carry from producers."""
    strings = _iter_strings(inputs)
    if not strings:
        return False
    saw = False
    for text in strings:
        refs = list(_BINDING.finditer(text))
        if not refs or _BINDING.sub("", text).strip():
            return False
        for match in refs:
            name, kind = match.group(1), match.group(2)
            if name in producers and kind in _CARRY_KINDS:
                saw = True
                continue
            return False
    return saw


def _assign_param(step: dict[str, Any], key: str, value: Any) -> None:
    params = step.get("params")
    if isinstance(params, dict):
        params[key] = value
        return
    args = step.get("args")
    if isinstance(args, dict):
        args[key] = value
        return
    step[key] = value


def _rewrite(value: Any, pattern: re.Pattern[str], changed: list[str]) -> Any:
    if isinstance(value, str):

        def sub(match: re.Match[str]) -> str:
            step = match.group(1)
            if step not in changed:
                changed.append(step)
            return f"@{step}.doc_keys"

        return pattern.sub(sub, value)
    if isinstance(value, list):
        return [_rewrite(item, pattern, changed) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key == "narrow_to":
                out[key] = item
            else:
                out[key] = _rewrite(item, pattern, changed)
        return out
    return value


def rewrite_fts_ids_to_doc_keys(
    body: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return a pipeline body whose later steps bind FTS hits as doc_keys.

    Hybrid, vector, and find steps are left alone. @step.node_ids, an
    existing @step.doc_keys binding, and narrow_to are left alone. The
    returned names are the steps whose @step.ids token was rewritten.
    """
    if not isinstance(body, Mapping):
        return {}, ()
    raw_steps = body.get("steps")
    if not isinstance(raw_steps, list):
        return dict(body), ()
    producers = _fts_names(raw_steps)
    if not producers:
        return dict(body), ()
    changed: list[str] = []
    mutated = False
    new_steps: list[Any] = []
    for step in raw_steps:
        if not isinstance(step, Mapping):
            new_steps.append(step)
            continue
        verb = _verb(step)
        name = _name(step)
        pattern = _ids_pattern(producers)
        rewrite_step = False
        flip_kind = False
        if pattern is not None and verb in _REWRITE_VERBS:
            rewrite_step = True
        elif pattern is not None and verb == "set":
            kind = str(_param(step, "id_kind") or "").strip().lower()
            if kind == "doc_keys":
                rewrite_step = True
            elif _inputs_are_doc_keys(_param(step, "inputs"), producers):
                rewrite_step = True
                flip_kind = True
        if rewrite_step and pattern is not None:
            before = len(changed)
            rewritten = _rewrite(dict(step), pattern, changed)
            if flip_kind:
                _assign_param(rewritten, "id_kind", "doc_keys")
            if len(changed) != before or flip_kind:
                mutated = True
            new_steps.append(rewritten)
        else:
            rewritten = step
            new_steps.append(step)
        if not name or not isinstance(rewritten, Mapping):
            continue
        if verb == "order" and _normalize_order_by(_param(rewritten, "by")) == "id":
            if _has_carry(_param(rewritten, "ids"), producers):
                producers.add(name)
        elif verb == "set":
            kind = str(_param(rewritten, "id_kind") or "").strip().lower()
            if kind == "doc_keys" and _has_carry(_param(rewritten, "inputs"), producers):
                producers.add(name)
    if not mutated:
        return dict(body), ()
    out = dict(body)
    out["steps"] = new_steps
    return out, tuple(changed)
