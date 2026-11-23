"""Model-facing tool trail lines (ZCP-137)."""

from __future__ import annotations

from zeus_client.domain.tool_trail import (
    model_facing_line,
    model_facing_lines,
    render_trail_inject,
    trail_entry_from_hop,
)


def test_success_line_is_model_facing_without_req_id() -> None:
    entry = trail_entry_from_hop(
        {"name": "search", "ok": True, "status": 200, "req_id": "req-ok"},
        seq=1,
    )
    line = model_facing_line(entry)
    assert line == "1. zeus.search ok hint=success"
    assert "req_id" not in line


def test_empty_hint_line_omits_req_id() -> None:
    entry = trail_entry_from_hop(
        {"name": "search", "ok": True, "status": 200, "req_id": "req-empty"},
        seq=1,
        empty=True,
    )
    line = model_facing_line(entry)
    assert line == "1. zeus.search ok hint=empty"
    assert "req_id" not in line


def test_409_line_hint_omits_req_id_log_keeps_it() -> None:
    entry = trail_entry_from_hop(
        {
            "name": "search",
            "ok": False,
            "status": 409,
            "req_id": "req-409",
            "error": "contract mismatch",
        },
        seq=1,
    )
    line = model_facing_line(entry)
    assert "hint=do_not_retry_same_args" in line
    assert "req_id" not in line
    logged = render_trail_inject([entry])
    assert "req_id=req-409" in logged


def test_model_facing_stops_after_16_and_keeps_earlier_lines() -> None:
    entries = [
        trail_entry_from_hop(
            {"name": "search", "ok": True, "status": 200, "req_id": f"req-{seq}"},
            seq=seq,
        )
        for seq in range(1, 18)
    ]
    lines = model_facing_lines(entries)
    assert lines == [f"{seq}. zeus.search ok hint=success" for seq in range(1, 17)]
    assert all(not line.startswith("17.") for line in lines)
    assert [entry["seq"] for entry in entries] == list(range(1, 18))
