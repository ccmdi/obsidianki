import pytest
import sys
import importlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.mocks.dummy_ai import DummyFlashcardAI
from tests.mocks.dummy_obsidian import DummyObsidianAPI
from tests.mocks.dummy_anki import DummyAnkiAPI

@pytest.fixture
def mock_services(monkeypatch):
    """Set up mock services before each test"""
    monkeypatch.setenv("OBSIDIAN_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

    import obsidianki.cli.services

    # Store originals
    original_ai = obsidianki.cli.services.AI
    original_obsidian = obsidianki.cli.services.OBSIDIAN
    original_anki = obsidianki.cli.services.ANKI

    # Replace with mocks
    obsidianki.cli.services.AI = DummyFlashcardAI()
    obsidianki.cli.services.OBSIDIAN = DummyObsidianAPI()
    obsidianki.cli.services.ANKI = DummyAnkiAPI()

    if 'obsidianki.cli.processors' in sys.modules:
        importlib.reload(sys.modules['obsidianki.cli.processors'])
    if 'obsidianki.main' in sys.modules:
        importlib.reload(sys.modules['obsidianki.main'])

    yield

    # Restore originals
    obsidianki.cli.services.AI = original_ai
    obsidianki.cli.services.OBSIDIAN = original_obsidian
    obsidianki.cli.services.ANKI = original_anki


@pytest.fixture
def clean_temp_config():
    """Create a temporary directory for fresh config setup"""
    import obsidianki.cli.config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "config.json"
        env_file = config_dir / ".env"
        history_file = config_dir / "processing_history.json"
        tags_file = config_dir / "tags.json"
        templates_file = config_dir / "templates.json"

        # Patch config paths
        with patch('obsidianki.cli.config.CONFIG_DIR', config_dir), \
             patch('obsidianki.cli.config.CONFIG_FILE', config_file), \
             patch('obsidianki.cli.config.ENV_FILE', env_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history_file', history_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'processing_history', {}), \
             patch.object(obsidianki.cli.config.CONFIG, 'tag_schema_file', tags_file), \
             patch.object(obsidianki.cli.config.CONFIG, 'templates_file', templates_file):
            yield {
                'config_dir': config_dir,
                'config_file': config_file,
                'env_file': env_file,
                'history_file': history_file,
                'tags_file': tags_file,
                'templates_file': templates_file
            }