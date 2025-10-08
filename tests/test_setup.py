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

    def test_setup_creates_config_files(self, clean_temp_config, mock_services, mock_prompts):
        """Test that setup creates .env and config.json"""
        paths = clean_temp_config

        # Verify files don't exist initially
        assert not paths['config_file'].exists(), "Config should not exist yet"
        assert not paths['env_file'].exists(), "Env file should not exist yet"

        sys.argv = ['oki', '--setup']

        from main import main

        try:
            result = main()
        except SystemExit as e:
            result = e.code if e.code is not None else 0

        # Should complete successfully
        assert result == 0, f"Setup should return 0, got {result}"

        # Verify files were created
        assert paths['env_file'].exists(), ".env file should be created"
        assert paths['config_file'].exists(), "config.json file should be created"

        # Verify .env has required keys
        with open(paths['env_file'], 'r') as f:
            env_content = f.read()
            assert 'OBSIDIAN_API_KEY' in env_content, ".env should contain OBSIDIAN_API_KEY"
            assert 'ANTHROPIC_API_KEY' in env_content, ".env should contain ANTHROPIC_API_KEY"

        # Verify config.json has valid JSON structure
        with open(paths['config_file'], 'r') as f:
            config = json.load(f)
            assert 'MAX_CARDS' in config, "config should contain MAX_CARDS"
            assert 'NOTES_TO_SAMPLE' in config, "config should contain NOTES_TO_SAMPLE"
            assert 'DECK' in config, "config should contain DECK"

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

    def test_setup_when_config_missing(self):
        """Test that setup wizard logic works correctly when called directly"""
        # This tests the setup wizard directly since testing through main()
        # with patched config paths is problematic due to module-level imports

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_config_dir = Path(tmpdir)
            test_env = test_config_dir / ".env"
            test_config = test_config_dir / "config.json"

            # Mock prompts
            def mock_prompt(text, **kwargs):
                if 'Obsidian' in text:
                    return 'test_obs_key_123'
                elif 'Anthropic' in text:
                    return 'test_anthro_key_456'
                elif 'Sampling mode' in text:
                    return 'random'
                elif 'Card type' in text:
                    return 'basic'
                return ''

            def mock_int_prompt(text, **kwargs):
                return kwargs.get('default', 6)

            def mock_confirm(text, **kwargs):
                return kwargs.get('default', False)

            # Patch both the wizard module's paths and the prompts
            with patch('cli.wizard.CONFIG_DIR', test_config_dir), \
                 patch('cli.wizard.ENV_FILE', test_env), \
                 patch('cli.wizard.CONFIG_FILE', test_config), \
                 patch('rich.prompt.Prompt.ask', side_effect=mock_prompt), \
                 patch('rich.prompt.IntPrompt.ask', side_effect=mock_int_prompt), \
                 patch('rich.prompt.Confirm.ask', side_effect=mock_confirm):

                from cli.wizard import setup
                setup(force_full_setup=True)

                # Verify files were created
                assert test_env.exists(), "Setup should create .env"
                assert test_config.exists(), "Setup should create config.json"

                # Verify content
                with open(test_env, 'r') as f:
                    env_content = f.read()
                    assert 'test_obs_key_123' in env_content
                    assert 'test_anthro_key_456' in env_content


class TestSetupValidation:
    """Test setup validation logic"""

    def test_empty_api_keys_rejected(self, clean_temp_config, mock_services):
        """Test that empty API keys are rejected during setup"""
        paths = clean_temp_config

        # Mock prompts to return empty strings
        def mock_empty_prompt(prompt_text, **kwargs):
            return ""  # Empty key

        with patch('rich.prompt.Prompt.ask', side_effect=mock_empty_prompt):
            sys.argv = ['oki', '--setup']
            from main import main

            result = main()

            # Setup should return None or 0 (it just returns early without creating files)
            # Files should NOT be created when API keys are empty
            assert not paths['env_file'].exists(), "Should not create .env with empty keys"

    def test_invalid_deck_names_handled(self, clean_temp_config, mock_services, mock_prompts):
        """Test that deck names with special characters are handled"""
        # Set up config first
        sys.argv = ['oki', '--setup']
        from main import main
        main()

        # Test that deck names with special characters work
        # AnkiConnect should handle deck creation
        sys.argv = ['oki', '-d', 'Test::Subdeck']
        result = main()

        # Should complete successfully - Anki allows :: for subdecks
        assert result == 0, "Should handle deck names with special characters"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
