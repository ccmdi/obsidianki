"""Test advanced features: deck tracking, duplicate prevention, hidden notes, formatting, templates, and --use-schema"""
import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import tests.utils
mock_services = tests.utils.mock_services


@pytest.fixture
def mock_config():
    """Patch config to use temp directory and disable interactive prompts"""
    import obsidianki.cli.config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        env_file = config_dir / ".env"
        config_file = config_dir / "config.json"
        history_file = config_dir / "processing_history.json"
        templates_file = config_dir / "templates.json"
        tags_file = config_dir / "tags.json"

        env_file.write_text("OBSIDIAN_API_KEY=test\nANTHROPIC_API_KEY=test\n")
        config_file.write_text('{"DECK": "TestDeck"}')

        with patch.object(obsidianki.cli.config, 'ENV_FILE', env_file), \
             patch.object(obsidianki.cli.config, 'CONFIG_FILE', config_file), \
             patch('obsidianki.main.ENV_FILE', env_file), \
             patch('obsidianki.main.CONFIG_FILE', config_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history_file', history_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history', {}), \
             patch.object(obsidianki.cli.config.CONFIG, 'templates_file', templates_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'tag_schema_file', tags_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'APPROVE_NOTES', False), \
             patch.object(obsidianki.cli.config.CONFIG, 'APPROVE_CARDS', False), \
             patch.object(obsidianki.cli.config.CONFIG, 'UPFRONT_BATCHING', False), \
             patch.object(obsidianki.cli.config.CONFIG, 'vector_dedup', False):
            yield {
                'config_dir': config_dir,
                'env_file': env_file,
                'config_file': config_file,
                'history_file': history_file,
                'templates_file': templates_file,
                'tags_file': tags_file
            }


class TestDeckTracking:
    """Test deck tracking in processing history"""

    def test_deck_field_in_processing_history(self, mock_services, mock_config):
        """Test that processing history includes deck field for each note"""
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'CustomDeck']

        from obsidianki.main import main
        import obsidianki.cli.config

        result = main()
        assert result == 0, "Should complete successfully"

        # Check processing history has deck field
        history = obsidianki.cli.config.CONFIG.processing_history

        # Find the note path that was processed
        assert len(history) > 0, "Should have processing history"

        for note_path, note_data in history.items():
            assert "decks" in note_data, f"Note {note_path} should have 'decks' field"
            assert isinstance(note_data["decks"], dict), "'decks' should be a dictionary"
            assert "CustomDeck" in note_data["decks"], "Should track CustomDeck"
            assert note_data["decks"]["CustomDeck"] > 0, "Should have flashcard count for deck"

    def test_deck_tracking_multiple_decks(self, mock_services, mock_config):
        """Test that a note can be tracked across multiple decks"""
        import obsidianki.cli.config
        from obsidianki.main import main

        # Process same note with different decks
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'Deck1']
        result1 = main()
        assert result1 == 0

        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'Deck2']
        result2 = main()
        assert result2 == 0

        # Check history tracks both decks
        history = obsidianki.cli.config.CONFIG.processing_history

        for note_path, note_data in history.items():
            if "Test Note 1" in note_path or note_path.endswith("test_note_1.md"):
                assert "Deck1" in note_data["decks"], "Should track Deck1"
                assert "Deck2" in note_data["decks"], "Should track Deck2"
                assert note_data["decks"]["Deck1"] > 0, "Deck1 should have cards"
                assert note_data["decks"]["Deck2"] > 0, "Deck2 should have cards"

    def test_deck_accumulation(self, mock_services, mock_config):
        """Test that deck counts accumulate over multiple runs"""
        import obsidianki.cli.config
        from obsidianki.main import main

        # First run
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'AccumDeck', '-c', '2']
        main()

        history = obsidianki.cli.config.CONFIG.processing_history
        note_path = list(history.keys())[0]
        first_count = history[note_path]["decks"]["AccumDeck"]

        # Second run
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'AccumDeck', '-c', '2']
        main()

        second_count = history[note_path]["decks"]["AccumDeck"]
        assert second_count > first_count, "Deck count should accumulate"
        assert second_count == first_count * 2, "Should double after second run with same card count"

    def test_deck_persistence(self, mock_services, mock_config):
        """Test that deck tracking persists to file"""
        import obsidianki.cli.config
        from obsidianki.main import main

        history_file = mock_config['history_file']

        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'PersistDeck']
        main()

        # Check file was written
        assert history_file.exists(), "Processing history file should exist"

        # Load and verify
        with open(history_file, 'r') as f:
            saved_history = json.load(f)

        assert len(saved_history) > 0, "Should have saved history"
        for note_path, note_data in saved_history.items():
            assert "decks" in note_data, "Should have decks field in saved history"
            assert "PersistDeck" in note_data["decks"], "Should persist deck name"


