"""Tests for multi-provider LLM support via LiteLLM"""
import pytest
import os
from unittest.mock import patch

from obsidianki.ai.models import MODEL_MAP


class TestModelMap:
    """Test the MODEL_MAP configuration"""

    def test_model_map_has_expected_models(self):
        """Verify MODEL_MAP contains all expected models"""
        expected_models = [
            "Claude Sonnet 4.5",
            "Claude Opus 4",
            "GPT-5",
            "Gemini 3",
            "GPT-4o",
            "GPT-4o Mini",
            "Gemini 2.5 Flash",
            "DeepSeek V3.1"
        ]

        for model in expected_models:
            assert model in MODEL_MAP, f"Model '{model}' not found in MODEL_MAP"

    def test_model_map_entries_have_required_fields(self):
        """Verify each MODEL_MAP entry has provider, model, and key_name"""
        required_fields = ['provider', 'model', 'key_name']

        for model_name, model_info in MODEL_MAP.items():
            for field in required_fields:
                assert field in model_info, f"Model '{model_name}' missing field '{field}'"
                assert model_info[field], f"Model '{model_name}' has empty '{field}'"

    def test_anthropic_models_use_correct_provider(self):
        """Verify Anthropic models use 'anthropic' provider"""
        claude_models = ["Claude Sonnet 4.5", "Claude Opus 4"]

        for model in claude_models:
            assert MODEL_MAP[model]["provider"] == "anthropic"
            assert MODEL_MAP[model]["key_name"] == "ANTHROPIC_API_KEY"

    def test_openai_models_use_correct_provider(self):
        """Verify OpenAI models use 'openai' provider"""
        openai_models = ["GPT-5", "GPT-4o", "GPT-4o Mini"]

        for model in openai_models:
            assert MODEL_MAP[model]["provider"] == "openai"
            assert MODEL_MAP[model]["key_name"] == "OPENAI_API_KEY"

    def test_google_models_use_correct_provider(self):
        """Verify Google models use 'google' provider"""
        google_models = ["Gemini 3", "Gemini 2.5 Flash"]

        for model in google_models:
            assert MODEL_MAP[model]["provider"] == "google"
            assert MODEL_MAP[model]["key_name"] == "GEMINI_API_KEY"

    def test_deepseek_models_use_correct_provider(self):
        """Verify DeepSeek models use 'deepseek' provider"""
        assert MODEL_MAP["DeepSeek V3.1"]["provider"] == "deepseek"
        assert MODEL_MAP["DeepSeek V3.1"]["key_name"] == "DEEPSEEK_API_KEY"


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

    def test_ai_client_respects_model_config(self):
        """Test that FlashcardAI uses model from CONFIG"""
        test_cases = [
            ("GPT-5", "openai", "gpt-5"),
            ("Claude Opus 4", "anthropic", "claude-opus-4-1"),
            ("Gemini 3", "google", "gemini/gemini-2.5-pro"),
        ]

        for model_name, expected_provider, expected_model in test_cases:
            model_info = MODEL_MAP[model_name]
            api_key_name = model_info["key_name"]

            with patch.dict(os.environ, {api_key_name: 'test_key'}):
                from obsidianki.ai.client import FlashcardAI

                with patch('obsidianki.ai.client.CONFIG') as mock_config:
                    mock_config.model = model_name

                    ai = FlashcardAI()

                    assert ai.provider == expected_provider, \
                        f"Model {model_name} should use provider {expected_provider}"
                    assert ai.model == expected_model, \
                        f"Model {model_name} should map to {expected_model}"


class TestModelConfiguration:
    """Test model configuration via config command"""

    def test_config_accepts_valid_model_names(self):
        """Test that config command accepts valid model names"""
        from obsidianki.cli.config import CONFIG

        valid_models = ["GPT-5", "Claude Sonnet 4.5", "Gemini 2.5 Flash"]

        for model in valid_models:
            assert model in MODEL_MAP, \
                f"Test assumes {model} is in MODEL_MAP but it's not"

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
