import base64
from urlextract import URLExtract
from urllib.parse import urlparse

extractor = URLExtract()


def clean_text(data):
    """Decodes base64url encoded string."""
    if not data:
        return ""
    clean_data = data.replace("-", "+").replace("_", "/")
    return base64.b64decode(clean_data).decode('utf-8')


def clean_urls(text: str) -> str:
    urls = extractor.find_urls(text)

    for url in urls:
        domain = urlparse(url).netloc
        replacement = f"[LINK: {domain}]"
        text = text.replace(url, replacement)

    return text


def format_messages(messages: list) -> str:
    """Convert LangChain messages into a readable conversation string."""
    lines = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))
        if role == "human":
            lines.append(f"User: {content}")
        elif role == "ai":
            lines.append(f"Assistant: {content}")
        elif role == "tool":
            lines.append(f"[Tool Output]: {content[:200]}")
    return "\n".join(lines)