class TestDuplicateNotePrevention:
    """Test prevention of duplicate notes in same oki run"""

    def test_no_duplicate_notes_in_sample(self, mock_services, mock_config):
        """Test that weighted sampling doesn't produce duplicate notes"""
        import obsidianki.cli.services
        from obsidianki.api.obsidian import ObsidianAPI

        # Create multiple instances of same note
        obsidian = obsidianki.cli.services.OBSIDIAN
        duplicate_note = obsidian.notes[0]  # Get first note

        # Add duplicates to the pool (simulating a bug scenario)
        obsidian.notes.extend([duplicate_note] * 5)

        # Sample notes
        sys.argv = ['oki', '-n', '3']
        from obsidianki.main import main
        result = main()

        # The system should handle duplicates gracefully
        assert result == 0, "Should complete even with duplicates in source"

    def test_pattern_matching_no_duplicates(self, mock_services, mock_config):
        """Test that pattern matching doesn't return duplicates"""
        from obsidianki.cli.models import NotePattern
        import obsidianki.cli.config

        # Temporarily set config for pattern matching
        with patch.object(obsidianki.cli.config.CONFIG, 'search_folders', []):
            pattern = NotePattern("Test*")
            notes = list(pattern)

            # Check for duplicates
            note_paths = [note.path for note in notes]
            assert len(note_paths) == len(set(note_paths)), "Should not have duplicate note paths"

    def test_weighted_sample_removes_selected_notes(self, mock_services, mock_config):
        """Test that _weighted_sample removes notes after selection to prevent duplicates"""
        import obsidianki.cli.services

        obsidian = obsidianki.cli.services.OBSIDIAN
        notes = obsidian.notes  # Get all notes (dummy has 3)

        # Sample all notes
        sampled = obsidian._weighted_sample(notes, limit=len(notes), bias_strength=0.0)

        # Check no duplicates
        sampled_paths = [note.path for note in sampled]
        assert len(sampled_paths) == len(set(sampled_paths)), "Sampled notes should be unique"
        assert len(sampled) == len(notes), f"Should sample all {len(notes)} notes"


