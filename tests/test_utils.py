"""Test utility functions"""
import pytest
from obsidianki.cli.utils import strip_html, process_code_blocks, encode_path


class TestStripHTML:
    """Test strip_html function"""

    def test_strip_simple_tags(self):
        """Test stripping simple HTML tags"""
        text = "<p>Hello <b>World</b></p>"
        result = strip_html(text)
        assert result == "Hello World"
        assert "<" not in result
        assert ">" not in result

    def test_strip_nested_tags(self):
        """Test stripping nested HTML tags"""
        text = "<div><span><strong>Nested</strong></span></div>"
        result = strip_html(text)
        assert result == "Nested"

    def test_html_entities(self):
        """Test converting HTML entities"""
        text = "Code: &lt;div&gt; &amp; &lt;span&gt;"
        result = strip_html(text)
        assert result == "Code: <div> & <span>"

    def test_no_html(self):
        """Test text without HTML"""
        text = "Plain text with no HTML"
        result = strip_html(text)
        assert result == text

    def test_empty_string(self):
        """Test empty string"""
        result = strip_html("")
        assert result == ""

    def test_complex_html(self):
        """Test complex HTML with attributes"""
        text = '<div class="test" id="main"><a href="link">Click</a></div>'
        result = strip_html(text)
        assert result == "Click"

    def test_self_closing_tags(self):
        """Test self-closing tags"""
        text = "Text with <br/> line break and <img src='test'/> image"
        result = strip_html(text)
        assert "<br/>" not in result
        assert "<img" not in result


class TestProcessCodeBlocks:
    """Test process_code_blocks function"""

    def test_code_block_no_syntax_highlighting(self):
        """Test code block without syntax highlighting"""
        text = "```python\nprint('hello')\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        assert "<code>" in result
        assert "</code>" in result
        assert "```" not in result

    def test_code_block_with_syntax_highlighting(self):
        """Test code block with syntax highlighting"""
        text = "```python\nprint('hello')\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=True)
        # Should contain some HTML from highlighting
        assert "<" in result
        assert ">" in result
        # Original backticks should be gone
        assert "```" not in result

    def test_code_block_unknown_language(self):
        """Test code block with unknown language"""
        text = "```unknownlang\nsome code\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=True)
        # Should fallback to simple code tag
        assert "<code>" in result or "some code" in result

    def test_code_block_no_language(self):
        """Test code block without language specifier"""
        text = "```\nplain code\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=True)
        assert "plain code" in result

    def test_multiple_code_blocks(self):
        """Test multiple code blocks"""
        text = "First ```python\ncode1\n``` and second ```js\ncode2\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        assert result.count("<code>") == 2
        assert result.count("</code>") == 2

    def test_no_code_blocks(self):
        """Test text without code blocks"""
        text = "Regular text without code blocks"
        result = process_code_blocks(text)
        assert result == text

    def test_empty_code_block(self):
        """Test empty code block"""
        text = "```\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        # Should handle gracefully
        assert isinstance(result, str)

    def test_code_block_with_special_chars(self):
        """Test code block with special characters"""
        text = "```python\ndef test():\n    return '<>&'\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        assert "def test()" in result
        assert "<>&" in result


class TestEncodePath:
    """Test encode_path function"""

    def test_encode_simple_path(self):
        """Test encoding simple path"""
        path = "folder/note.md"
        result = encode_path(path)
        assert "/" not in result  # Slashes should be encoded
        assert "folder" in result
        assert "note" in result

    def test_encode_path_with_spaces(self):
        """Test encoding path with spaces"""
        path = "my folder/my note.md"
        result = encode_path(path)
        assert " " not in result  # Spaces should be encoded
        assert "%20" in result

    def test_encode_path_with_special_chars(self):
        """Test encoding path with special characters"""
        path = "folder/note (1).md"
        result = encode_path(path)
        assert "(" not in result
        assert ")" not in result
        assert "%28" in result  # (
        assert "%29" in result  # )

    def test_encode_path_unicode(self):
        """Test encoding path with Unicode characters"""
        path = "folder/文档.md"
        result = encode_path(path)
        # Should be encoded
        assert isinstance(result, str)
        # Original Unicode should be escaped
        assert "文档" not in result or "%" in result

    def test_encode_empty_path(self):
        """Test encoding empty path"""
        result = encode_path("")
        assert result == ""

    def test_encode_path_already_encoded(self):
        """Test encoding already encoded path"""
        path = "folder%2Fnote.md"
        result = encode_path(path)
        # Should encode the % as well
        assert "%25" in result

    def test_encode_path_with_hash(self):
        """Test encoding path with hash"""
        path = "folder/note#heading.md"
        result = encode_path(path)
        assert "#" not in result
        assert "%23" in result


class TestUtilsEdgeCases:
    """Test edge cases for utility functions"""

    def test_strip_html_malformed(self):
        """Test stripping malformed HTML"""
        text = "<div>Unclosed tag"
        result = strip_html(text)
        # Should handle gracefully
        assert isinstance(result, str)
        assert "Unclosed tag" in result

    def test_process_code_blocks_nested_backticks(self):
        """Test code blocks with nested backticks"""
        text = "```python\ncode = '```'\n```"
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        # Should handle gracefully
        assert isinstance(result, str)

    def test_strip_html_only_tags(self):
        """Test stripping HTML that's only tags"""
        text = "<div></div>"
        result = strip_html(text)
        assert result == ""

    def test_encode_path_very_long(self):
        """Test encoding very long path"""
        path = "/".join(["folder"] * 50) + "/note.md"
        result = encode_path(path)
        assert isinstance(result, str)
        assert len(result) > 0


class TestUtilsPerformance:
    """Test performance-related aspects"""

    def test_strip_html_large_text(self):
        """Test stripping HTML from large text"""
        text = "<p>Test</p>" * 1000
        result = strip_html(text)
        assert "Test" in result
        assert "<p>" not in result

    def test_process_code_blocks_many_blocks(self):
        """Test processing many code blocks"""
        text = "```python\ncode\n```\n" * 10
        result = process_code_blocks(text, enable_syntax_highlighting=False)
        # Should handle all blocks
        assert result.count("<code>") == 10

    def test_encode_path_many_special_chars(self):
        """Test encoding path with many special characters"""
        path = "!@#$%^&*()_+-={}[]|:;<>?,./"
        result = encode_path(path)
        # Should encode all special chars
        assert "%" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
