import requests
import os
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict

from cli.config import console

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ObsidianAPI:
    def __init__(self):
        self.base_url = "https://127.0.0.1:27124"
        self.api_key = os.getenv("OBSIDIAN_API_KEY")

        if not self.api_key:
            raise ValueError("OBSIDIAN_API_KEY not found in environment variables")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _build_folder_filter(self, search_folders) -> str:
        """Build DQL folder filter condition based on search_folders"""
        if search_folders is None or len(search_folders) == 0:
            return ""

        folder_conditions = []
        for folder in search_folders:
            folder_conditions.append(f'startswith(file.path, "{folder}/")')

        return f"AND ({' OR '.join(folder_conditions)})"

    def _build_exclude_filter(self, config_manager) -> str:
        """Build DQL exclude filter condition based on excluded tags"""
        if not config_manager or not hasattr(config_manager, 'excluded_tags'):
            return ""

        excluded_tags = config_manager.excluded_tags
        if not excluded_tags:
            return ""

        exclude_conditions = []
        for tag in excluded_tags:
            exclude_conditions.append(f'!contains(file.tags, "{tag}")')

        return f"AND ({' AND '.join(exclude_conditions)})"

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None):
        """Make a request to the Obsidian REST API, ignoring SSL verification"""
        response = requests.request(
            method=method,
            url=f"{self.base_url}{endpoint}",
            headers=self.headers,
            json=data,
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text

    def search_with_dql(self, query: str) -> List[Dict]:
        """Search notes using Dataview DQL query"""
        headers = {
            **self.headers,
            "Content-Type": "application/vnd.olrapi.dataview.dql+txt"
        }

        try:
            response = requests.post(
                f"{self.base_url}/search/",
                headers=headers,
                data=query,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]ERROR:[/red] Error executing DQL query: {e}")
            raise

    def get_notes_older_than(self, days: int, limit: int = None, config_manager=None) -> List[Dict]:
        """Get notes that haven't been modified in the specified number of days using DQL"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        from cli.config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)
        exclude_filter = self._build_exclude_filter(config_manager)

        dql_query = f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.size AS "size"
            FROM ""
            WHERE file.mtime < date("{cutoff_str}")
            {folder_filter}
            {exclude_filter}
            SORT file.mtime ASC"""

        if limit:
            dql_query += f"\nLIMIT {limit}"

        return self.search_with_dql(dql_query)

    def get_notes_by_tags(self, tags: List[str], exclude_recent_days: int = 0, config_manager=None) -> List[Dict]:
        """Get notes that contain specific tags, optionally excluding recently modified ones"""
        tag_conditions = " OR ".join([f'contains(file.tags, "{tag}")' for tag in tags])
        from cli.config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)
        exclude_filter = self._build_exclude_filter(config_manager)

        dql_query = f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.tags AS "tags"
            FROM ""
            WHERE ({tag_conditions})"""

        if exclude_recent_days > 0:
            cutoff_date = datetime.now() - timedelta(days=exclude_recent_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            dql_query += f'\nAND file.mtime < date("{cutoff_str}")'

        if folder_filter:
            dql_query += f"\n{folder_filter}"

        if exclude_filter:
            dql_query += f"\n{exclude_filter}"

        dql_query += "\nSORT file.mtime ASC"

        return self.search_with_dql(dql_query)

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        import urllib.parse
        encoded_path = urllib.parse.quote(note_path, safe='/')
        response = self._make_request(f"/vault/{encoded_path}")
        return response if isinstance(response, str) else response.get("content", "")

    def get_random_old_notes(self, days: int, limit: int = None, config_manager=None, bias_strength: float = None) -> List[Dict]:
        """Get a random sample of notes older than specified days, optionally weighted by tags"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        from cli.config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)

        # Get notes with tags for weighted sampling
        exclude_filter = self._build_exclude_filter(config_manager)

        dql_query = f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.size AS "size",
            file.tags AS "tags"
            FROM ""
            WHERE file.mtime < date("{cutoff_str}")
            AND file.size > 100
            {folder_filter}
            {exclude_filter}
            SORT file.mtime ASC"""

        all_old_notes = self.search_with_dql(dql_query)

        if not all_old_notes:
            return []

        if not limit or len(all_old_notes) <= limit:
            return all_old_notes

        # Weighted sampling if config_manager provided
        if config_manager:
            return self._weighted_sample(all_old_notes, limit, config_manager, bias_strength)

        import random
        return random.sample(all_old_notes, limit)

    def _weighted_sample(self, notes: List[Dict], limit: int, config_manager, bias_strength: float = None) -> List[Dict]:
        """Perform weighted sampling based on note tags and processing history"""
        import random
        from cli.config import get_sampling_weight_for_note

        # Calculate weights for each note
        weights = []
        for note in notes:
            note_tags = note['result'].get('tags', []) or []
            note_path = note['result'].get('path', '')
            note_size = note['result'].get('size', 0)

            weight = get_sampling_weight_for_note(note_tags, note_path, note_size, config_manager, bias_strength)
            weights.append(weight)

        # Weighted random selection
        return random.choices(notes, weights=weights, k=limit)

    def find_notes_by_pattern(self, pattern: str, config_manager=None, sample_size: int = None, bias_strength: float = None) -> List[Dict]:
        """Find notes by directory pattern"""
        exclude_filter = self._build_exclude_filter(config_manager)

        # Handle directory patterns ending with /*
        if pattern.endswith('/*'):
            directory_path = pattern[:-2]  # Remove /*
            dql_query = f"""TABLE
                file.name AS "filename",
                file.path AS "path",
                file.mtime AS "mtime",
                file.size AS "size",
                file.tags AS "tags"
                FROM ""
                WHERE startswith(file.path, "{directory_path}/")
                AND file.size > 100
                {exclude_filter}
                SORT file.mtime ASC"""
        else:
            # Handle wildcards in filenames
            if '*' in pattern:
                # Convert simple glob pattern to DQL contains/startswith
                if pattern.startswith('*'):
                    search_term = pattern[1:]
                    condition = f'endswith(file.path, "{search_term}")'
                elif pattern.endswith('*'):
                    search_term = pattern[:-1]
                    condition = f'startswith(file.path, "{search_term}")'
                else:
                    # Middle wildcard - use contains
                    parts = pattern.split('*')
                    conditions = []
                    for part in parts:
                        if part:
                            conditions.append(f'contains(file.path, "{part}")')
                    condition = ' AND '.join(conditions) if conditions else 'true'
            else:
                # No wildcards - treat as exact path or name match
                condition = f'(file.path = "{pattern}" OR contains(file.name, "{pattern}"))'

            dql_query = f"""TABLE
                file.name AS "filename",
                file.path AS "path",
                file.mtime AS "mtime",
                file.size AS "size",
                file.tags AS "tags"
                FROM ""
                WHERE {condition}
                AND file.size > 100
                {exclude_filter}
                SORT file.mtime ASC"""

        results = self.search_with_dql(dql_query)

        if not results:
            return []

        # Apply sampling if requested and we have more results than sample_size
        if sample_size and len(results) > sample_size:
            if config_manager:
                return self._weighted_sample(results, sample_size, config_manager, bias_strength)
            else:
                import random
                return random.sample(results, sample_size)

        return results

    def find_note_by_name(self, note_name: str, config_manager=None) -> Dict:
        """Find a specific note by name (partial match)"""
        from cli.config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)
        exclude_filter = self._build_exclude_filter(config_manager)

        dql_query = f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.size AS "size",
            file.tags AS "tags"
            FROM ""
            WHERE contains(file.name, "{note_name}")
            {folder_filter}
            {exclude_filter}
            SORT file.name ASC"""

        results = self.search_with_dql(dql_query)

        if not results:
            return None
        elif len(results) == 1:
            return results[0]
        else:
            # Multiple matches - find exact match first, otherwise return first partial match
            for note in results:
                if note['result']['filename'].lower() == note_name.lower():
                    return note
                if note['result']['filename'].lower() == f"{note_name.lower()}.md":
                    return note
            return results[0]  # Return first partial match

    def test_connection(self) -> bool:
        """Test if the connection to Obsidian API is working"""
        try:
            self._make_request("/")
            return True
        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to connect to Obsidian API: {e}")
            return False

