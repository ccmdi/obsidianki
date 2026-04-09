"""JsonLogic-style filters shared by REST and CLI Obsidian clients."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import obsidianki.cli.config as _oki_config


def combine_filters(*filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    valid_filters = [f for f in filters if f is not None]

    if not valid_filters:
        return {"var": ""}

    if len(valid_filters) == 1:
        condition = valid_filters[0]
    else:
        condition = {"and": valid_filters}

    return {
        "if": [
            condition,
            {"var": ""},
            None,
        ]
    }


def build_folder_filter(search_folders: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    folders = search_folders or []
    if not folders:
        return None

    if len(folders) == 1:
        return {"glob": [f"{folders[0]}/*", {"var": "path"}]}

    return {
        "or": [
            {"glob": [f"{folder}/*", {"var": "path"}]}
            for folder in folders
        ]
    }


def build_excluded_tags_filter(excluded_tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    if excluded_tags is None:
        cfg = _oki_config.CONFIG
        if not cfg or not cfg.excluded_tags:
            return None
        excluded_tags = cfg.excluded_tags

    if not excluded_tags:
        return None

    return {
        "and": [
            {"!": {"in": [tag, {"var": "tags"}]}}
            for tag in excluded_tags
        ]
    }
