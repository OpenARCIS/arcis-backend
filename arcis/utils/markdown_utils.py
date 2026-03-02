import re

def escape_markdown(text: str) -> str:
    """
    Escapes characters that are reserved in Telegram's MarkdownV2 syntax.
    """
    if not text:
        return ""

    # Characters that need escaping in MarkdownV2 outside of pre/code blocks
    # Note: this is a basic implementation. A perfect one requires parsing the MD fully.
    reserved_chars = [
        "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"
    ]
    
    # We use a backslash to escape, but re.sub needs it double-escaped or we can just iterate.
    # The pattern matches any of the reserved characters
    pattern = r"([_*\[\]()~`>#\+\-=|{}\.!])"
    
    # Simple replace for now, though it might break existing valid markdown.
    # A more robust solution would be preferable eventually, but Pyrogram often fails
    # if ANY of these are unescaped outside of a proper syntax block.
    
    # For a safer initial approach that won't destroy actual bold/italic formatting, 
    # we might only escape the most problematic ones that users type normally.
    # But for Telegram V2 strictly, everything needs escaping. Let's do a strict escape for now.
    
    # Let's try to only escape characters that aren't already part of MD structure
    # This is a complex problem. A simple fallback is to just escape everything
     
    return re.sub(pattern, r"\\\1", text)
