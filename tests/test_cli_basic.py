"""Basic CLI command tests"""
import pytest
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import tests.utils
mock_services = tests.utils.mock_services


@pytest.fixture
def temp_config():
    """Create temporary config directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "config.json"
        env_file = config_dir / ".env"

        # Create minimal config
        config_data = {
            "DECK": "Test Deck",
            "MAX_CARDS": 10,
            "NOTES_TO_SAMPLE": 3,
            "APPROVE_NOTES": False,
            "APPROVE_CARDS": False,
            "CARD_TYPE": "basic",
            "SAMPLING_MODE": "weighted",
            "DAYS_OLD": 7,
            "DIFFICULTY": "normal",
            "SYNTAX_HIGHLIGHTING": False,
            "SEARCH_FOLDERS": [],
            "DEDUPLICATE_VIA_HISTORY": False,
            "DEDUPLICATE_VIA_DECK": False,
            "USE_DECK_SCHEMA": False,
            "UPFRONT_BATCHING": False,
            "BATCH_SIZE_LIMIT": 10,
            "BATCH_CARD_LIMIT": 20,
            "DENSITY_BIAS_STRENGTH": 0.0
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        # Create minimal .env
        with open(env_file, 'w') as f:
            f.write("ANTHROPIC_API_KEY=test_key\n")
            f.write("OBSIDIAN_API_KEY=test_key\n")

        # Patch config paths
        with patch('obsidianki.cli.config.CONFIG_DIR', config_dir), \
             patch('obsidianki.cli.config.CONFIG_FILE', config_file), \
             patch('obsidianki.cli.config.ENV_FILE', env_file), \
             patch('obsidianki.cli.commands.config_cmd.CONFIG_FILE', config_file):
            yield config_dir


@pytest.fixture
def mock_config():
    """Patch config to use temp directory and disable interactive prompts"""
    import obsidianki.cli.config

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
             patch.object(obsidianki.cli.config.CONFIG, 'APPROVE_CARDS', False):
            yield


class TestBasicCommands:
    """Test basic CLI commands that don't require full setup"""

    def test_help_command(self, capsys):
        """Test help command displays without error"""
        sys.argv = ['oki', '--help']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "ObsidianKi" in captured.out or "Usage" in captured.out

    def test_config_help(self, capsys):
        """Test config help command"""
        sys.argv = ['oki', 'config', '--help']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "config" in captured.out.lower()

    def test_tag_help(self, capsys):
        """Test tag help command"""
        sys.argv = ['oki', 'tag', '--help']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "tag" in captured.out.lower()

    def test_history_help(self, capsys):
        """Test history help command"""
        sys.argv = ['oki', 'history', '--help']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "history" in captured.out.lower()

    def test_deck_help(self, capsys):
        """Test deck help command"""
        sys.argv = ['oki', 'deck', '--help']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "deck" in captured.out.lower()


class TestConfigCommands:
    """Test config management commands with mocked environment"""

    def test_config_list(self, mock_services, temp_config, capsys):
        """Test listing configuration"""
        sys.argv = ['oki', 'config']

        from obsidianki.main import main

        result = main()
        assert result == 0

    def test_config_where(self, mock_services, temp_config, capsys):
        """Test showing config directory"""
        sys.argv = ['oki', 'config', 'where']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        # Should print a directory path
        assert len(captured.out.strip()) > 0
        assert '/' in captured.out or '\\' in captured.out  # Path separator

    def test_config_set_difficulty(self, mock_services, temp_config, capsys):
        """Test setting difficulty configuration"""
        import json
        from obsidianki.cli.config import CONFIG_FILE

        # Test setting to 'easy'
        sys.argv = ['oki', 'config', 'set', 'difficulty', 'easy']
        from obsidianki.main import main
        result = main()
        assert result == 0

        # Verify the config file was updated
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        assert config['DIFFICULTY'] == 'easy'

        # Test setting to 'hard'
        sys.argv = ['oki', 'config', 'set', 'difficulty', 'hard']
        result = main()
        assert result == 0

        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        assert config['DIFFICULTY'] == 'hard'

        # Test setting to 'normal'
        sys.argv = ['oki', 'config', 'set', 'difficulty', 'normal']
        result = main()
        assert result == 0

        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        assert config['DIFFICULTY'] == 'normal'

        # Test invalid difficulty value
        sys.argv = ['oki', 'config', 'set', 'difficulty', 'invalid']
        result = main()
        # Should not change the value
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        assert config['DIFFICULTY'] == 'normal'  # Should still be 'normal'


class TestDeckCommands:
    """Test deck management commands"""

    def test_deck_list(self, mock_services, temp_config, capsys):
        """Test listing decks"""
        sys.argv = ['oki', 'deck']

        from obsidianki.main import main
        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "deck" in captured.out.lower() or "Default" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
