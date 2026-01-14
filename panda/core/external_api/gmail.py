import asyncio
import json

from aiogoogle import Aiogoogle
from datetime import datetime

from panda import Config
from panda.database.mongo.connection import mongo, COLLECTIONS
from panda.utils.text import clean_text, clean_urls

from bs4 import BeautifulSoup

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
]


def _extract_message_text(payload):

    def search_parts(parts, mime_type):
        for part in parts:
            if part['mimeType'] == mime_type:
                return clean_text(part['body'].get('data', ''))
            if 'parts' in part:
                found = search_parts(part['parts'], mime_type)
                if found: return found
        return None

    text_content = None
    if 'parts' in payload:
        text_content = search_parts(payload['parts'], 'text/plain')
    
    if not text_content:
        if payload.get('mimeType') == 'text/html':
            html_content = clean_text(payload['body'].get('data', ''))
        elif 'parts' in payload:
            html_content = search_parts(payload['parts'], 'text/html')
        else:
            html_content = ""
            
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            text_content = soup.get_text(separator=' ')

    if text_content:
        text = " ".join(text_content.split())
        return clean_urls(text)
        
    return ""


async def poll_gmail_updates(username: str): 
    while True:
        try:
            user = await mongo.db[COLLECTIONS['users']].find_one({'username': username})
            if not user:
                break
                
            creds = user.get('gmail_credentials')
            
            # 2. Authenticate
            async with Aiogoogle(client_creds=GmailWrapper.get_client_creds(), user_creds=creds) as aiogoogle:
                gmail = await aiogoogle.discover('gmail', 'v1')
                
                response = await aiogoogle.as_user(
                    gmail.users.messages.list(
                        userId='me',
                        labelIds=['INBOX'],
                        q='is:unread category:primary',
                        maxResults=5
                    )
                )
                
                messages = response.get('messages', [])
                
                if messages:
                    for msg_summary in messages:
                        msg_id = msg_summary['id']

                        if await is_message_processed(msg_id): 
                            continue

                        full_msg = await aiogoogle.as_user(
                            gmail.users.messages.get(
                                userId='me', 
                                id=msg_id
                            )
                        )

                        headers = full_msg['payload']['headers']
                        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                        body = _extract_message_text(full_msg['payload'])

                        email_obj = {
                            "id": msg_id,
                            "sender": sender,
                            "subject": subject,
                            "body": body
                        }
                        print(email_obj)
                        
                        #await mark_message_as_processed(msg_id)
                
                else:
                    print("No new mail.")

        except Exception as e:
            print(f"Error during polling: {e}")
        
        break
        await asyncio.sleep(10) 


async def is_message_processed(email_id):
    doc = await mongo.db[COLLECTIONS['processed_emails']].find_one({'email_id': email_id})
    return doc is not None


async def mark_message_as_processed(email_id):
    await mongo.db[COLLECTIONS['processed_emails']].insert_one({
        'email_id': email_id,
        'processed_at': datetime.utcnow() 
    })


def get_client_creds():
    """
    Get JSON data from google credentials file.

    Returns:
        json_data
    """
    with open(Config.GOOGLE_CLIENT_SECRETS_FILE, "r") as f:
        data = json.load(f)
    
    creds_payload = data.get("web") or data.get("installed")
    
    if not creds_payload:
        raise ValueError("Invalid credentials file: could not find 'web' or 'installed' keys.")

    return {
        "client_id": creds_payload["client_id"],
        "client_secret": creds_payload["client_secret"],
        "scopes": SCOPES,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI
    }