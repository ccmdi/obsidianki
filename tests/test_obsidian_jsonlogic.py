"""Tests for local JsonLogic evaluation (CLI vault parity)."""

import pytest

from obsidianki.api.obsidian_jsonlogic import eval_jsonlogic


def test_var_dot_path():
    data = {"path": "a/b.md", "stat": {"mtime": 100, "size": 50}, "tags": ["x"]}
    assert eval_jsonlogic({"var": "path"}, data) == "a/b.md"
    assert eval_jsonlogic({"var": "stat.mtime"}, data) == 100


def test_if_and_glob():
    data = {"path": "notes/old.md", "stat": {"mtime": 1, "size": 200}, "tags": []}
    q = {
        "if": [
            {
                "and": [
                    {"<": [{"var": "stat.mtime"}, 9999999999999]},
                    {">": [{"var": "stat.size"}, 100]},
                    {"glob": ["notes/*", {"var": "path"}]},
                ]
            },
            {"var": ""},
            None,
        ]
    }
    assert eval_jsonlogic(q, data) == data


def test_excluded_tag():
    data = {"path": "x.md", "stat": {"mtime": 1, "size": 200}, "tags": ["private", "ok"]}
    q = {
        "if": [
            {"!": {"in": ["private", {"var": "tags"}]}},
            {"var": ""},
            None,
        ]
    }
    assert eval_jsonlogic(q, data) is None


@pytest.mark.parametrize(
    "op,args,expected",
    [
        ("or", [{"in": ["a", {"var": "tags"}]}, {"in": ["b", {"var": "tags"}]}], True),
        ("and", [{">": [{"var": "stat.size"}, 50]}, {">": [{"var": "stat.size"}, 500]}], False),
    ],
)
def test_or_in_tags(op, args, expected):
    data = {"path": "t.md", "stat": {"mtime": 0, "size": 100}, "tags": ["a"]}
    assert bool(eval_jsonlogic({op: args}, data)) == expected
