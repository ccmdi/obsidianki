"""Test the main flashcard generation flow with all critical branching paths"""
import pytest
import sys
from unittest.mock import patch

import tests.utils
mock_services = tests.utils.mock_services


@pytest.fixture
def mock_config():
    """Patch config to use temp directory and disable interactive prompts"""
    import obsidianki.cli.config
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        env_file = config_dir / ".env"
        config_file = config_dir / "config.json"
        history_file = config_dir / "processing_history.json"

        env_file.write_text("OBSIDIAN_API_KEY=test\nANTHROPIC_API_KEY=test\n")
        config_file.write_text('{"DECK": "Obsidian-test"}')

        with patch.object(obsidianki.cli.config, 'ENV_FILE', env_file), \
             patch.object(obsidianki.cli.config, 'CONFIG_FILE', config_file), \
             patch('obsidianki.main.ENV_FILE', env_file), \
             patch('obsidianki.main.CONFIG_FILE', config_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history_file', history_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history', {}), \
             patch.object(obsidianki.cli.config.CONFIG, 'APPROVE_NOTES', False), \
             patch.object(obsidianki.cli.config.CONFIG, 'APPROVE_CARDS', False), \
             patch.object(obsidianki.cli.config.CONFIG, 'UPFRONT_BATCHING', False):
            yield


class TestDefaultFlow:
    """Test default behavior (no flags)"""

    def test_default_run(self, mock_services, mock_config):
        """Test: oki (default run, samples old notes)"""
        sys.argv = ['oki']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Default run should complete successfully"

    def test_default_generates_cards(self, mock_services, mock_config):
        """Test: oki generates flashcards and adds to Anki"""
        sys.argv = ['oki']

        from obsidianki.main import main
        import obsidianki.cli.services
        import obsidianki.cli.config

        anki = obsidianki.cli.services.ANKI
        deck_name = obsidianki.cli.config.CONFIG.DECK  # Use the actual configured deck name
        initial_card_count = len(anki.cards.get(deck_name, []))

        result = main()

        # Should have added cards
        final_card_count = len(anki.cards.get(deck_name, []))
        assert final_card_count > initial_card_count, "Should add cards to Anki"


class TestCardsFlag:
    """Test -c/--cards flag behavior"""

    def test_cards_limit(self, mock_services, mock_config):
        """Test: oki -c 5 (limits max cards)"""
        sys.argv = ['oki', '-c', '5']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should complete successfully with card limit"

    def test_cards_zero(self, mock_services, mock_config):
        """Test: oki -c 0 (edge case: zero cards)"""
        sys.argv = ['oki', '-c', '0']

        from obsidianki.main import main
        result = main()

        # The code uses max(1, max_cards // len(notes)), so even with -c 0,
        # target_cards_per_note will be 1. However, the final output message says
        # "Added X/0 flashcards" because max_cards is 0. This is expected behavior.
        assert result == 0, "Should complete successfully with zero card limit"

    def test_cards_large_number(self, mock_services, mock_config):
        """Test: oki -c 100 (large card limit)"""
        sys.argv = ['oki', '-c', '100']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should handle large card limit"


class TestNotesFlag:
    """Test -n/--notes flag behavior"""

    def test_notes_count(self, mock_services, mock_config):
        """Test: oki -n 2 (sample N notes)"""
        sys.argv = ['oki', '-n', '2']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should sample 2 notes successfully"

    def test_notes_by_name(self, mock_services, mock_config):
        """Test: oki -n "Test Note 1" (specific note by name)"""
        sys.argv = ['oki', '-n', 'Test Note 1']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should process specific note"

    def test_notes_multiple_names(self, mock_services, mock_config):
        """Test: oki -n "Test Note 1" "Test Note 2" (multiple notes)"""
        sys.argv = ['oki', '-n', 'Test Note 1', 'Test Note 2']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should process multiple named notes"

    def test_notes_pattern(self, mock_services, mock_config):
        """Test: oki -n "notes/*" (pattern matching)"""
        sys.argv = ['oki', '-n', 'notes/*']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should process notes matching pattern"

    def test_notes_pattern_with_sample(self, mock_services, mock_config):
        """Test: oki -n "notes/*:2" (pattern with sample size)"""
        sys.argv = ['oki', '-n', 'notes/*:2']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should sample from pattern"

    def test_notes_nonexistent(self, mock_services, mock_config):
        """Test: oki -n "NonexistentNote" (note not found)"""
        sys.argv = ['oki', '-n', 'NonexistentNote']

        from obsidianki.main import main
        result = main()

        # Should fail or return 1 when no notes found
        assert result == 1, "Should return error when note not found"


