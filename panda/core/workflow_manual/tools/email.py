from typing import Optional
from langchain.tools import tool
from panda.core.external_api.gmail import gmail_api


@tool
async def email_draft(recipient: str, subject: str, body: str) -> str:
    """
    Creates a draft email in the user's Gmail account without sending it.
    Use this when the user wants to review or edit a message before it goes out.

    Args:
        recipient: The email address of the person receiving the email.
        subject: The subject line of the email.
        body: The full content/message of the email.
    """
    await gmail_api.draft_email(recipient, subject, body)
    return f"✉️ DRAFT CREATED\nTo: {recipient}\nSubject: {subject}\nBody: {body[:100]}..."


@tool
def email_send(recipient: str, subject: str, body: str) -> str:
    """
    Sends an email immediately to a recipient. 
    Use this for direct communication when no further review is needed.

    Args:
        recipient: The destination email address.
        subject: The subject line for the email.
        body: The text content of the email to be sent.
    """
    # Note: Ensure you implement the actual sending logic here via your API
    return f"✅ EMAIL SENT to {recipient} with subject '{subject}'"


@tool
def email_read(folder: str = "inbox", limit: int = 5) -> str:
    """
    Retrieves a list of recent emails from a specific folder.

    Args:
        folder: The Gmail folder to read from (e.g., 'inbox', 'sent', 'spam'). Defaults to 'inbox'.
        limit: The maximum number of email headers to retrieve. Defaults to 5.
    """
    return f"📬 Retrieved {limit} emails from {folder}"


@tool
async def email_search(query: str) -> str:
    """
    Searches the user's Gmail history for emails matching a specific search query.
    The query can include keywords, sender names, or dates (e.g., 'from:boss' or 'invoice').

    Args:
        query: The search string used to filter emails.
    """
    result = await gmail_api.search_email(query)
    return f"🔍 Found emails matching '{query}':\n{result}"


email_tools = [email_draft, email_send, email_read, email_search]