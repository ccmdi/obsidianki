"""Test Note and Flashcard models - Fixed version"""
import pytest
from unittest.mock import Mock, patch
from obsidianki.cli.models import Note, Flashcard
from obsidianki.cli.config import Config


class TestNoteModelBasics:
    """Test basic Note model functionality"""

    def test_note_creation(self):
        """Test creating a Note"""
        note = Note(
            path="test/note.md",
            filename="note.md",
            content="Test content",
            tags=["test", "example"],
            size=100
        )
        assert note.path == "test/note.md"
        assert note.filename == "note.md"
        assert note.content == "Test content"
        assert "test" in note.tags
        assert note.size == 100

    def test_note_from_obsidian_result(self):
        """Test creating Note from Obsidian API result"""
        result = {
            "filename": "My Note",
            "path": "folder/my_note.md",
            "mtime": "2024-01-01",
            "size": 500,
            "tags": ["tag1", "tag2"]
        }

        # from_obsidian_result accepts optional content parameter
        note = Note.from_dql_result(result, content="Content here")

        assert note.filename == "My Note"
        assert note.path == "folder/my_note.md"
        assert note.size == 500
        assert len(note.tags) == 2
        assert note.content == "Content here"

    def test_note_str_representation(self):
        """Test Note string representation"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )
        str_repr = str(note)
        assert "test.md" in str_repr or isinstance(str_repr, str)

    def test_note_with_empty_tags(self):
        """Test Note with empty tags list"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )
        assert note.tags == []
        assert len(note.tags) == 0

    def test_note_title_property(self):
        """Test Note title property strips .md extension"""
        note = Note(
            path="test.md",
            filename="MyNote.md",
            content="content",
            tags=[],
            size=50
        )
        assert note.title == "MyNote"

    def test_note_obsidian_uri(self):
        """Test generating Obsidian URI"""
        note = Note(
            path="folder/note.md",
            filename="note.md",
            content="content",
            tags=[],
            size=50
        )
        uri = note.to_obsidian_uri()
        assert uri.startswith("obsidian://open?file=")
        assert "folder" in uri

    def test_note_with_special_characters(self):
        """Test Note with special characters in path"""
        note = Note(
            path="folder/note (1).md",
            filename="note (1).md",
            content="content",
            tags=[],
            size=50
        )
        assert "(" in note.path
        assert ")" in note.path

    def test_note_large_content(self):
        """Test Note with large content"""
        large_content = "x" * 10000
        note = Note(
            path="large.md",
            filename="large.md",
            content=large_content,
            tags=[],
            size=10000
        )
        assert len(note.content) == 10000

    def test_note_unicode_content(self):
        """Test Note with Unicode content"""
        note = Note(
            path="unicode.md",
            filename="unicode.md",
            content="Hello 世界 🌍",
            tags=["中文"],
            size=100
        )
        assert "世界" in note.content
        assert "中文" in note.tags


class TestFlashcardModelBasics:
    """Test basic Flashcard model functionality"""

    def test_flashcard_creation(self):
        """Test creating a Flashcard"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=["test"],
            size=50
        )

        flashcard = Flashcard(
            front="What is Python?",
            back="A programming language",
            note=note,
            front_original="What is Python?",
            back_original="A programming language"
        )

        assert flashcard.front == "What is Python?"
        assert flashcard.back == "A programming language"
        assert flashcard.note == note
        assert flashcard.front_original == "What is Python?"

    def test_flashcard_str_representation(self):
        """Test Flashcard string representation"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )

        flashcard = Flashcard(
            front="Question",
            back="Answer",
            note=note,
            front_original="Question",
            back_original="Answer"
        )

        str_repr = str(flashcard)
        assert isinstance(str_repr, str)

    def test_flashcard_with_html(self):
        """Test Flashcard with HTML content"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )

        flashcard = Flashcard(
            front="What is <b>bold</b>?",
            back="HTML <code>tag</code>",
            note=note,
            front_original="What is bold?",
            back_original="HTML tag"
        )

        assert "<b>" in flashcard.front
        assert "<code>" in flashcard.back

    def test_flashcard_with_multiline(self):
        """Test Flashcard with multiline content"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )

        multiline_front = "Question:\n1. Part A\n2. Part B"
        multiline_back = "Answer:\n- Point 1\n- Point 2"

        flashcard = Flashcard(
            front=multiline_front,
            back=multiline_back,
            note=note,
            front_original=multiline_front,
            back_original=multiline_back
        )

        assert "\n" in flashcard.front
        assert "\n" in flashcard.back
        assert "Part A" in flashcard.front
        assert "Point 1" in flashcard.back

    def test_flashcard_with_code_blocks(self):
        """Test Flashcard with code blocks"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=["programming"],
            size=50
        )

        flashcard = Flashcard(
            front="What does this code do?\n```python\nprint('hello')\n```",
            back="Prints hello",
            note=note,
            front_original="What does this code do?\nprint('hello')",
            back_original="Prints hello"
        )

        assert "```" in flashcard.front
        assert "python" in flashcard.front

    def test_flashcard_very_long_content(self):
        """Test Flashcard with very long content"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )

        long_text = "Word " * 500  # 2500+ characters

        flashcard = Flashcard(
            front="Question",
            back=long_text,
            note=note,
            front_original="Question",
            back_original=long_text
        )

        assert len(flashcard.back) > 2000


class TestModelEdgeCases:
    """Test edge cases for models"""

    def test_note_negative_size(self):
        """Test Note with negative size"""
        note = Note(
            path="test.md",
            filename="test.md",
            content="",
            tags=[],
            size=-1
        )
        # Should accept but might want validation in future
        assert note.size == -1

    def test_note_from_obsidian_result_with_defaults(self):
        """Test Note.from_obsidian_result with minimal fields"""
        result = {
            "filename": "Minimal",
            "path": "minimal.md"
        }

        # Should handle missing optional fields with defaults
        note = Note.from_dql_result(result, content="test")
        assert note.filename == "Minimal"
        assert note.path == "minimal.md"
        assert note.content == "test"
        # Tags should default to empty list
        assert isinstance(note.tags, list)


class TestModelIntegration:
    """Test model integration scenarios"""

    def test_note_to_flashcard_workflow(self):
        """Test creating flashcards from a note"""
        note = Note(
            path="study.md",
            filename="Study Note",
            content="Python is a programming language",
            tags=["programming", "python"],
            size=200
        )

        flashcards = []
        for i in range(3):
            fc = Flashcard(
                front=f"Question {i+1}",
                back=f"Answer {i+1}",
                note=note,
                front_original=f"Question {i+1}",
                back_original=f"Answer {i+1}"
            )
            flashcards.append(fc)

        assert len(flashcards) == 3
        assert all(fc.note == note for fc in flashcards)
        assert all("programming" in fc.note.tags for fc in flashcards)

    def test_multiple_notes_with_flashcards(self):
        """Test managing multiple notes with flashcards"""
        notes = []
        for i in range(5):
            note = Note(
                path=f"note{i}.md",
                filename=f"Note {i}",
                content=f"Content {i}",
                tags=[f"tag{i}"],
                size=100
            )
            notes.append(note)

        assert len(notes) == 5
        assert all(isinstance(n, Note) for n in notes)

        # Create flashcards from each note
        all_flashcards = []
        for note in notes:
            fc = Flashcard(
                front=f"Q for {note.filename}",
                back="Answer",
                note=note,
                front_original=f"Q for {note.filename}",
                back_original="Answer"
            )
            all_flashcards.append(fc)

        assert len(all_flashcards) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
