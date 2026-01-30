import os
from urllib3.exceptions import InsecureRequestWarning
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from obsidianki.cli.config import console, CONFIG
from obsidianki.cli.models import Note
from obsidianki.api.base import BaseAPI

urllib3.disable_warnings(InsecureRequestWarning)

OBSIDIAN_TIMEOUT_LENGTH = 30


class ObsidianAPI(BaseAPI):
    def __init__(self):
        super().__init__("https://127.0.0.1:27124", OBSIDIAN_TIMEOUT_LENGTH)
        self.api_key = os.getenv("OBSIDIAN_API_KEY")

        if not self.api_key:
            raise ValueError("OBSIDIAN_API_KEY not found in environment variables")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def search(self, query: Dict[str, Any]) -> List[Note]:
        """Search notes using JsonLogic query - returns Note objects"""
        headers = {
            **self.headers,
            "Content-Type": "application/vnd.olrapi.jsonlogic+json"
        }

        try:
            url = f"{self.base_url}/search/"
            response = super()._make_request("POST", url, headers=headers, json=query, verify=False)
            results = self._parse_response(response)

            return [Note.from_jsonlogic_result(r) for r in results]
        except Exception as e:
            raise

    def dql(self, query: str) -> List[Note]:
        """Search notes using Dataview DQL query - returns Note objects.

        Note: Requires the Dataview plugin to be installed in Obsidian.
        Used primarily by agent mode (--agent) which generates DQL queries dynamically.
        """
        headers = {
            **self.headers,
            "Content-Type": "application/vnd.olrapi.dataview.dql+txt"
        }

        try:
            url = f"{self.base_url}/search/"
            response = super()._make_request("POST", url, headers=headers, data=query, verify=False)
            dict_results = self._parse_response(response)

            return [Note.from_dql_result(result) for result in dict_results]
        except Exception as e:
            raise

    def _build_folder_filter(self, search_folders: Optional[List[str]] = None) -> Optional[Dict]:
        """Build JsonLogic filter for folder restrictions"""
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

    def _build_excluded_tags_filter(self) -> Optional[Dict]:
        """Build JsonLogic filter to exclude notes with certain tags"""
        if not CONFIG or not CONFIG.excluded_tags:
            return None

        # None of the excluded tags should be present
        return {
            "and": [
                {"!": {"in": [tag, {"var": "tags"}]}}
                for tag in CONFIG.excluded_tags
            ]
        }

    def _combine_filters(self, *filters) -> Dict:
        """Combine multiple JsonLogic filters with AND, returning full note object on match"""
        valid_filters = [f for f in filters if f is not None]

        if not valid_filters:
            # Match all - return full object
            return {"var": ""}

        if len(valid_filters) == 1:
            condition = valid_filters[0]
        else:
            condition = {"and": valid_filters}

        # Wrap in if to return full note object when condition matches
        return {
            "if": [
                condition,
                {"var": ""},  # Return full note object on match
                None          # Return null (falsy) on no match
            ]
        }

    def _make_obsidian_request(self, endpoint: str, method: str = "GET", data: dict = {}):
        """Make a request to the Obsidian REST API, ignoring SSL verification"""
        url = f"{self.base_url}{endpoint}"
        response = super()._make_request(method, url, json=data, verify=False)
        return self._parse_response(response)

    def get_old_notes(self, days: int, limit: int = 0) -> List[Note]:
        """Get notes older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_ms = int(cutoff_date.timestamp() * 1000)

        query = self._combine_filters(
            {"<": [{"var": "stat.mtime"}, cutoff_ms]},
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(CONFIG.search_folders),
            self._build_excluded_tags_filter()
        )

        results = self.search(query)

        if limit and len(results) > limit:
            return results[:limit]

        return results

    def get_tagged_notes(self, tags: List[str], exclude_recent_days: int = 0) -> List[Note]:
        """Get notes with specific tags"""
        # At least one of the tags should be present
        tag_filter = {
            "or": [
                {"in": [tag, {"var": "tags"}]}
                for tag in tags
            ]
        }

        filters: List[Optional[Dict]] = [tag_filter]

        if exclude_recent_days > 0:
            cutoff_date = datetime.now() - timedelta(days=exclude_recent_days)
            cutoff_ms = int(cutoff_date.timestamp() * 1000)
            filters.append({"<": [{"var": "stat.mtime"}, cutoff_ms]})

        filters.append(self._build_folder_filter(CONFIG.search_folders))
        filters.append(self._build_excluded_tags_filter())

        query = self._combine_filters(*filters)
        return self.search(query)

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        import urllib.parse
        encoded_path = urllib.parse.quote(note_path, safe='/')
        response = self._make_obsidian_request(f"/vault/{encoded_path}")
        return response if isinstance(response, str) else response.get("content", "")

    def sample_old_notes(self, days: int, limit: int = 0, bias_strength: float = 0.0, search_folders: List[str] = []) -> List[Note]:
        """Sample old notes with optional weighting"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_ms = int(cutoff_date.timestamp() * 1000)

        query = self._combine_filters(
            {"<": [{"var": "stat.mtime"}, cutoff_ms]},
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter()
        )

        all_notes = self.search(query)

        if not all_notes:
            return []

        all_notes = [note for note in all_notes if not CONFIG.is_note_hidden(note.path)]

        if not all_notes:
            return []

        if not limit or len(all_notes) <= limit:
            return all_notes

        return self._weighted_sample(all_notes, limit, bias_strength)

    def _weighted_sample(self, notes: List[Note], limit: int, bias_strength: float = 0.0) -> List[Note]:
        """Perform weighted sampling based on note tags and processing history"""
        import random

        weights = []
        for note in notes:
            weight = note.get_sampling_weight(bias_strength)
            weights.append(weight)

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

    def find_by_pattern(self, pattern: str, sample_size: int = 0, bias_strength: float = 0.0, search_folders: List[str] = []) -> List[Note]:
        """Find notes by pattern"""
        # Build pattern condition using glob
        if pattern.endswith('/*'):
            # Directory pattern: frontend/*
            directory_path = pattern[:-2]
            pattern_filter = {"glob": [f"{directory_path}/*", {"var": "path"}]}
        elif '*' in pattern:
            # Glob pattern - convert to glob syntax
            # Handle patterns like "react*", "*hooks", "react*hooks"
            glob_pattern = pattern if pattern.endswith('*') or pattern.startswith('*') else f"*{pattern}*"
            pattern_filter = {"glob": [glob_pattern, {"var": "path"}]}
        else:
            # Exact match or name contains
            pattern_filter = {"glob": [f"*{pattern}*", {"var": "path"}]}

        query = self._combine_filters(
            pattern_filter,
            {">": [{"var": "stat.size"}, 100]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter()
        )

        results = self.search(query)

        if not results:
            return []

        results = [note for note in results if not CONFIG.is_note_hidden(note.path)]

        if not results:
            return []

        if not sample_size or len(results) <= sample_size:
            return results

        if CONFIG.sampling_mode == "weighted":
            return self._weighted_sample(results, sample_size, bias_strength)
        else:
            import random
            return random.sample(results, sample_size)

    def find_by_name(self, note_name: str, search_folders: List[str]) -> Note | None:
        """Find note by name with partial matching"""
        query = self._combine_filters(
            {"glob": [f"*{note_name}*", {"var": "path"}]},
            self._build_folder_filter(search_folders),
            self._build_excluded_tags_filter()
        )

        results = self.search(query)

        if not results:
            return None

        if len(results) == 1:
            return results[0]
        else:
            # Find exact match first, otherwise return first partial match
            for note in results:
                filename = note.filename.lower()
                if filename == note_name.lower() or filename == f"{note_name.lower()}.md":
                    return note
            return results[0]

    def test_connection(self) -> bool:
        """Test if the connection to Obsidian API is working"""
        try:
            self._make_obsidian_request("/")
            return True
        except Exception:
            return False
