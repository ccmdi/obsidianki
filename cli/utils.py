import re

# TODO: unused
def strip_html_for_terminal(text: str) -> str:
    """Strip HTML tags for cleaner terminal display"""
    # Remove HTML tags but keep the content
    text = re.sub(r'<[^>]+>', '', text)
    # Convert HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return text

def process_code_blocks(text: str, enable_syntax_highlighting: bool = True) -> str:
    """Convert markdown code blocks to HTML, optionally with syntax highlighting"""
    if not enable_syntax_highlighting:
        # Simple conversion without syntax highlighting
        text = re.sub(r'```([^`]+)```', r'<code>\1</code>', text)
        return text

    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, ClassNotFound
        from pygments.formatters import HtmlFormatter

        def replace_code_block(match):
            full_content = match.group(1)
            lines = full_content.split('\n')

            # Check if first line is a language identifier
            if lines and lines[0].strip() and not ' ' in lines[0].strip():
                language = lines[0].strip()
                code_content = '\n'.join(lines[1:])
            else:
                language = 'text'
                code_content = full_content

            try:
                lexer = get_lexer_by_name(language)
                formatter = HtmlFormatter(
                    style='monokai',
                    noclasses=True,
                    cssclass='highlight'
                )
                highlighted = highlight(code_content, lexer, formatter)
                return highlighted
            except ClassNotFound:
                # Fallback to simple code tag if language not found
                return f'<code>{code_content}</code>'

        # Replace triple backticks with syntax highlighted HTML
        text = re.sub(r'```([^`]+)```', replace_code_block, text, flags=re.DOTALL)
        return text

    except ImportError:
        # Fallback to simple code tags if Pygments not available
        text = re.sub(r'```([^`]+)```', r'<code>\1</code>', text)
        return text