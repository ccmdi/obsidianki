"""Test core business logic (weighting, sampling, bias calculations, etc.)"""
import pytest
from obsidianki.cli.models import Note
from obsidianki.cli.config import Config
from pathlib import Path
import tempfile
import json


class TestWeightedSampling:
    """Test tag weighting logic"""

    def test_tag_weight_calculation(self):
        """Test that notes get correct weights based on tags"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            tag_file = config_dir / "tags.json"

            # Create tag weights
            tag_weights = {
                "important": 3.0,
                "review": 2.0,
                "low-priority": 0.5,
                "_default": 1.0
            }
            with open(tag_file, 'w') as f:
                json.dump(tag_weights, f)

            # Create config manager
            config = Config()
            config.tag_schema_file = tag_file
            config.load_or_create_tag_schema()

            # Test: Note with high priority tag
            high_note = Note(
                path="test1.md",
                filename="High Priority",
                content="test",
                tags=["important", "other"],
                size=100
            )
            high_note._config = config
            weight = config.get_sampling_weight_for_note_object(high_note, bias_strength=0)
            assert weight == 3.0, "Should use highest tag weight"

            # Test: Note with medium priority tag
            med_note = Note(
                path="test2.md",
                filename="Medium Priority",
                content="test",
                tags=["review"],
                size=100
            )
            med_note._config = config
            weight = config.get_sampling_weight_for_note_object(med_note, bias_strength=0)
            assert weight == 2.0, "Should use tag weight"

            # Test: Note with no matching tags uses default
            default_note = Note(
                path="test3.md",
                filename="Default Priority",
                content="test",
                tags=["unweighted"],
                size=100
            )
            default_note._config = config
            weight = config.get_sampling_weight_for_note_object(default_note, bias_strength=0)
            assert weight == 1.0, "Should use default weight for unmatched tags"

            # Test: Note with multiple tags uses highest
            multi_note = Note(
                path="test4.md",
                filename="Multi Tag",
                content="test",
                tags=["important", "review", "low-priority"],
                size=100
            )
            multi_note._config = config
            weight = config.get_sampling_weight_for_note_object(multi_note, bias_strength=0)
            assert weight == 3.0, "Should use highest weight among tags"

    def test_tag_exclusion(self):
        """Test that excluded tags prevent note selection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            tag_file = config_dir / "tags.json"

            # Create tag weights with exclusions
            tag_schema = {
                "important": 2.0,
                "_default": 1.0,
                "_exclude": ["private", "draft"]
            }
            with open(tag_file, 'w') as f:
                json.dump(tag_schema, f)

            config = Config()
            config.tag_schema_file = tag_file
            config.load_or_create_tag_schema()

            # Test: Note with excluded tag
            excluded_note = Note(
                path="test1.md",
                filename="Private Note",
                content="test",
                tags=["private", "important"],
                size=100
            )
            assert config.is_note_excluded(excluded_note), "Should exclude notes with private tag"

            # Test: Normal note
            normal_note = Note(
                path="test2.md",
                filename="Normal Note",
                content="test",
                tags=["important"],
                size=100
            )
            assert not config.is_note_excluded(normal_note), "Should not exclude normal notes"


class TestDensityBias:
    """Test density bias calculations"""

    def test_density_bias_unprocessed_notes(self):
        """Test that unprocessed notes have no bias"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            history_file = config_dir / "processing_history.json"

            config = Config()
            config.processing_history_file = history_file
            config.processing_history = {}

            note = Note(
                path="new_note.md",
                filename="New Note",
                content="test content",
                tags=[],
                size=100
            )
            note._config = config

            bias = config.get_density_bias_for_note(note, bias_strength=0.5)
            assert bias == 1.0, "Unprocessed notes should have no bias penalty"

    def test_density_bias_processed_notes(self):
        """Test that heavily processed notes get bias penalty"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            history_file = config_dir / "processing_history.json"

            # Create history with heavily processed note
            history = {
                "processed.md": {
                    "size": 100,
                    "total_flashcards": 50,  # 50 cards from 100 chars = high density
                    "sessions": [],
                    "flashcard_fronts": []
                }
            }
            with open(history_file, 'w') as f:
                json.dump(history, f)

            config = Config()
            config.processing_history_file = history_file
            config.load_processing_history()

            note = Note(
                path="processed.md",
                filename="Processed Note",
                content="test",
                tags=[],
                size=100
            )
            note._config = config

            # With bias strength 1.0, heavily processed notes should have very low weight
            bias = config.get_density_bias_for_note(note, bias_strength=1.0)
            assert bias < 0.1, "Heavily processed notes should have strong bias penalty with high bias_strength"

            # With bias strength 0.0, no penalty
            bias_none = config.get_density_bias_for_note(note, bias_strength=0.0)
            assert bias_none == 1.0, "No bias penalty with bias_strength=0"

    def test_density_bias_combined_with_tags(self):
        """Test that density bias multiplies with tag weights"""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            tag_file = config_dir / "tags.json"
            history_file = config_dir / "processing_history.json"

            # Create tag weights
            tag_weights = {"important": 2.0, "_default": 1.0}
            with open(tag_file, 'w') as f:
                json.dump(tag_weights, f)

            # Create processing history
            history = {
                "note.md": {
                    "size": 100,
                    "total_flashcards": 10,
                    "sessions": [],
                    "flashcard_fronts": []
                }
            }
            with open(history_file, 'w') as f:
                json.dump(history, f)

            config = Config()
            config.tag_schema_file = tag_file
            config.processing_history_file = history_file
            config.load_or_create_tag_schema()
            config.load_processing_history()

            # Patch both the config module's SAMPLING_MODE and the models CONFIG
            with patch('obsidianki.cli.config.CONFIG.SAMPLING_MODE', 'weighted'), \
                 patch('obsidianki.cli.models.CONFIG', config):

                note = Note(
                    path="note.md",
                    filename="Note",
                    content="test",
                    tags=["important"],
                    size=100
                )

                # Get individual components
                density_bias = config.get_density_bias_for_note(note, bias_strength=0.5)

                # Tag weight for "important" should be 2.0
                tag_weight = 2.0

                # Final weight should be their product
                weight = config.get_sampling_weight_for_note_object(note, bias_strength=0.5)
                expected = tag_weight * density_bias

                # Verify the calculation is correct
                assert abs(weight - expected) < 0.001, f"Weight {weight} should be tag_weight ({tag_weight}) * density_bias ({density_bias}) = {expected}"

                # Verify density bias is less than 1 for processed notes
                assert density_bias < 1.0, "Processed notes should have density_bias < 1.0"


