"""Shared vault query and sampling logic for REST and CLI Obsidian clients."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import obsidianki.cli.config as _oki_config
from obsidianki.cli.models import Note
from obsidianki.api.obsidian_filters import (
    combine_filters,
    build_folder_filter,
    build_excluded_tags_filter,
)


class ObsidianVaultOpsMixin:
    """Requires subclass to implement ``search`` and ``get_note_content``."""

    def _build_folder_filter(self, search_folders: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        return build_folder_filter(search_folders)

    def _build_excluded_tags_filter(self) -> Optional[Dict[str, Any]]:
        return build_excluded_tags_filter()

    def _combine_filters(self, *filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return combine_filters(*filters)

    def get_old_notes(self, days: int, limit: int = 0) -> List[Note]:
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_ms = int(cutoff_date.timestamp() * 1000)

        query = self._combine_filters(
            {"<": [{"var": "stat.mtime"}, cutoff_ms]},
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(_oki_config.CONFIG.search_folders),
            self._build_excluded_tags_filter(),
        )

        results = self.search(query)

        if limit and len(results) > limit:
            return results[:limit]

        return results

    def get_tagged_notes(self, tags: List[str], exclude_recent_days: int = 0) -> List[Note]:
        tag_filter = {
            "or": [
                {"in": [tag, {"var": "tags"}]}
                for tag in tags
            ]
        }

        filters: List[Optional[Dict[str, Any]]] = [tag_filter]

        if exclude_recent_days > 0:
            cutoff_date = datetime.now() - timedelta(days=exclude_recent_days)
            cutoff_ms = int(cutoff_date.timestamp() * 1000)
            filters.append({"<": [{"var": "stat.mtime"}, cutoff_ms]})

        filters.append(self._build_folder_filter(_oki_config.CONFIG.search_folders))
        filters.append(self._build_excluded_tags_filter())

        query = self._combine_filters(*filters)
        return self.search(query)

    def sample_old_notes(
        self,
        days: int,
        limit: int = 0,
        bias_strength: float = 0.0,
        search_folders: List[str] | None = None,
    ) -> List[Note]:
        if search_folders is None:
            search_folders = []
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_ms = int(cutoff_date.timestamp() * 1000)

        query = self._combine_filters(
            {"<": [{"var": "stat.mtime"}, cutoff_ms]},
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter(),
        )

        all_notes = self.search(query)

        if not all_notes:
            return []

        all_notes = [note for note in all_notes if not _oki_config.CONFIG.is_note_hidden(note.path)]

        if not all_notes:
            return []

        if not limit or len(all_notes) <= limit:
            return all_notes

        return self._weighted_sample(all_notes, limit, bias_strength)

    def _weighted_sample(self, notes: List[Note], limit: int, bias_strength: float = 0.0) -> List[Note]:
        weights = [note.get_sampling_weight(bias_strength) for note in notes]

        sampled_notes = []
        available_notes = list(notes)
        available_weights = list(weights)

        for _ in range(min(limit, len(available_notes))):
            chosen = random.choices(available_notes, weights=available_weights, k=1)[0]
            chosen_idx = available_notes.index(chosen)

            sampled_notes.append(chosen)

            available_notes.pop(chosen_idx)
            available_weights.pop(chosen_idx)

        return sampled_notes

    def find_by_pattern(
        self,
        pattern: str,
        sample_size: int = 0,
        bias_strength: float = 0.0,
        search_folders: List[str] | None = None,
    ) -> List[Note]:
        if search_folders is None:
            search_folders = []
        if pattern.endswith("/*"):
            directory_path = pattern[:-2]
            pattern_filter = {"glob": [f"{directory_path}/*", {"var": "path"}]}
        elif "*" in pattern:
            glob_pattern = pattern if pattern.endswith("*") or pattern.startswith("*") else f"*{pattern}*"
            pattern_filter = {"glob": [glob_pattern, {"var": "path"}]}
        else:
            pattern_filter = {"glob": [f"*{pattern}*", {"var": "path"}]}

        query = self._combine_filters(
            pattern_filter,
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter(),
        )

        results = self.search(query)

        if not results:
            return []

        results = [note for note in results if not _oki_config.CONFIG.is_note_hidden(note.path)]

        if not results:
            return []

        if not sample_size or len(results) <= sample_size:
            return results

        if _oki_config.CONFIG.sampling_mode == "weighted":
            return self._weighted_sample(results, sample_size, bias_strength)
        return random.sample(results, sample_size)

    def find_by_name(self, note_name: str, search_folders: List[str]) -> Note | None:
        query = self._combine_filters(
            {"glob": [f"*{note_name}*", {"var": "path"}]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter(),
        )

        results = self.search(query)

        if not results:
            return None

        if len(results) == 1:
            return results[0]
        for note in results:
            filename = note.filename.lower()
            if filename == note_name.lower() or filename == f"{note_name.lower()}.md":
                return note
        return results[0]