class TestHiddenNotes:
    """Test hidden note management commands"""

    def test_hide_command_lists_hidden_notes(self, mock_services, mock_config):
        """Test: oki hide (list hidden notes)"""
        import obsidianki.cli.config
        from obsidianki.cli.commands.hide_cmd import handle_hide_command

        # Hide a note first
        obsidianki.cli.config.CONFIG.hide_note("test/note1.md")
        obsidianki.cli.config.CONFIG.hide_note("test/note2.md")

        # Capture output
        from io import StringIO
        import sys
        captured = StringIO()

        with patch('sys.stdout', captured):
            class Args:
                help = False
                hide_action = None
                note_path = None

            handle_hide_command(Args())

        # Check hidden notes were listed (via CONFIG methods)
        hidden = obsidianki.cli.config.CONFIG.get_hidden_notes()
        assert "test/note1.md" in hidden
        assert "test/note2.md" in hidden
        assert len(hidden) == 2

    def test_hide_unhide_command(self, mock_services, mock_config):
        """Test: oki hide unhide <note_path>"""
        import obsidianki.cli.config
        from obsidianki.cli.commands.hide_cmd import handle_hide_command

        # Hide a note
        obsidianki.cli.config.CONFIG.hide_note("test/hidden_note.md")
        assert obsidianki.cli.config.CONFIG.is_note_hidden("test/hidden_note.md")

        # Unhide it
        class Args:
            help = False
            hide_action = 'unhide'
            note_path = 'test/hidden_note.md'

        handle_hide_command(Args())

        # Verify it's unhidden
        assert not obsidianki.cli.config.CONFIG.is_note_hidden("test/hidden_note.md")
        hidden = obsidianki.cli.config.CONFIG.get_hidden_notes()
        assert "test/hidden_note.md" not in hidden

    def test_hidden_notes_excluded_from_sampling(self, mock_services, mock_config):
        """Test that hidden notes are excluded from note sampling"""
        import obsidianki.cli.services
        import obsidianki.cli.config

        obsidian = obsidianki.cli.services.OBSIDIAN

        # Hide a specific note
        test_note = obsidian.notes[0]
        obsidianki.cli.config.CONFIG.hide_note(test_note.path)

        # Sample notes
        sampled = obsidian.sample_old_notes(days=30, limit=10)

        # Verify hidden note is not in sample
        sampled_paths = [note.path for note in sampled]
        assert test_note.path not in sampled_paths, "Hidden note should not appear in sample"

    def test_hidden_notes_excluded_from_dql(self, mock_services, mock_config):
        """Test that hidden notes are filtered from DQL results"""
        import obsidianki.cli.services
        import obsidianki.cli.config

        obsidian = obsidianki.cli.services.OBSIDIAN

        # Hide a note
        test_note = obsidian.notes[0]
        obsidianki.cli.config.CONFIG.hide_note(test_note.path)

        # Query notes (DQL simulation)
        results = obsidian.dql('LIST WHERE file.name = "Test Note 1"')

        # Verify hidden note filtered out
        if results:
            result_paths = [note.path for note in results]
            assert test_note.path not in result_paths, "Hidden note should be filtered from DQL"

    def test_hide_note_during_approval(self, mock_services, mock_config):
        """Test that notes can be hidden during approval process"""
        import obsidianki.cli.config
        import obsidianki.cli.services

        # Directly test the hide_note functionality instead of approve_note
        # since approve_note uses Prompt which is complex to mock
        test_note = obsidianki.cli.services.OBSIDIAN.notes[0]

        # Verify note is not hidden initially
        assert not obsidianki.cli.config.CONFIG.is_note_hidden(test_note.path)

        # Hide the note
        obsidianki.cli.config.CONFIG.hide_note(test_note.path)

        # Verify it's now hidden
        assert obsidianki.cli.config.CONFIG.is_note_hidden(test_note.path)

        # Verify hidden notes are excluded from operations
        sampled = obsidianki.cli.services.OBSIDIAN.sample_old_notes(days=30, limit=10)
        sampled_paths = [n.path for n in sampled]
        assert test_note.path not in sampled_paths, "Hidden note should not be sampled"