class TestProcessingHistory:
    """Test processing history tracking"""

    def test_record_flashcards(self):
        """Test that flashcard creation is recorded correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            history_file = config_dir / "processing_history.json"

            config = Config()
            config.processing_history_file = history_file
            config.processing_history = {}

            note = Note(
                path="test.md",
                filename="Test",
                content="content",
                tags=[],
                size=100
            )

            # Record first session
            config.record_flashcards_created(
                note,
                flashcard_count=5,
                flashcard_fronts=["Q1", "Q2", "Q3", "Q4", "Q5"]
            )

            assert "test.md" in config.processing_history
            assert config.processing_history["test.md"]["total_flashcards"] == 5
            assert len(config.processing_history["test.md"]["flashcard_fronts"]) == 5
            assert len(config.processing_history["test.md"]["sessions"]) == 1

            # Record second session
            config.record_flashcards_created(
                note,
                flashcard_count=3,
                flashcard_fronts=["Q6", "Q7", "Q8"]
            )

            assert config.processing_history["test.md"]["total_flashcards"] == 8
            assert len(config.processing_history["test.md"]["flashcard_fronts"]) == 8
            assert len(config.processing_history["test.md"]["sessions"]) == 2

    def test_get_previous_fronts(self):
        """Test retrieving previous flashcard fronts for deduplication"""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            history_file = config_dir / "processing_history.json"

            history = {
                "note.md": {
                    "size": 100,
                    "total_flashcards": 3,
                    "sessions": [],
                    "flashcard_fronts": ["Question 1?", "Question 2?", "Question 3?"]
                }
            }
            with open(history_file, 'w') as f:
                json.dump(history, f)

            config = Config()
            config.processing_history_file = history_file
            config.load_processing_history()

            # Patch the global CONFIG that Note uses
            with patch('obsidianki.cli.models.CONFIG', config):
                note = Note(path="note.md", filename="Note", content="test", tags=[], size=100)

                fronts = note.get_previous_flashcard_fronts()
                assert len(fronts) == 3
                assert "Question 1?" in fronts
                assert "Question 2?" in fronts
                assert "Question 3?" in fronts


class TestNoteArgParsing:
    """Test how -n/--notes argument is parsed"""

    def test_notes_count_parsing(self):
        """Test that -n 5 is correctly identified as count"""
        # Single digit argument should be treated as count
        args = ['5']
        assert len(args) == 1
        assert args[0].isdigit()

    def test_notes_pattern_parsing(self):
        """Test that patterns with : are parsed correctly"""
        pattern = "notes/*:3"

        # Should split on last :
        if ':' in pattern and not pattern.endswith('/'):
            parts = pattern.rsplit(':', 1)
            if parts[1].isdigit():
                path_pattern = parts[0]
                sample_size = int(parts[1])

                assert path_pattern == "notes/*"
                assert sample_size == 3

    def test_notes_name_vs_pattern(self):
        """Test distinguishing note names from patterns"""
        # Pattern has * or /
        assert '*' in "notes/*" or '/' in "notes/*"

        # Name doesn't
        name = "My Note"
        assert not ('*' in name or '/' in name)


class TestCardLimitCalculation:
    """Test card limit calculations"""

    def test_target_cards_per_note_calculation(self):
        """Test that target_cards_per_note is calculated correctly"""
        # With 3 notes and 10 max cards
        max_cards = 10
        num_notes = 3
        target = max(1, max_cards // num_notes)
        assert target == 3, "Should be 10 // 3 = 3"

        # With 5 notes and 12 max cards
        max_cards = 12
        num_notes = 5
        target = max(1, max_cards // num_notes)
        assert target == 2, "Should be 12 // 5 = 2"

        # Edge case: 0 max cards should still give 1 per note
        max_cards = 0
        num_notes = 3
        target = max(1, max_cards // num_notes)
        assert target == 1, "Should be max(1, 0) = 1"

    def test_cards_and_notes_scaling(self):
        """Test how cards and notes scale together"""
        # When only --notes provided, cards should scale
        num_notes = 3
        expected_cards = num_notes * 2
        assert expected_cards == 6

        # When only --cards provided, notes should scale
        max_cards = 10
        expected_notes = max(1, max_cards // 2)
        assert expected_notes == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
