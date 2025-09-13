import requests
import os
from dotenv import load_dotenv
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

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
            print(f"Error executing DQL query: {e}")
            raise

    def get_notes_older_than(self, days: int, limit: int = None) -> List[Dict]:
        """Get notes that haven't been modified in the specified number of days using DQL"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        from config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)

        dql_query = f"""TABLE
            file.name AS "filename",
            file.path AS "path",
            file.mtime AS "mtime",
            file.size AS "size"
            FROM ""
            WHERE file.mtime < date("{cutoff_str}")
            {folder_filter}
            SORT file.mtime ASC"""

        if limit:
            dql_query += f"\nLIMIT {limit}"

        return self.search_with_dql(dql_query)

    def get_notes_by_tags(self, tags: List[str], exclude_recent_days: int = 0) -> List[Dict]:
        """Get notes that contain specific tags, optionally excluding recently modified ones"""
        tag_conditions = " OR ".join([f'contains(file.tags, "{tag}")' for tag in tags])
        from config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)

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

        dql_query += "\nSORT file.mtime ASC"

        return self.search_with_dql(dql_query)

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        import urllib.parse
        encoded_path = urllib.parse.quote(note_path, safe='/')
        response = self._make_request(f"/vault/{encoded_path}")
        return response if isinstance(response, str) else response.get("content", "")

    def get_random_old_notes(self, days: int, limit: int = None, config_manager=None) -> List[Dict]:
        """Get a random sample of notes older than specified days, optionally weighted by tags"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        from config import SEARCH_FOLDERS
        folder_filter = self._build_folder_filter(SEARCH_FOLDERS)

        # Get notes with tags for weighted sampling
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
            SORT file.mtime ASC"""

        all_old_notes = self.search_with_dql(dql_query)

        if not all_old_notes:
            return []

        if not limit or len(all_old_notes) <= limit:
            return all_old_notes

        # Weighted sampling if config_manager provided
        if config_manager:
            return self._weighted_sample(all_old_notes, limit, config_manager)
        else:
            import random
            return random.sample(all_old_notes, limit)

    def _weighted_sample(self, notes: List[Dict], limit: int, config_manager) -> List[Dict]:
        """Perform weighted sampling based on note tags and processing history"""
        import random
        from config import get_sampling_weight_for_note

        # Calculate weights for each note
        weights = []
        for note in notes:
            note_tags = note['result'].get('tags', []) or []
            note_path = note['result'].get('path', '')
            note_size = note['result'].get('size', 0)

            weight = get_sampling_weight_for_note(note_tags, note_path, note_size, config_manager)
            weights.append(weight)

        # Weighted random selection
        return random.choices(notes, weights=weights, k=limit)

    def test_connection(self) -> bool:
        """Test if the connection to Obsidian API is working"""
        try:
            self._make_request("/")
            print("✓ Successfully connected to Obsidian API")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to Obsidian API: {e}")
            return False

if __name__ == "__main__":
    try:
        obsidian = ObsidianAPI()

        if obsidian.test_connection():
            print("\n--- Testing DQL Queries ---")

            print("\n1. Getting notes older than 30 days:")
            old_notes = obsidian.get_random_old_notes(days=30)
            for note in old_notes:
                print(f"  - {note.get('filename', 'Unknown')} (modified: {note['result'].get('mtime', 'Unknown')})")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please create a .env file with OBSIDIAN_API_KEY=your_api_key")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your Obsidian REST API plugin is running on https://127.0.0.1:27124")