class TestQueryMode:
    """Test -q/--query flag behavior"""

    def test_query_standalone(self, mock_services, mock_config):
        """Test: oki -q "Python lists" (standalone query mode)"""
        sys.argv = ['oki', '-q', 'Python lists']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Standalone query should work"

    def test_query_with_notes(self, mock_services, mock_config):
        """Test: oki -q "lists" -n "Test Note 1" (targeted extraction)"""
        sys.argv = ['oki', '-q', 'lists', '-n', 'Test Note 1']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Query extraction from specific note should work"

    def test_query_with_multiple_notes(self, mock_services, mock_config):
        """Test: oki -q "programming" -n 2 (query across multiple notes)"""
        sys.argv = ['oki', '-q', 'programming', '-n', '2']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Query extraction from multiple notes should work"

    def test_query_with_cards_limit(self, mock_services, mock_config):
        """Test: oki -q "Python" -c 3 (query with card limit)"""
        sys.argv = ['oki', '-q', 'Python', '-c', '3']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Query with card limit should work"


class TestDeckFlag:
    """Test -d/--deck flag behavior"""

    def test_custom_deck(self, mock_services, mock_config):
        """Test: oki -d "Custom Deck" (use different deck)"""
        sys.argv = ['oki', '-d', 'Custom Deck']

        from obsidianki.main import main
        import obsidianki.cli.services

        result = main()

        # Check that cards were added to custom deck
        anki = obsidianki.cli.services.ANKI
        assert 'Custom Deck' in anki.decks, "Custom deck should be created"
        assert len(anki.cards.get('Custom Deck', [])) > 0, "Cards should be in custom deck"

    def test_deck_with_spaces(self, mock_services, mock_config):
        """Test: oki -d "My Special Deck" (deck name with spaces)"""
        sys.argv = ['oki', '-d', 'My Special Deck']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should handle deck names with spaces"


class TestBiasFlag:
    """Test -b/--bias flag behavior"""

    def test_bias_zero(self, mock_services, mock_config):
        """Test: oki -b 0.0 (no bias)"""
        sys.argv = ['oki', '-b', '0.0']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should work with zero bias"

    def test_bias_max(self, mock_services, mock_config):
        """Test: oki -b 1.0 (maximum bias)"""
        sys.argv = ['oki', '-b', '1.0']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should work with maximum bias"

    def test_bias_mid(self, mock_services, mock_config):
        """Test: oki -b 0.5 (medium bias)"""
        sys.argv = ['oki', '-b', '0.5']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should work with medium bias"


class TestUseSchemaFlag:
    """Test -u/--use-schema flag behavior"""

    def test_use_schema(self, mock_services, mock_config):
        """Test: oki -u (use existing deck card schema)"""
        sys.argv = ['oki', '-u']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Should use deck schema for formatting"


