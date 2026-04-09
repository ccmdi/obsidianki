import os
from urllib3.exceptions import InsecureRequestWarning
import urllib3
from typing import List, Dict, Any

from obsidianki.cli.config import CONFIG
from obsidianki.cli.models import Note
from obsidianki.api.base import BaseAPI
from obsidianki.api.obsidian_ops import ObsidianVaultOpsMixin

urllib3.disable_warnings(InsecureRequestWarning)

OBSIDIAN_TIMEOUT_LENGTH = 30


class ObsidianAPI(ObsidianVaultOpsMixin, BaseAPI):
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
        except Exception:
            raise

    def _make_obsidian_request(self, endpoint: str, method: str = "GET", data: dict = {}):
        """Make a request to the Obsidian REST API, ignoring SSL verification"""
        url = f"{self.base_url}{endpoint}"
        response = super()._make_request(method, url, json=data, verify=False)
        return self._parse_response(response)

    def get_note_content(self, note_path: str) -> str:
        """Get the content of a specific note"""
        import urllib.parse
        encoded_path = urllib.parse.quote(note_path, safe='/')
        response = self._make_obsidian_request(f"/vault/{encoded_path}")
        return response if isinstance(response, str) else response.get("content", "")

    def test_connection(self) -> bool:
        """Test if the connection to Obsidian API is working"""
        try:
            self._make_obsidian_request("/")
            return True
        except Exception:
            return False