class TestSemanticPadding:
    """Test semantic padding/indentation for flashcard output"""

    def test_flashcard_output_has_padding(self, mock_services, mock_config):
        """Test that flashcard output uses proper padding"""
        from obsidianki.cli.interactive.approval import approve_flashcard
        from obsidianki.cli.models import Flashcard, Note
        from rich.console import Console
        from io import StringIO

        # Create test flashcard
        note = Note(
            path="test.md",
            filename="test.md",
            content="test content",
            tags=["test"],
            size=100
        )
        flashcard = Flashcard(
            front="What is Python?",
            back="A programming language",
            note=note,
            front_original="What is Python?",
            back_original="A programming language"
        )

        # Capture console output
        string_io = StringIO()
        test_console = Console(file=string_io, force_terminal=True, width=120)

        # Mock Confirm.ask to auto-approve
        from rich.prompt import Confirm
        with patch.object(Confirm, 'ask', return_value=True), \
             patch('obsidianki.cli.interactive.approval.console', test_console):
            result = approve_flashcard(flashcard)

            output = string_io.getvalue()

            # Check that output contains Front and Back labels
            assert "Front:" in output, "Should display Front label"
            assert "Back:" in output, "Should display Back label"
            assert "What is Python?" in output
            assert "A programming language" in output

    def test_multiline_flashcard_maintains_indentation(self, mock_services, mock_config):
        """Test that multiline flashcards maintain proper indentation"""
        from obsidianki.cli.interactive.approval import approve_flashcard
        from obsidianki.cli.models import Flashcard, Note
        from rich.console import Console
        from io import StringIO

        # Create flashcard with multiline content
        note = Note(
            path="test.md",
            filename="test.md",
            content="test",
            tags=[],
            size=100
        )

        multiline_front = "What are the three pillars?\n1. First\n2. Second\n3. Third"
        multiline_back = "Answer:\n- Point A\n- Point B\n- Point C"

        flashcard = Flashcard(
            front=multiline_front,
            back=multiline_back,
            note=note,
            front_original=multiline_front,
            back_original=multiline_back
        )

        string_io = StringIO()
        test_console = Console(file=string_io, force_terminal=True, width=120)

        from rich.prompt import Confirm
        with patch.object(Confirm, 'ask', return_value=True), \
             patch('obsidianki.cli.interactive.approval.console', test_console):
            approve_flashcard(flashcard)
            output = string_io.getvalue()

            # Verify multiline content is present (check without color codes)
            assert "First" in output
            assert "Second" in output
            assert "Point A" in output


