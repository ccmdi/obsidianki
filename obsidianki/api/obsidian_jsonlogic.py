"""Evaluate the JsonLogic subset used by ObsidianKi vault queries (REST API parity for CLI)."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, Dict


def eval_jsonlogic(expr: Any, data: Dict[str, Any]) -> Any:
    if expr is None:
        return None
    if not isinstance(expr, dict):
        return expr
    if len(expr) != 1:
        raise ValueError(f"Unsupported JsonLogic expression: {expr!r}")

    op, raw_args = next(iter(expr.items()))

    if op == "var":
        if raw_args == "":
            return data
        parts = str(raw_args).split(".")
        cur: Any = data
        for p in parts:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur

    if op == "if":
        args = raw_args
        if not isinstance(args, list) or len(args) < 2:
            raise ValueError(f"Invalid 'if': {args!r}")
        cond = eval_jsonlogic(args[0], data)
        if cond:
            return eval_jsonlogic(args[1], data)
        if len(args) > 2:
            return eval_jsonlogic(args[2], data)
        return None

    if op == "and":
        if not isinstance(raw_args, list):
            raise ValueError(f"Invalid 'and': {raw_args!r}")
        last: Any = True
        for part in raw_args:
            last = eval_jsonlogic(part, data)
            if not last:
                return last
        return last

    if op == "or":
        if not isinstance(raw_args, list):
            raise ValueError(f"Invalid 'or': {raw_args!r}")
        last: Any = False
        for part in raw_args:
            last = eval_jsonlogic(part, data)
            if last:
                return last
        return last

    if op == "!":
        return not eval_jsonlogic(raw_args, data)

    if op == "<":
        args = raw_args
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError(f"Invalid '<': {args!r}")
        a = eval_jsonlogic(args[0], data)
        b = eval_jsonlogic(args[1], data)
        if a is None or b is None:
            return False
        return a < b

    if op == ">":
        args = raw_args
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError(f"Invalid '>': {args!r}")
        a = eval_jsonlogic(args[0], data)
        b = eval_jsonlogic(args[1], data)
        if a is None or b is None:
            return False
        return a > b

    if op == "in":
        args = raw_args
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError(f"Invalid 'in': {args!r}")
        needle = eval_jsonlogic(args[0], data)
        haystack = eval_jsonlogic(args[1], data)
        if haystack is None:
            return False
        if isinstance(haystack, (list, tuple, set)):
            return needle in haystack
        if isinstance(haystack, str):
            return needle in haystack
        return False

    if op == "glob":
        args = raw_args
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError(f"Invalid 'glob': {args!r}")
        pattern = eval_jsonlogic(args[0], data)
        path = eval_jsonlogic(args[1], data)
        if pattern is None or path is None:
            return False
        path_n = str(path).replace("\\", "/")
        pat_n = str(pattern).replace("\\", "/")
        return fnmatch(path_n, pat_n)

    raise ValueError(f"Unsupported JsonLogic operator: {op!r}")