class TestCombinedFlags:
    """Test combinations of flags"""

    def test_cards_and_notes(self, mock_services, mock_config):
        """Test: oki -c 6 -n 2 (card limit with note sampling)"""
        sys.argv = ['oki', '-c', '6', '-n', '2']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Cards and notes flags should work together"

    def test_query_cards_deck(self, mock_services, mock_config):
        """Test: oki -q "Python" -c 5 -d "Study Deck" (query with limits and deck)"""
        sys.argv = ['oki', '-q', 'Python', '-c', '5', '-d', 'Study Deck']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Query, cards, and deck flags should work together"

    def test_notes_bias_schema(self, mock_services, mock_config):
        """Test: oki -n "Test" -b 0.7 -u (notes with bias and schema)"""
        sys.argv = ['oki', '-n', 'Test', '-b', '0.7', '-u']

        from obsidianki.main import main
        result = main()

        assert result == 0, "Notes, bias, and schema flags should work together"

    def test_all_flags(self, mock_services, mock_config):
        """Test: oki -c 10 -n 2 -d "Full Test" -b 0.5 -u (all major flags)"""
        sys.argv = ['oki', '-c', '10', '-n', '2', '-d', 'Full Test', '-b', '0.5', '-u']

        from obsidianki.main import main
        result = main()

        assert result == 0, "All flags should work together"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_no_notes_found(self, mock_services, mock_config):
        """Test behavior when no notes match criteria"""
        import obsidianki.cli.services
        
        # The fixture provides the mock, we just modify it
        obsidianki.cli.services.OBSIDIAN.notes = []

        sys.argv = ['oki']
        from obsidianki.main import main
        result = main()
        assert result == 1, "Should return error when no notes found"

    def test_connection_failure_obsidian(self, mock_services, mock_config):
        """Test behavior when Obsidian connection fails"""
        import obsidianki.cli.services
        
        # The fixture provides the mock, we just modify it
        obsidianki.cli.services.OBSIDIAN.test_connection = lambda: False

        sys.argv = ['oki']
        from obsidianki.main import main
        result = main()
        assert result == 1, "Should fail when Obsidian connection fails"

    def test_connection_failure_anki(self, mock_services, mock_config):
        """Test behavior when Anki connection fails"""
        import obsidianki.cli.services

        # The fixture provides the mock, we just modify it
        obsidianki.cli.services.ANKI.test_connection = lambda: False

        sys.argv = ['oki']
        from obsidianki.main import main
        result = main()
        assert result == 1, "Should fail when Anki connection fails"

    def test_no_flashcards_generated(self, mock_services, mock_config):
        """Test behavior when AI generates no flashcards"""
        import obsidianki.cli.services

        # The fixture provides the mock, we just modify it
        obsidianki.cli.services.AI.generate_flashcards = lambda *args, **kwargs: []

        # Use a command that is guaranteed to find a note
        sys.argv = ['oki']

        from obsidianki.main import main
        result = main()
        assert result == 0, "Should handle no flashcards gracefully"


class TestFlashcardGeneration:
    """Test actual flashcard generation logic"""

    def test_flashcards_have_content(self, mock_services, mock_config):
        """Test that generated flashcards have front and back"""
        sys.argv = ['oki', '-n', '1']

        from obsidianki.main import main
        import obsidianki.cli.services
        import obsidianki.cli.config

        result = main()

        # Check cards in Anki have content
        anki = obsidianki.cli.services.ANKI
        deck_name = obsidianki.cli.config.CONFIG.DECK  # Use the actual configured deck name
        cards = anki.cards.get(deck_name, [])

        assert len(cards) > 0, "Should generate at least one card"
        for card in cards:
            assert card['front'], "Card should have front"
            assert card['back'], "Card should have back"

    def test_flashcards_have_tags(self, mock_services, mock_config):
        """Test that flashcards have appropriate tags"""
        sys.argv = ['oki', '-n', 'Test Note 1']

        from obsidianki.main import main
        import obsidianki.cli.services
        import obsidianki.cli.config

        result = main()

        anki = obsidianki.cli.services.ANKI
        deck_name = obsidianki.cli.config.CONFIG.DECK  # Use the actual configured deck name
        cards = anki.cards.get(deck_name, [])

        assert len(cards) > 0, "Should generate cards"
        for card in cards:
            assert card['tags'], "Card should have tags"
            assert len(card['tags']) > 0, "Tags should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
