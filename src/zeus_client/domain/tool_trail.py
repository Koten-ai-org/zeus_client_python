"""Slim Zeus hop trail for later LLM rounds (CHECKLIST B · AGENT_TOOL_TRAIL)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "trail_entry_from_hop",
    "model_facing_line",
    "error_class_for",
]


def error_class_for(*, ok: bool, status: int, error: str | None = None) -> str | None:
    if ok:
        return None
    if status == 409:
        return "contract_mismatch"
    if status in {429, 503} or (error and "timeout" in str(error).lower()):
        return "retryable_later"
    if 400 <= int(status or 0) < 500:
        return "do_not_retry_same_args"
    return "zeus_error"


def _hint(*, ok: bool, status: int, empty: bool, error_class: str | None) -> str | None:
    if ok and empty:
        return "empty"
    if ok:
        return "success"
    if error_class == "contract_mismatch" or error_class == "do_not_retry_same_args":
        return "do_not_retry_same_args"
    if error_class == "retryable_later":
        return "retryable_later"
    return None


def trail_entry_from_hop(
    hop: Mapping[str, Any],
    *,
    seq: int,
    empty: bool = False,
) -> dict[str, Any]:
    ok = bool(hop.get("ok"))
    status = int(hop.get("status") or hop.get("status_code") or 0)
    err = hop.get("error")
    klass = error_class_for(ok=ok, status=status, error=str(err) if err else None)
    verb = str(hop.get("name") or hop.get("verb") or "")
    entry: dict[str, Any] = {
        "seq": seq,
        "verb": verb,
        "l0": f"zeus.{verb}" if verb else "",
        "ok": ok,
        "http_status": status or None,
        "req_id": hop.get("req_id"),
        "error_class": klass,
        "hint": _hint(ok=ok, status=status, empty=empty, error_class=klass),
        "path": hop.get("url") or hop.get("path") or "",
    }
    return {k: v for k, v in entry.items() if v is not None and v != ""}


def model_facing_line(entry: Mapping[str, Any]) -> str:
    """One hop for the model. req_id stays off this line."""
    seq = entry.get("seq", "?")
    l0 = str(entry.get("l0") or entry.get("verb") or "hop")
    status = "ok" if entry.get("ok") else "fail"
    hint = entry.get("hint") or ""
    return f"{seq}. {l0} {status} hint={hint}"
