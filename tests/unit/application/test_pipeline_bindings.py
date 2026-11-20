"""FTS pipeline @step.ids is rewritten to @step.doc_keys before Zeus."""

from __future__ import annotations

from zeus_client.domain.pipeline_bindings import rewrite_fts_ids_to_doc_keys


def _peach():
    return {
        "steps": [
            {
                "as": "peach_beers",
                "verb": "search",
                "entity_type": "Beer",
                "strategy": "fts",
                "query_text": "peach",
            },
            {
                "as": "ranked",
                "verb": "project",
                "ids": "@peach_beers.ids",
                "fields": ["name", "style"],
            },
        ],
        "summary": "keep @peach_beers.ids in the summary",
    }


def test_fts_project_ids_become_doc_keys() -> None:
    body, changed = rewrite_fts_ids_to_doc_keys(_peach())
    assert changed == ("peach_beers",)
    assert body["steps"][1]["ids"] == "@peach_beers.doc_keys"
    assert body["summary"] == "keep @peach_beers.ids in the summary"
    assert body["steps"][0]["strategy"] == "fts"


def test_order_passthrough_rewrites_the_next_ids() -> None:
    body = {
        "steps": [
            {"as": "peach_beers", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "ranked", "verb": "order", "ids": "@peach_beers.ids", "by": "id"},
            {"as": "rows", "verb": "project", "ids": "@ranked.ids", "fields": ["name"]},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("peach_beers", "ranked")
    assert out["steps"][1]["ids"] == "@peach_beers.doc_keys"
    assert out["steps"][2]["ids"] == "@ranked.doc_keys"


def test_hybrid_ids_stay() -> None:
    body = {
        "steps": [
            {"as": "hits", "verb": "search", "strategy": "hybrid", "query_text": "peach"},
            {"as": "ranked", "verb": "project", "ids": "@hits.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out["steps"][1]["ids"] == "@hits.ids"


def test_node_ids_and_doc_keys_stay() -> None:
    body = {
        "steps": [
            {"as": "hits", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {
                "as": "ranked",
                "verb": "project",
                "ids": "@hits.node_ids",
                "src_keys": "@hits.doc_keys",
            },
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out["steps"][1]["ids"] == "@hits.node_ids"
    assert out["steps"][1]["src_keys"] == "@hits.doc_keys"


def test_nested_params_and_longer_step_name() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "peach_beers", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"verb": "project", "params": {"ids": ["@peach.ids", "@peach_beers.ids"]}},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert set(changed) == {"peach", "peach_beers"}
    assert out["steps"][2]["params"]["ids"] == [
        "@peach.doc_keys",
        "@peach_beers.doc_keys",
    ]


def test_strategy_inside_params() -> None:
    body = {
        "steps": [
            {"as": "hits", "verb": "search", "params": {"strategy": "fts", "query_text": "peach"}},
            {"as": "rows", "verb": "project", "ids": "@hits.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("hits",)
    assert out["steps"][1]["ids"] == "@hits.doc_keys"


def test_no_steps_is_unchanged() -> None:
    body = {"summary": "hi"}
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out == body


def test_fetched_order_keeps_the_following_get() -> None:
    for by in ("field:name", "name", "created_at"):
        body = {
            "steps": [
                {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
                {"as": "ranked", "verb": "order", "ids": "@peach.ids", "by": by},
                {"as": "rows", "verb": "get", "ids": "@ranked.ids"},
            ]
        }
        out, changed = rewrite_fts_ids_to_doc_keys(body)
        assert changed == ("peach",), by
        assert out["steps"][1]["ids"] == "@peach.doc_keys", by
        assert out["steps"][1]["by"] == by
        assert out["steps"][2]["ids"] == "@ranked.ids", by

    already = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "ranked", "verb": "order", "ids": "@peach.doc_keys", "by": "field:name"},
            {"as": "rows", "verb": "get", "ids": "@ranked.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(already)
    assert changed == ()
    assert out["steps"][2]["ids"] == "@ranked.ids"


def test_order_by_id_follows_scored_doc_keys() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "ranked", "verb": "order", "ids": "@peach.scored", "by": "id"},
            {"as": "rows", "verb": "project", "ids": "@ranked.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("ranked",)
    assert out["steps"][1]["ids"] == "@peach.scored"
    assert out["steps"][2]["ids"] == "@ranked.doc_keys"


def test_get_traverse_and_narrow_to_keep_ids() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "walk", "verb": "traverse", "from": "@peach.ids"},
            {"as": "found", "verb": "find", "narrow_to": "@peach.ids"},
            {
                "as": "card",
                "verb": "project",
                "ids": "@peach.ids",
                "narrow_to": "@peach.ids",
            },
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("peach",)
    assert out["steps"][1]["from"] == "@peach.ids"
    assert out["steps"][2]["narrow_to"] == "@peach.ids"
    assert out["steps"][3]["ids"] == "@peach.doc_keys"
    assert out["steps"][3]["narrow_to"] == "@peach.ids"


def test_set_node_ids_keeps_a_mixed_union() -> None:
    body = {
        "steps": [
            {"as": "cities", "verb": "find", "entity_type": "City"},
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {
                "as": "both",
                "verb": "set",
                "op": "union",
                "id_kind": "node_ids",
                "inputs": ["@cities.ids", "@peach.ids"],
            },
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out["steps"][2]["inputs"] == ["@cities.ids", "@peach.ids"]
    assert out["steps"][2]["id_kind"] == "node_ids"


def test_set_of_fts_inputs_becomes_doc_keys() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {"as": "ale", "verb": "search", "strategy": "fts", "query_text": "ale"},
            {
                "as": "both",
                "verb": "set",
                "op": "union",
                "id_kind": "node_ids",
                "inputs": ["@peach.ids", "@ale.ids"],
            },
            {"as": "rows", "verb": "project", "ids": "@both.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("peach", "ale", "both")
    assert out["steps"][2]["inputs"] == ["@peach.doc_keys", "@ale.doc_keys"]
    assert out["steps"][2]["id_kind"] == "doc_keys"
    assert out["steps"][3]["ids"] == "@both.doc_keys"


def test_set_doc_keys_rewrites_fts_inputs() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {
                "as": "both",
                "verb": "set",
                "params": {
                    "op": "union",
                    "id_kind": "doc_keys",
                    "inputs": ["@peach.ids", "@peach.doc_keys"],
                },
            },
            {"as": "rows", "verb": "project", "ids": "@both.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("peach", "both")
    assert out["steps"][1]["params"]["inputs"] == ["@peach.doc_keys", "@peach.doc_keys"]
    assert out["steps"][1]["params"]["id_kind"] == "doc_keys"
    assert out["steps"][2]["ids"] == "@both.doc_keys"


def test_tool_name_and_args_count_as_fts() -> None:
    shapes = [
        {"name": "peach", "tool": "search", "args": {"strategy": "fts", "query_text": "peach"}},
        {"as": "peach", "verb": "search", "args": {"strategy": "fts"}},
        {"name": "peach", "tool": "search", "strategy": "fts", "query_text": "peach"},
    ]
    for search in shapes:
        body = {
            "steps": [
                search,
                {"as": "rows", "verb": "project", "ids": "@peach.ids"},
            ]
        }
        out, changed = rewrite_fts_ids_to_doc_keys(body)
        assert changed == ("peach",), search
        assert out["steps"][1]["ids"] == "@peach.doc_keys"


def test_params_bag_hides_a_flat_strategy() -> None:
    body = {
        "steps": [
            {
                "as": "hits",
                "verb": "search",
                "strategy": "fts",
                "params": {"query_text": "peach"},
            },
            {"as": "rows", "verb": "project", "ids": "@hits.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out["steps"][1]["ids"] == "@hits.ids"


def test_args_by_id_promotes_when_the_flat_by_is_a_field() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {
                "as": "ranked",
                "verb": "order",
                "by": "field:name",
                "args": {"ids": "@peach.ids", "by": "id"},
            },
            {"as": "rows", "verb": "project", "ids": "@ranked.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ("peach", "ranked")
    assert out["steps"][1]["args"]["ids"] == "@peach.doc_keys"
    assert out["steps"][1]["by"] == "field:name"
    assert out["steps"][2]["ids"] == "@ranked.doc_keys"


def test_carry_ignores_a_mention_outside_ids() -> None:
    body = {
        "steps": [
            {"as": "peach", "verb": "search", "strategy": "fts", "query_text": "peach"},
            {
                "as": "ranked",
                "verb": "order",
                "ids": "@other.ids",
                "by": "id",
                "note": "see @peach.doc_keys",
            },
            {"as": "rows", "verb": "project", "ids": "@ranked.ids"},
        ]
    }
    out, changed = rewrite_fts_ids_to_doc_keys(body)
    assert changed == ()
    assert out["steps"][1]["note"] == "see @peach.doc_keys"
    assert out["steps"][2]["ids"] == "@ranked.ids"
