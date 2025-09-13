import requests
import os
from dotenv import load_dotenv
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Disable SSL warnings since we're ignoring SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Configure which folders to search in (set to None to search all folders)
SEARCH_FOLDERS = ["Research", "Life"]  # Only search in these folders, or set to None for all folders

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

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make a request to the Obsidian REST API, ignoring SSL verification"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                verify=False,  # Ignore SSL verification
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            raise

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
        # Calculate the cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        # Build DQL query to find old notes
        dql_query = f"""TABLE
  file.name AS "filename",
  file.path AS "path",
  file.mtime AS "mtime",
  file.size AS "size"
FROM ""
WHERE file.mtime < date("{cutoff_str}")
SORT file.mtime ASC"""

        if limit:
            dql_query += f"\nLIMIT {limit}"

        return self.search_with_dql(dql_query)

    def get_notes_by_tags(self, tags: List[str], exclude_recent_days: int = 0) -> List[Dict]:
        """Get notes that contain specific tags, optionally excluding recently modified ones"""
        tag_conditions = " OR ".join([f'contains(file.tags, "{tag}")' for tag in tags])

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

        dql_query += "\nSORT file.mtime ASC"

        return self.search_with_dql(dql_query)

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        response = self._make_request(f"/vault/{note_path}")
        return response.get("content", "")

    def get_random_old_notes(self, days: int, limit: int = 10) -> List[Dict]:
        """Get a random sample of notes older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        # Note: DQL doesn't have built-in random, so we'll get all old notes and sample in Python
        dql_query = f"""TABLE
  file.name AS "filename",
  file.path AS "path",
  file.mtime AS "mtime",
  file.size AS "size"
FROM ""
WHERE file.mtime < date("{cutoff_str}")
AND file.size > 100
SORT file.mtime ASC"""

        all_old_notes = self.search_with_dql(dql_query)

        # Random sampling if we have more notes than requested
        import random
        if len(all_old_notes) > limit:
            return random.sample(all_old_notes, limit)
        return all_old_notes

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
    # Test the connection and demonstrate DQL functionality
    try:
        obsidian = ObsidianAPI()

        if obsidian.test_connection():
            print("\n--- Testing DQL Queries ---")

            # Test getting old notes
            print("\n1. Getting notes older than 30 days (limit 5):")
            old_notes = obsidian.get_notes_older_than(days=30, limit=5)
            for note in old_notes[:3]:  # Show first 3
                print(f"  - {note.get('filename', 'Unknown')} (modified: {note.get('mtime', 'Unknown')})")

            # Test custom DQL query
            print("\n2. Testing custom DQL query (all notes with file info):")
            custom_query = """TABLE
  file.name AS "filename",
  file.size AS "size",
  length(file.outlinks) AS "outlinks"
FROM ""
WHERE file.size > 50
SORT file.mtime DESC
LIMIT 3"""

            results = obsidian.search_with_dql(custom_query)
            for result in results:
                print(f"  - {result.get('filename', 'Unknown')} ({result.get('size', 0)} bytes, {result.get('outlinks', 0)} links)")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please create a .env file with OBSIDIAN_API_KEY=your_api_key")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your Obsidian REST API plugin is running on https://127.0.0.1:27124")