"""
Clean data models for ObsidianKi to replace scattered dictionaries and parameter hell.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from cli.config import CONFIG_MANAGER


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

    def get_sampling_weight(self, bias_strength: float = None) -> float:
        """Calculate total sampling weight based on tags and processing history."""
        return CONFIG_MANAGER.get_sampling_weight_for_note_object(self, bias_strength)

    def get_density_bias(self, bias_strength: float = None) -> float:
        """Get density bias factor for this note."""
        return CONFIG_MANAGER.get_density_bias_for_note(self, bias_strength)

    def is_excluded(self) -> bool:
        """Check if this note should be excluded based on its tags."""
        return CONFIG_MANAGER.is_note_excluded(self)

    def has_processing_history(self) -> bool:
        """Check if this note has been processed before."""
        return self.path in CONFIG_MANAGER.processing_history

    def get_previous_flashcard_fronts(self) -> List[str]:
        """Get all previously created flashcard fronts for deduplication."""
        return CONFIG_MANAGER.get_flashcard_fronts_for_note(self)

    def ensure_content(self):
        """Ensure the note content is loaded."""
        from cli.services import OBSIDIAN
        if not self.content:
            self.content = OBSIDIAN.get_note_content(self.path)

    @classmethod
    def from_obsidian_result(cls, obsidian_result: Dict[str, Any], content: str = None) -> 'Note':
        """Create Note from Obsidian API result format."""
        result = obsidian_result.get('result', obsidian_result)
        return cls(
            path=result['path'],
            filename=result['filename'],
            content=content or "",
            tags=result.get('tags', []),
            size=result.get('size', 0)
        )


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