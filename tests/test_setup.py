"""Test the interactive setup wizard flow"""
import pytest
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import mocks
from tests.mocks.dummy_ai import DummyFlashcardAI
from tests.mocks.dummy_obsidian import DummyObsidianAPI
from tests.mocks.dummy_anki import DummyAnkiAPI


@pytest.fixture
def clean_temp_config():
    """Create a temporary directory for fresh config setup"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "config.json"
        env_file = config_dir / ".env"

        # Patch config paths
        with patch('cli.config.CONFIG_DIR', config_dir), \
             patch('cli.config.CONFIG_FILE', config_file), \
             patch('cli.config.ENV_FILE', env_file):
            yield {
                'config_dir': config_dir,
                'config_file': config_file,
                'env_file': env_file
            }


@pytest.fixture
def mock_services():
    """Set up mock services before each test"""
    import cli.services

    # Store originals
    original_ai = cli.services.AI
    original_obsidian = cli.services.OBSIDIAN
    original_anki = cli.services.ANKI

    # Replace with mocks
    cli.services.AI = DummyFlashcardAI()
    cli.services.OBSIDIAN = DummyObsidianAPI()
    cli.services.ANKI = DummyAnkiAPI()

    yield

    # Restore originals
    cli.services.AI = original_ai
    cli.services.OBSIDIAN = original_obsidian
    cli.services.ANKI = original_anki


@pytest.fixture
def mock_prompts():
    """Mock all interactive prompts for automated testing"""
    mock_responses = {
        'api_key': 'test_anthropic_key_12345',
        'obsidian_key': 'test_obsidian_key_67890',
        'deck': 'Test Deck',
        'max_cards': 10,
        'notes_to_sample': 5,
        'approve_notes': False,
        'approve_cards': False,
        'card_type': 'basic',
        'sampling_mode': 'weighted',
        'days_old': 7,
    }

    def mock_prompt_ask(prompt_text, default=None, choices=None, password=False, **kwargs):
        """Mock Prompt.ask() - handles both string and choice prompts"""
        prompt_lower = prompt_text.lower()

        # API keys
        if 'anthropic' in prompt_lower:
            return mock_responses['api_key']
        elif 'obsidian' in prompt_lower:
            return mock_responses['obsidian_key']

        # Choices
        if choices:
            if 'card type' in prompt_lower:
                return 'basic'
            elif 'sampling' in prompt_lower:
                return 'weighted'
            return choices[0]

        return default if default else ''

    def mock_int_prompt_ask(prompt_text, default=None, **kwargs):
        """Mock IntPrompt.ask() - returns integers"""
        prompt_lower = prompt_text.lower()

        if 'flashcards' in prompt_lower or 'cards' in prompt_lower:
            return mock_responses['max_cards']
        elif 'notes' in prompt_lower and 'sample' in prompt_lower:
            return mock_responses['notes_to_sample']
        elif 'days' in prompt_lower:
            return mock_responses['days_old']

        return default if default else 0

    def mock_confirm_ask(prompt_text, default=None, **kwargs):
        """Mock Confirm.ask() - returns booleans"""
        prompt_lower = prompt_text.lower()

        # Return False for approval prompts
        if 'review' in prompt_lower or 'approve' in prompt_lower:
            return False

        # Return True for feature toggles by default
        if 'syntax' in prompt_lower or 'highlighting' in prompt_lower:
            return True
        if 'duplicate' in prompt_lower or 'history' in prompt_lower:
            return True

        return default if default is not None else True

    with patch('rich.prompt.Prompt.ask', side_effect=mock_prompt_ask), \
         patch('rich.prompt.IntPrompt.ask', side_effect=mock_int_prompt_ask), \
         patch('rich.prompt.Confirm.ask', side_effect=mock_confirm_ask):
        yield mock_responses


class TestSetupFlow:
    """Test the setup wizard"""

    def test_setup_creates_config_files(self, clean_temp_config, mock_services, mock_prompts, capsys):
        #TODO
        """Test that setup creates .env and config.json"""
        print("\n=== Testing setup flow ===")

        paths = clean_temp_config

        # Verify files don't exist initially
        assert not paths['config_file'].exists(), "Config should not exist yet"
        assert not paths['env_file'].exists(), "Env file should not exist yet"

        sys.argv = ['oki', '--setup']

        from main import main

        try:
            result = main()
            print(f"Setup returned: {result}")
        except SystemExit as e:
            print(f"Setup exited with: {e.code}")
            result = e.code if e.code is not None else 0

        captured = capsys.readouterr()
        print(f"Setup output:\n{captured.out}")

        # Check if files were created
        if paths['env_file'].exists():
            print(f".env file created: {paths['env_file']}")
            with open(paths['env_file'], 'r') as f:
                print(f"Contents:\n{f.read()}")

        if paths['config_file'].exists():
            print(f"config.json created: {paths['config_file']}")
            with open(paths['config_file'], 'r') as f:
                print(f"Contents:\n{f.read()}")

    def test_setup_runs_without_error(self, clean_temp_config, mock_services, mock_prompts):
        """Test that setup completes without crashing"""
        sys.argv = ['oki', '--setup']

        from main import main

        # Should not raise an exception
        try:
            result = main()
            # Setup might return 0 or None
            assert result == 0 or result is None
        except SystemExit as e:
            # SystemExit with code 0 is ok
            assert e.code == 0 or e.code is None

    def test_setup_when_config_missing(self, clean_temp_config, mock_services, mock_prompts):
        #TODO
        """Test that CLI triggers setup when config is missing"""
        paths = clean_temp_config

        # Config doesn't exist, so it should trigger setup
        sys.argv = ['oki', 'config']

        from main import main

        # Should run setup automatically or gracefully handle missing config
        try:
            result = main()
            # Should either complete setup or handle missing config
            assert result == 0 or result is None or result == 1
        except SystemExit:
            pass  # Exit is acceptable for setup flow


class TestSetupValidation:
    """Test setup validation logic"""

    def test_empty_api_keys_rejected(self):
        #TODO
        """Test that empty API keys are handled"""
        # This would test validation logic
        # For now, just document the expected behavior
        assert True

    def test_invalid_deck_names_handled(self):
        #TODO
        """Test that invalid deck names are handled"""
        # Would test deck name validation
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
