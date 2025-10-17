"""Dummy Obsidian API implementation"""
from typing import List
from datetime import datetime, timedelta
from obsidianki.cli.models import Note


class DummyObsidianAPI:
    """Mock Obsidian API that returns static note data"""

    def __init__(self):
        # Pre-populate with test notes
        self.notes = [
            Note(
                path="notes/test1.md",
                filename="Test Note 1",
                content="# Test Note 1\n\nThis is a test note about Python.",
                tags=["python", "programming"],
                size=200
            ),
            Note(
                path="notes/test2.md",
                filename="Test Note 2",
                content="# Test Note 2\n\nThis is a test note about JavaScript.",
                tags=["javascript", "programming"],
                size=250
            ),
            Note(
                path="notes/test3.md",
                filename="Test Note 3",
                content="# Test Note 3\n\nThis is a test note about databases.",
                tags=["database", "sql"],
                size=180
            ),
        ]

    def test_connection(self) -> bool:
        """Always return success"""
        return True

    def sample_old_notes(
        self, days: int, limit: int = None, bias_strength: float = None, search_folders: List[str] = None
    ) -> List[Note]:
        """Return sample notes"""
        filtered = self.notes
        if limit:
            filtered = filtered[:limit]
        return filtered

    def get_old_notes(self, days: int, limit: int = None) -> List[Note]:
        """Return old notes"""
        return self.notes[:limit] if limit else self.notes

    def get_tagged_notes(self, tags: List[str], exclude_recent_days: int = 0) -> List[Note]:
        """Return notes with matching tags"""
        return [n for n in self.notes if any(tag in n.tags for tag in tags)]

    def get_note_content(self, note_path: str) -> str:
        """Return content for a note"""
        for note in self.notes:
            if note.path == note_path:
                return note.content
        return "# Mock Note\n\nThis is mock content."

    def find_by_name(self, note_name: str, search_folders: List[str] = None) -> Note:
        """Find note by name"""
        for note in self.notes:
            if note_name.lower() in note.filename.lower():
                return note
        return None

    def find_by_pattern(
        self, pattern: str, sample_size: int = None, bias_strength: float = None, search_folders: List[str] = None
    ) -> List[Note]:
        """Find notes by pattern"""
        # Simple pattern matching
        matching = []
        for note in self.notes:
            if pattern.replace("*", "") in note.path or pattern.replace("*", "") in note.filename:
                matching.append(note)

        if sample_size and len(matching) > sample_size:
            return matching[:sample_size]
        return matching

    def dql(self, query: str) -> List[Note]:
        """Execute DQL query - return all notes"""
        return self.notes

    def _weighted_sample(self, notes: List[Note], limit: int, bias_strength: float = None) -> List[Note]:
        """Simple sampling"""
        return notes[:limit]
