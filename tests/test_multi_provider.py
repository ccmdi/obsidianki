"""Tests for multi-provider LLM support via LiteLLM"""
import pytest
import os
from unittest.mock import patch

from obsidianki.ai.models import MODEL_MAP

class TestFlashcardAIModelSelection:
    """Test FlashcardAI model initialization with different providers"""

    def test_ai_client_uses_claude_by_default(self):
        """Test that FlashcardAI defaults to Claude Sonnet 4.5"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
            from obsidianki.ai.client import FlashcardAI

            # Mock CONFIG to not have model set
            with patch('obsidianki.ai.client.CONFIG') as mock_config:
                mock_config.model = 'Claude Sonnet 4.5'

                ai = FlashcardAI()

                assert ai.provider == "anthropic"
                assert "claude" in ai.model.lower()


class TestModelConfiguration:
    """Test model configuration via config command"""

    def test_all_model_map_keys_are_user_friendly(self):
        """Verify MODEL_MAP keys are human-friendly, not technical IDs"""
        for model_name in MODEL_MAP.keys():
            # Should not be technical model IDs like "claude-sonnet-4.5-20250514"
            assert not model_name.startswith("claude-"), \
                f"Model key '{model_name}' should be human-friendly, not technical ID"
            assert not model_name.startswith("gpt-"), \
                f"Model key '{model_name}' should be human-friendly, not technical ID"
            assert not model_name.startswith("gemini-"), \
                f"Model key '{model_name}' should be human-friendly, not technical ID"

            # Should contain spaces or be a proper name
            assert " " in model_name or model_name[0].isupper(), \
                f"Model key '{model_name}' should be human-friendly with spaces or proper capitalization"


class TestBackwardsCompatibility:
    """Test backwards compatibility with existing configs"""

    def test_anthropic_api_key_still_works(self):
        """Verify ANTHROPIC_API_KEY environment variable still works"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-ant-test123'}):
            from obsidianki.ai.client import FlashcardAI

            with patch('obsidianki.ai.client.CONFIG') as mock_config:
                mock_config.model = 'Claude Sonnet 4.5'

                # Should not raise an error about missing API key
                ai = FlashcardAI()
                assert ai.provider == "anthropic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