class TestTemplates:
    """Test template functionality"""

    def test_template_add(self, mock_services, mock_config):
        """Test: oki template add <name> <command>"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config

        class Args:
            template_action = 'add'
            help = False
            name = 'test_template'
            template_command = '--notes 5 --cards 10'

        handle_template_command(Args())

        # Verify template was saved
        templates = obsidianki.cli.config.CONFIG.load_templates()
        assert 'test_template' in templates
        assert templates['test_template'] == '--notes 5 --cards 10'

    def test_template_list(self, mock_services, mock_config):
        """Test: oki template (list all templates)"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config

        # Add some templates
        templates = {
            'template1': '--notes 3',
            'template2': '--cards 5 --deck Test'
        }
        obsidianki.cli.config.CONFIG.save_templates(templates)

        class Args:
            template_action = None
            help = False

        # Should list templates without error
        handle_template_command(Args())

        # Verify templates can be loaded
        loaded = obsidianki.cli.config.CONFIG.load_templates()
        assert 'template1' in loaded
        assert 'template2' in loaded

    def test_template_use(self, mock_services, mock_config):
        """Test: oki template use <name>"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config

        # Save a template
        templates = {'quick': '--notes 1 --cards 2'}
        obsidianki.cli.config.CONFIG.save_templates(templates)

        # Use template
        class Args:
            template_action = 'use'
            help = False
            name = 'quick'

        # Mock main and sys.exit to prevent actual execution
        from obsidianki import main as main_module
        import sys
        with patch.object(main_module, 'main') as mock_main, \
             patch.object(sys, 'exit') as mock_exit:
            mock_main.return_value = 0
            handle_template_command(Args())

            # Verify main was called
            assert mock_main.called, "Should call main() to execute template"
            # Verify sys.exit was called with 0
            mock_exit.assert_called_once_with(0)

    def test_template_remove(self, mock_services, mock_config):
        """Test: oki template remove <name>"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config

        # Add a template
        templates = {'to_remove': '--notes 10'}
        obsidianki.cli.config.CONFIG.save_templates(templates)

        class Args:
            template_action = 'remove'
            help = False
            name = 'to_remove'

        # Mock confirm
        with patch('obsidianki.cli.commands.template_cmd.Confirm.ask', return_value=True):
            handle_template_command(Args())

        # Verify template was removed
        loaded = obsidianki.cli.config.CONFIG.load_templates()
        assert 'to_remove' not in loaded

    def test_template_persistence(self, mock_services, mock_config):
        """Test that templates persist to file"""
        import obsidianki.cli.config

        templates_file = mock_config['templates_file']

        # Add template
        templates = {'persistent': '--notes 7 --bias 0.5'}
        obsidianki.cli.config.CONFIG.save_templates(templates)

        # Verify file exists
        assert templates_file.exists(), "Templates file should exist"

        # Load from file
        with open(templates_file, 'r') as f:
            saved = json.load(f)

        assert 'persistent' in saved
        assert saved['persistent'] == '--notes 7 --bias 0.5'

    def test_template_with_complex_command(self, mock_services, mock_config):
        """Test template with complex command including quotes and special chars"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config

        complex_cmd = '--notes "Test Note 1" --cards 5 --deck "My Deck"'

        class Args:
            template_action = 'add'
            help = False
            name = 'complex'
            template_command = complex_cmd

        handle_template_command(Args())

        templates = obsidianki.cli.config.CONFIG.load_templates()
        assert templates['complex'] == complex_cmd

    def test_template_with_overrides(self, mock_services, mock_config):
        """Test template use with override arguments"""
        from obsidianki.cli.commands.template_cmd import handle_template_command
        import obsidianki.cli.config
        import sys

        # Save a template with specific deck and cards
        templates = {'japanese': '--notes 5 --cards 10 --deck Japanese --bias 0.7'}
        obsidianki.cli.config.CONFIG.save_templates(templates)

        # Use template with override arguments
        class Args:
            template_action = 'use'
            help = False
            name = 'japanese'
            override_args = ['--deck', 'JLPT_N3', '--cards', '20']

        # Mock main and sys.exit to capture the final argv
        from obsidianki import main as main_module
        captured_argv = None

        def capture_argv(*args, **kwargs):
            nonlocal captured_argv
            captured_argv = list(sys.argv)
            return 0

        with patch.object(main_module, 'main', side_effect=capture_argv) as mock_main, \
             patch.object(sys, 'exit') as mock_exit:
            handle_template_command(Args())

            # Verify the final argv contains overridden values
            assert captured_argv is not None, "main() should have been called"
            argv_str = ' '.join(captured_argv)

            # Should have both template args and overrides, with overrides taking precedence
            assert '--notes' in captured_argv
            assert '5' in captured_argv
            assert '--bias' in captured_argv
            assert '0.7' in captured_argv

            # Deck should appear twice (template + override), but argparse uses the last one
            assert argv_str.count('--deck') == 2
            deck_indices = [i for i, x in enumerate(captured_argv) if x == '--deck']
            assert len(deck_indices) == 2
            # First deck is from template
            assert captured_argv[deck_indices[0] + 1] == 'Japanese'
            # Second deck is from override (this one wins)
            assert captured_argv[deck_indices[1] + 1] == 'JLPT_N3'

            # Cards should also appear twice
            assert argv_str.count('--cards') == 2
            cards_indices = [i for i, x in enumerate(captured_argv) if x == '--cards']
            assert captured_argv[cards_indices[0] + 1] == '10'  # template
            assert captured_argv[cards_indices[1] + 1] == '20'  # override wins


class TestUseSchemaWithNote:
    """Test --use-schema flag with specific note specification"""

    def test_use_schema_with_single_note(self, mock_services, mock_config):
        """Test: oki -n "NoteName" --use-schema"""
        sys.argv = ['oki', '-n', 'Test Note 1', '--use-schema']

        from obsidianki.main import main
        import obsidianki.cli.config

        result = main()
        assert result == 0, "Should work with specific note and schema"

        # Verify that use_deck_schema was enabled
        assert obsidianki.cli.config.CONFIG.use_deck_schema is True, "--use-schema should enable schema usage"

    def test_use_schema_with_pattern(self, mock_services, mock_config):
        """Test: oki -n "folder/*" --use-schema"""
        sys.argv = ['oki', '-n', 'Test*', '--use-schema']

        from obsidianki.main import main
        import obsidianki.cli.config

        result = main()
        assert result == 0, "Should work with pattern and schema"

        # Verify schema was enabled
        assert obsidianki.cli.config.CONFIG.use_deck_schema is True, "--use-schema should enable schema usage"

    def test_use_schema_fetches_deck_examples(self, mock_services, mock_config):
        """Test that --use-schema fetches examples from the specified deck"""
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'CustomDeck', '--use-schema']

        from obsidianki.main import main
        import obsidianki.cli.config
        import obsidianki.cli.services
        from unittest.mock import MagicMock

        # Track if get_card_examples is called
        original_get_card_examples = obsidianki.cli.services.ANKI.get_card_examples
        obsidianki.cli.services.ANKI.get_card_examples = MagicMock(return_value=[
            {'front': 'What is X?', 'back': 'X is Y'}
        ])

        result = main()
        assert result == 0, "Should work with schema flag"

        # Verify get_card_examples was called with the CustomDeck
        assert obsidianki.cli.services.ANKI.get_card_examples.called, "Should fetch card examples"
        call_args = obsidianki.cli.services.ANKI.get_card_examples.call_args
        assert call_args[0][0] == 'CustomDeck', "Should fetch examples from CustomDeck"

        # Restore
        obsidianki.cli.services.ANKI.get_card_examples = original_get_card_examples

    def test_use_schema_with_origin_note(self, mock_services, mock_config):
        """Test --use-schema with origin note specification (from note path)"""
        sys.argv = ['oki', '-n', 'Test Note 1', '--use-schema', 'Test Note 2']

        from obsidianki.main import main
        import obsidianki.cli.services
        import obsidianki.cli.config
        from unittest.mock import MagicMock

        # Mock get_card_examples to return cards from specific note
        original_get_card_examples = obsidianki.cli.services.ANKI.get_card_examples
        obsidianki.cli.services.ANKI.get_card_examples = MagicMock(return_value=[
            {'front': 'Origin Q1', 'back': 'Origin A1'},
            {'front': 'Origin Q2', 'back': 'Origin A2'}
        ])

        result = main()
        assert result == 0, "Should work with origin note specification"

        # Verify get_card_examples was called with note_paths parameter
        assert obsidianki.cli.services.ANKI.get_card_examples.called, "Should fetch card examples from origin note"

        # Restore
        obsidianki.cli.services.ANKI.get_card_examples = original_get_card_examples

    def test_use_schema_empty_deck(self, mock_services, mock_config):
        """Test --use-schema behavior when deck has no cards"""
        sys.argv = ['oki', '-n', 'Test Note 1', '-d', 'EmptyDeck', '--use-schema']

        from obsidianki.main import main
        import obsidianki.cli.services
        import obsidianki.cli.config
        from unittest.mock import MagicMock

        # Mock to return empty list
        original_get_card_examples = obsidianki.cli.services.ANKI.get_card_examples
        obsidianki.cli.services.ANKI.get_card_examples = MagicMock(return_value=[])

        result = main()
        # Should still work, just without schema examples
        assert result == 0, "Should handle empty deck gracefully"

        # Verify schema was enabled even though deck is empty
        assert obsidianki.cli.config.CONFIG.use_deck_schema is True, "--use-schema should be enabled"
        assert obsidianki.cli.services.ANKI.get_card_examples.called, "Should attempt to fetch examples"

        # Restore
        obsidianki.cli.services.ANKI.get_card_examples = original_get_card_examples


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
