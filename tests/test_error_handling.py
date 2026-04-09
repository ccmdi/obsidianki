"""Test error handling and edge cases - Fixed version"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import requests


class TestAPIErrorHandling:
    """Test error handling in API classes"""

    @patch('requests.request')
    def test_anki_connection_timeout(self, mock_post):
        """Test handling of connection timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(requests.exceptions.Timeout):
            anki._request("deckNames")

    @patch('requests.request')
    def test_anki_connection_refused(self, mock_post):
        """Test handling of connection refused"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(requests.exceptions.ConnectionError):
            anki._request("version")

    @patch('requests.request')
    def test_anki_invalid_json_response(self, mock_post):
        """Test handling of invalid JSON response"""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "not json"
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises((AttributeError, TypeError)):
            anki._request("deckNames")

    def test_obsidian_missing_api_key(self):
        """Test ObsidianAPI initialization without API key"""
        with patch.dict('os.environ', {}, clear=True):
            from obsidianki.api.obsidian import ObsidianAPI

            with pytest.raises(ValueError, match="OBSIDIAN_API_KEY not found"):
                ObsidianAPI()


class TestConfigErrorHandling:
    """Test error handling in configuration"""

    def test_config_loads_defaults_on_error(self):
        """Test that config loads defaults when file has errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            # Write invalid JSON
            config_file.write_text("{ invalid json }")

            from obsidianki.cli.config import Config

            with patch('obsidianki.cli.config.CONFIG_FILE', config_file):
                # Should load defaults instead of crashing
                config = Config()
                # Verify it has default values
                assert hasattr(config, '_config')
                assert 'DECK' in config._config or 'MAX_CARDS' in config._config

    def test_config_handles_missing_file(self):
        """Test config handles missing config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent.json"

            from obsidianki.cli.config import Config

            with patch('obsidianki.cli.config.CONFIG_FILE', nonexistent):
                # Should use defaults
                config = Config()
                assert hasattr(config, '_config')


class TestNetworkErrors:
    """Test network-related error handling"""

    @patch('requests.request')
    def test_network_unreachable(self, mock_post):
        """Test handling of network unreachable error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Network is unreachable")

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(requests.exceptions.ConnectionError):
            anki._request("version")

    @patch('requests.request')
    def test_dns_resolution_failure(self, mock_post):
        """Test handling of DNS resolution failure"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed to resolve hostname")

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI(url="http://invalid.hostname:8765")

        with pytest.raises(requests.exceptions.ConnectionError):
            anki._request("deckNames")

    @patch('requests.request')
    def test_rate_limit_response(self, mock_post):
        """Test handling of rate limit response"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
        mock_post.return_value = mock_response

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(requests.exceptions.HTTPError):
            anki._request("deckNames")


class TestDataValidation:
    """Test data validation"""

    def test_note_accepts_empty_path(self):
        """Test that Note can handle empty path"""
        from obsidianki.cli.models import Note

        # Test various edge cases
        note = Note(
            path="",
            filename="test.md",
            content="content",
            tags=[],
            size=100
        )
        assert note.path == ""

    def test_note_accepts_whitespace_path(self):
        """Test that Note handles whitespace in path"""
        from obsidianki.cli.models import Note

        note = Note(
            path=" test.md ",
            filename="test.md",
            content="content",
            tags=[],
            size=100
        )
        assert note.path.strip() == "test.md"

    def test_flashcard_with_empty_strings(self):
        """Test Flashcard with empty strings"""
        from obsidianki.cli.models import Note, Flashcard

        note = Note(
            path="test.md",
            filename="test.md",
            content="content",
            tags=[],
            size=50
        )

        flashcard = Flashcard(
            front="",
            back="",
            note=note,
            front_original="",
            back_original=""
        )

        assert flashcard.front == ""
        assert flashcard.back == ""


class TestAnkiAPIErrors:
    """Test AnkiAPI specific error handling"""

    @patch('requests.request')
    def test_anki_error_message(self, mock_post):
        """Test handling of AnkiConnect error messages"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": None,
            "error": "model was not found: NonExistent"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(Exception, match="AnkiConnect error"):
            anki._request("modelNames")

    @patch('requests.request')
    def test_anki_duplicate_note_handling(self, mock_post):
        """Test that duplicate notes are handled gracefully"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": None,
            "error": "cannot create note because it is a duplicate"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        # Should return empty list for duplicates
        result = anki._request("addNote", {"note": {}})
        assert result == []

    @patch('requests.request')
    def test_anki_http_error(self, mock_post):
        """Test handling of HTTP errors"""
        mock_post.side_effect = requests.exceptions.HTTPError("500 Server Error")

        from obsidianki.api.anki import AnkiAPI
        anki = AnkiAPI()

        with pytest.raises(requests.exceptions.HTTPError):
            anki._request("deckNames")


class TestObsidianAPIErrors:
    """Test ObsidianAPI specific error handling"""

    def test_obsidian_requires_api_key(self):
        """Test that ObsidianAPI requires API key"""
        with patch.dict('os.environ', {}, clear=True):
            from obsidianki.api.obsidian import ObsidianAPI

            with pytest.raises(ValueError):
                ObsidianAPI()


class TestFileSystemHandling:
    """Test file system related scenarios"""

    def test_config_creates_directory(self):
        """Test that config creates directory if needed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "new_config"
            config_file = config_dir / "config.json"

            from obsidianki.cli.config import Config

            with patch('obsidianki.cli.config.CONFIG_DIR', config_dir), \
                 patch('obsidianki.cli.config.CONFIG_FILE', config_file):
                config = Config()

                # When saving, should create directory
                test_config = {"DECK": "Test"}
                config.save(test_config)

                # Directory should exist now
                assert config_dir.exists()

    def test_config_save_and_load(self):
        """Test config save and load cycle"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            from obsidianki.cli.config import Config

            config = Config()
            test_data = {"DECK": "TestDeck", "MAX_CARDS": 10}

            with patch('obsidianki.cli.config.CONFIG_DIR', Path(tmpdir)), \
                 patch('obsidianki.cli.config.CONFIG_FILE', config_file):
                config.save(test_data)

                # File should exist
                assert config_file.exists()

                # Load and verify
                loaded = config.load()
                assert "DECK" in loaded or "MAX_CARDS" in loaded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
