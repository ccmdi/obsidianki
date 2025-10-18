import os
import urllib3
from datetime import datetime, timedelta
from typing import List

from obsidianki.cli.config import console, CONFIG
from obsidianki.cli.models import Note
from obsidianki.api.base import BaseAPI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

    def _build_filters(self, search_folders=None) -> str:
        """Build combined DQL filter conditions"""
        filters = []

        # Folder filter
        if search_folders:
            folder_conditions = [f'startswith(file.path, "{folder}/")' for folder in search_folders]
            filters.append(f"({' OR '.join(folder_conditions)})")

        # Excluded tags filter
        if CONFIG and CONFIG.excluded_tags:
            exclude_conditions = [f'!contains(file.tags, "{tag}")' for tag in CONFIG.excluded_tags]
            filters.append(f"({' AND '.join(exclude_conditions)})")

        return f"AND {' AND '.join(filters)}" if filters else ""

    def _build_base_query(self, extra_conditions="", sort_field="file.mtime", sort_order="ASC") -> str:
        """Build standard DQL query structure"""
        return f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.size AS "size",
            file.tags AS "tags"
            FROM ""
            WHERE {extra_conditions}
            SORT {sort_field} {sort_order}"""

    def _make_obsidian_request(self, endpoint: str, method: str = "GET", data: dict = {}):
        """Make a request to the Obsidian REST API, ignoring SSL verification"""
        url = f"{self.base_url}{endpoint}"
        response = super()._make_request(method, url, json=data, verify=False)
        return self._parse_response(response)

    def dql(self, query: str) -> List[Note]:
        """Search notes using Dataview DQL query - returns Note objects"""
        headers = {
            **self.headers,
            "Content-Type": "application/vnd.olrapi.dataview.dql+txt"
        }

        try:
            url = f"{self.base_url}/search/"
            response = super()._make_request("POST", url, headers=headers, data=query, verify=False)
            dict_results = self._parse_response(response)

            return [Note.from_obsidian_result(result) for result in dict_results]
        except Exception as e:
            raise

    def get_old_notes(self, days: int, limit: int = 0) -> List[Note]:
        """Get notes older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        filters = self._build_filters(CONFIG.search_folders)

        condition = f'file.mtime < date("{cutoff_str}") {filters}'
        query = self._build_base_query(condition)

        if limit:
            query += f"\nLIMIT {limit}"

        return self.dql(query)

    def get_tagged_notes(self, tags: List[str], exclude_recent_days: int = 0) -> List[Note]:
        """Get notes with specific tags"""
        tag_conditions = " OR ".join([f'contains(file.tags, "{tag}")' for tag in tags])
        filters = self._build_filters(CONFIG.search_folders)

        condition = f'({tag_conditions})'

        if exclude_recent_days > 0:
            cutoff_date = datetime.now() - timedelta(days=exclude_recent_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            condition += f' AND file.mtime < date("{cutoff_str}")'

        condition += f' {filters}'

        return self.dql(self._build_base_query(condition))

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        import urllib.parse
        encoded_path = urllib.parse.quote(note_path, safe='/')
        response = self._make_obsidian_request(f"/vault/{encoded_path}")
        return response if isinstance(response, str) else response.get("content", "")

    def sample_old_notes(self, days: int, limit: int = 0, bias_strength: float = 0.0, search_folders: List[str] = []) -> List[Note]:
        """Sample old notes with optional weighting"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        filters = self._build_filters(search_folders)

        condition = f'file.mtime < date("{cutoff_str}") AND file.size > 100 {filters}'
        all_notes = self.dql(self._build_base_query(condition))

        if not all_notes:
            return []

        all_notes = [note for note in all_notes if not CONFIG.is_note_hidden(note.path)]

        if not all_notes:
            return []

        if not limit or len(all_notes) <= limit:
            return all_notes

        # Use weighted sampling by default (since we have global config)
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
        filters = self._build_filters(search_folders)

        # Build pattern condition
        if pattern.endswith('/*'):
            directory_path = pattern[:-2]
            condition = f'startswith(file.path, "{directory_path}/")'
        elif '*' in pattern:
            if pattern.startswith('*'):
                condition = f'endswith(file.path, "{pattern[1:]}")'
            elif pattern.endswith('*'):
                condition = f'startswith(file.path, "{pattern[:-1]}")'
            else:
                parts = [f'contains(file.path, "{part}")' for part in pattern.split('*') if part]
                condition = ' AND '.join(parts) if parts else 'true'
        else:
            condition = f'(file.path = "{pattern}" OR contains(file.name, "{pattern}"))'

        full_condition = f'{condition} AND file.size > 100 {filters}'
        results = self.dql(self._build_base_query(full_condition))

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
        filters = self._build_filters(search_folders)

        condition = f'contains(file.name, "{note_name}") {filters}'
        results = self.dql(self._build_base_query(condition, sort_field="file.name"))

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

