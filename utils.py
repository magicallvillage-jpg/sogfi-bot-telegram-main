import re

def escape_markdownv2(text):
    """
    Escapes all reserved characters for Telegram MarkdownV2.
    
    Args:
        text: The text to escape (converted to string if not already).
    
    Returns:
        str: Text with all reserved characters escaped.
    """
    if not isinstance(text, str):
        text = str(text)  # Handle non-string inputs like None or numbers
    reserved_chars = r'([_\*\[\]\(\)\~`>#\+\-=|{}\.!])'
    return re.sub(reserved_chars, r'\\\1', text)
