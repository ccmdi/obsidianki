"""Tests for IndentedConsole."""

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO

from rich.console import Console
from obsidianki.cli.config import IndentedConsole


class TestIndentedConsole:
    """Tests for the IndentedConsole class."""

    @pytest.fixture
    def console(self):
        """Create an IndentedConsole for testing."""
        base = Console(file=StringIO(), force_terminal=True)
        return IndentedConsole(base)

    def test_initial_level_is_zero(self, console):
        """Initial indent level should be 0."""
        assert console._level == 0

    def test_initial_prefix_is_empty(self, console):
        """Initial prefix should be empty string."""
        assert console.prefix == ""

    def test_indent_increases_level(self, console):
        """indent() should increase the level."""
        assert console._level == 0
        with console.indent():
            assert console._level == 1

    def test_indent_decreases_on_exit(self, console):
        """Level should decrease when exiting indent context."""
        with console.indent():
            assert console._level == 1
        assert console._level == 0

    def test_nested_indent(self, console):
        """Nested indents should accumulate."""
        assert console._level == 0
        with console.indent():
            assert console._level == 1
            with console.indent():
                assert console._level == 2
                with console.indent():
                    assert console._level == 3
                assert console._level == 2
            assert console._level == 1
        assert console._level == 0

    def test_indent_multiple_levels(self, console):
        """indent() can increase by multiple levels at once."""
        with console.indent(levels=3):
            assert console._level == 3
        assert console._level == 0

    def test_prefix_reflects_level(self, console):
        """Prefix should be indent_str repeated by level."""
        assert console.prefix == ""
        with console.indent():
            assert console.prefix == "   "
            with console.indent():
                assert console.prefix == "      "

    def test_custom_indent_string(self):
        """Can use custom indent string."""
        base = Console(file=StringIO())
        console = IndentedConsole(base, indent_str="\t")

        assert console.prefix == ""
        with console.indent():
            assert console.prefix == "\t"
            with console.indent():
                assert console.prefix == "\t\t"

    def test_print_adds_prefix(self, console):
        """print() should prepend the current prefix."""
        output = StringIO()
        base = Console(file=output, force_terminal=False, width=200)
        console = IndentedConsole(base)

        console.print("Level 0")
        with console.indent():
            console.print("Level 1")

        result = output.getvalue()
        assert "Level 0" in result
        assert "   Level 1" in result

    def test_print_with_no_args(self, console):
        """print() with no args should still work."""
        # Should not raise
        console.print()

    def test_indent_context_handles_exceptions(self, console):
        """Level should decrease even if exception occurs."""
        try:
            with console.indent():
                assert console._level == 1
                raise ValueError("Test error")
        except ValueError:
            pass

        assert console._level == 0

    def test_input_adds_prefix(self):
        """input() should prepend prefix to prompt."""
        base = MagicMock(spec=Console)
        base.input = MagicMock(return_value="user input")
        console = IndentedConsole(base)

        with console.indent():
            result = console.input("Enter: ")

        base.input.assert_called_once_with("   Enter: ")
        assert result == "user input"

    def test_getattr_delegates_to_base(self):
        """Unknown attributes should delegate to base console."""
        base = MagicMock(spec=Console)
        base.some_method = MagicMock(return_value="result")
        console = IndentedConsole(base)

        result = console.some_method("arg")

        base.some_method.assert_called_once_with("arg")
        assert result == "result"


class TestIndentedConsoleStatus:
    """Tests for the status spinner functionality."""

    @pytest.fixture
    def console(self):
        """Create an IndentedConsole for testing."""
        base = Console(file=StringIO(), force_terminal=True)
        return IndentedConsole(base)

    @patch('obsidianki.cli.config.CONFIG')
    @patch('obsidianki.ai.models.MODEL_MAP', {
        "Claude Sonnet 4.5": {"provider": "anthropic"}
    })
    @patch('obsidianki.ai.models.PROVIDER_COLORS', {
        "anthropic": "#D97757"
    })
    def test_status_returns_live_context(self, mock_config, console):
        """status() should return a Live context manager."""
        mock_config.model = "Claude Sonnet 4.5"

        status = console.status("Loading...")

        # Should be a Live instance (context manager)
        assert hasattr(status, '__enter__')
        assert hasattr(status, '__exit__')

    @patch('obsidianki.cli.config.CONFIG')
    @patch('obsidianki.ai.models.MODEL_MAP', {
        "Claude Sonnet 4.5": {"provider": "anthropic"}
    })
    @patch('obsidianki.ai.models.PROVIDER_COLORS', {
        "anthropic": "#D97757"
    })
    def test_status_spinner_frames_include_indent(self, mock_config, console):
        """Spinner frames should include the current indent prefix."""
        mock_config.model = "Claude Sonnet 4.5"

        with console.indent():
            status = console.status("Loading...")
            # Access the spinner through the Live object
            spinner = status.renderable
            # Each frame should start with indent
            for frame in spinner.frames:
                assert frame.startswith("   ")

    @patch('obsidianki.cli.config.CONFIG')
    @patch('obsidianki.ai.models.MODEL_MAP', {
        "GPT-5": {"provider": "openai"}
    })
    @patch('obsidianki.ai.models.PROVIDER_COLORS', {
        "openai": "#10A37F"
    })
    def test_status_color_from_provider(self, mock_config, console):
        """Status spinner should use provider color."""
        mock_config.model = "GPT-5"

        status = console.status("Loading...")
        spinner = status.renderable

        # Spinner style should be the provider color
        assert spinner.style == "#10A37F"

    @patch('obsidianki.cli.config.CONFIG')
    @patch('obsidianki.ai.models.MODEL_MAP', {})
    @patch('obsidianki.ai.models.PROVIDER_COLORS', {})
    def test_status_defaults_to_white(self, mock_config, console):
        """Unknown model should default to white color."""
        mock_config.model = "Unknown Model"

        status = console.status("Loading...")
        spinner = status.renderable

        assert spinner.style == "white"
