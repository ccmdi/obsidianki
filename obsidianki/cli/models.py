"""
Clean data models for ObsidianKi to replace scattered dictionaries and parameter hell.
"""

from typing import List, Optional, Dict, Any, Iterator
from dataclasses import dataclass
from obsidianki.cli.config import CONFIG


@dataclass
class Note:
    """A clean representation of an Obsidian note with all its metadata."""

    path: str
    filename: str
    content: str
    tags: List[str]
    size: int

    def __post_init__(self):
        # Ensure we have clean data
        if not self.tags:
            self.tags = []

    @property
    def title(self) -> str:
        """Clean title without file extension."""
        return self.filename.rsplit('.md', 1)[0] if self.filename.endswith('.md') else self.filename

    def get_sampling_weight(self, bias_strength: float = 0.0) -> float:
        """Calculate total sampling weight based on tags and processing history."""
        return CONFIG.get_sampling_weight_for_note_object(self, bias_strength)

    def get_density_bias(self, bias_strength: float = 0.0) -> float:
        """Get density bias factor for this note."""
        return CONFIG.get_density_bias_for_note(self, bias_strength)

    def is_excluded(self) -> bool:
        """Check if this note should be excluded based on its tags."""
        return CONFIG.is_note_excluded(self)

    def has_processing_history(self) -> bool:
        """Check if this note has been processed before."""
        return self.path in CONFIG.processing_history

    def get_previous_flashcard_fronts(self) -> List[str]:
        """Get all previously created flashcard fronts for deduplication."""
        return CONFIG.get_flashcard_fronts_for_note(self)

    def ensure_content(self):
        """Ensure the note content is loaded."""
        from obsidianki.cli.services import OBSIDIAN
        if not self.content:
            self.content = OBSIDIAN.get_note_content(self.path)

    def to_obsidian_uri(self) -> str:
        """Generate Obsidian URI: obsidian://open?file=<encoded_path>"""
        import urllib.parse
        encoded_path = urllib.parse.quote(self.path, safe='')
        return f"obsidian://open?file={encoded_path}"

    def to_obsidian_link_html(self) -> str:
        """Generate HTML anchor tag: <a href='obsidian://...'>title</a>"""
        return f"<a href='{self.to_obsidian_uri()}'>{self.title}</a>"

    def to_obsidian_link_rich(self) -> str:
        """Generate Rich markup link: [link=obsidian://...]path[/link]"""
        return f"[link={self.to_obsidian_uri()}]{self.path}[/link]"

    @classmethod
    def from_obsidian_result(cls, obsidian_result: Dict[str, Any], content: str = "") -> 'Note':
        """Create Note from Obsidian API result format."""
        result = obsidian_result.get('result', obsidian_result)
        return cls(
            path=result['path'],
            filename=result['filename'],
            content=content or "",
            tags=result.get('tags', []),
            size=result.get('size', 0)
        )


class NotePattern:
    """
    A pattern matcher for notes that can be directly iterated to get matching notes.

    Handles various pattern formats:
    - Simple count: "5" -> sample 5 notes
    - Exact name: "React" -> find notes matching "React"
    - Wildcard patterns: "docs/*", "*React*", etc.
    - Patterns with sampling: "docs/*:5" -> sample 5 notes from pattern

    Usage:
        pattern = NotePattern("docs/*:5")
        notes = list(pattern)  # Get matching notes

        # Or iterate directly:
        for note in NotePattern("docs/*"):
            print(note.filename)
    """

    def __init__(self, pattern: str, bias_strength: float = 0.0, search_folders: List[str] = []):
        """
        Initialize a note pattern.

        Args:
            pattern: Pattern string (e.g., "5", "React", "docs/*", "docs/*:5")
            bias_strength: Density bias strength for sampling (0.0-1.0)
            search_folders: Folders to search in (defaults to CONFIG.search_folders)
        """
        self.original_pattern = pattern
        self.bias_strength = bias_strength
        self.search_folders = search_folders or (CONFIG.search_folders if CONFIG else [])

        # Parse the pattern
        self.pattern = pattern
        self.sample_size = 0

        # Check if pattern has sampling suffix (e.g., "docs/*:5")
        if ':' in pattern and not pattern.endswith('/'):
            parts = pattern.rsplit(':', 1)
            if parts[1].isdigit():
                self.pattern = parts[0]
                self.sample_size = int(parts[1])

        # Determine pattern type
        self.is_count = self.pattern.isdigit()
        self.is_wildcard = '*' in self.pattern or '/' in self.pattern

    def __iter__(self) -> Iterator[Note]:
        """Make NotePattern directly iterable."""
        return iter(self.resolve())

    def resolve(self) -> List[Note]:
        """
        Resolve the pattern to a list of notes.

        Returns:
            List[Note]: List of notes matching the pattern
        """
        from obsidianki.cli.services import OBSIDIAN

        if self.is_count:
            # Simple count pattern: sample N random notes
            count = int(self.pattern)
            return OBSIDIAN.sample_old_notes(
                days=CONFIG.days_old if CONFIG else 7,
                limit=count,
                bias_strength=self.bias_strength,
                search_folders=self.search_folders
            )
        elif self.is_wildcard:
            # Wildcard pattern matching
            return OBSIDIAN.find_by_pattern(
                self.pattern,
                sample_size=self.sample_size,
                bias_strength=self.bias_strength,
                search_folders=self.search_folders
            )
        else:
            # Exact name matching
            note = OBSIDIAN.find_by_name(self.pattern, search_folders=self.search_folders)
            return [note] if note else []

    def __repr__(self) -> str:
        return f"NotePattern('{self.original_pattern}')"


@dataclass
class Flashcard:
    """A clean representation of a flashcard with its metadata."""

    front: str
    back: str
    note: Note
    tags: Optional[List[str]] = None
    front_original: Optional[str] = None
    back_original: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = self.note.tags.copy()

    @property
    def source_path(self) -> str:
        """Path to the source note."""
        return self.note.path

    @property
    def source_title(self) -> str:
        """Title of the source note."""
        return self.note.title

    def get_clean_front(self) -> str:
        """Get HTML-stripped front text (uses front_original if available)"""
        if self.front_original:
            return self.front_original
        from obsidianki.cli.utils import strip_html
        return strip_html(self.front)

    def get_clean_back(self) -> str:
        """Get HTML-stripped back text (uses back_original if available)"""
        if self.back_original:
            return self.back_original
        from obsidianki.cli.utils import strip_html
        return strip_html(self.back)

    def ensure_clean_originals(self) -> None:
        """Populate front_original and back_original with HTML-stripped versions"""
        if not self.front_original:
            from obsidianki.cli.utils import strip_html
            self.front_original = strip_html(self.front)
        if not self.back_original:
            from obsidianki.cli.utils import strip_html
            self.back_original = strip_html(self.back)

    @classmethod
    def from_ai_response(cls, ai_flashcard: Dict[str, Any], note: Note) -> 'Flashcard':
        """Create Flashcard from AI-generated flashcard dict."""
        return cls(
            front=ai_flashcard.get('front', ''),
            back=ai_flashcard.get('back', ''),
            note=note,
            tags=ai_flashcard.get('tags', note.tags.copy()),
            front_original=ai_flashcard.get('front_original'),
            back_original=ai_flashcard.get('back_original')
        )