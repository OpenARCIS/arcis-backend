import base64

from aiogoogle import Aiogoogle
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from panda.core.external_api.google import GoogleAPI, NotDoneGoogleAuthentication
from panda.utils.text import clean_text, clean_urls



class GmailAPI(GoogleAPI):
    async def load_creds(self):
        self.client_creds = GoogleAPI.load_client_creds()

        # user creds failing is acceptable
        try:
            self.user_cred = await GoogleAPI.load_user_creds()
        except NotDoneGoogleAuthentication:
            print("GMAIL: Failed to load User credentials")
            self.user_cred = None


    @staticmethod
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


    def _create_message(self, sender, to, subject, message_text):
        """Creates a MIME message and encodes it for the Gmail API."""
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject

        msg = MIMEText(message_text)
        message.attach(msg)

        raw = base64.urlsafe_b64encode(message.as_bytes())
        return {'raw': raw.decode()}


    async def get_n_mails(self, n: int):
        email_list = []
        try:
            async with Aiogoogle(client_creds=self.client_creds, user_creds=self.user_cred) as aiogoogle:
                gmail = await aiogoogle.discover('gmail', 'v1')
                
                response = await aiogoogle.as_user(
                    gmail.users.messages.list(
                        userId='me',
                        labelIds=['INBOX'],
                        q='is:unread category:primary',
                        maxResults=n
                    )
                )
                
                messages = response.get('messages', [])
                
                if messages:
                    for msg_summary in messages:
                        msg_id = msg_summary['id']

                        #if await is_message_processed(msg_id): 
                            #continue

                        full_msg = await aiogoogle.as_user(
                            gmail.users.messages.get(
                                userId='me', 
                                id=msg_id
                            )
                        )

                        headers = full_msg['payload']['headers']
                        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                        body = self._extract_message_text(full_msg['payload'])

                        email_obj = {
                            "id": msg_id,
                            "sender": sender,
                            "subject": subject,
                            "body": body
                        }
                        email_list.append(email_obj)
                        
                        #await mark_message_as_processed(msg_id)
                
                else:
                    print("No new mail.")
            
            return email_list

        except Exception as e:
            print(f"Error during polling: {e}")
            return []


    async def search_email(self, query: str, max_results: int = 5):
        """
        Searches for emails based on a query string (e.g., 'from:boss subject:urgent').
        """
        async with Aiogoogle(client_creds=self.client_creds, user_creds=self.user_cred) as aiogoogle:
            gmail = await aiogoogle.discover('gmail', 'v1')

            response = await aiogoogle.as_user(
                gmail.users.messages.list(
                    userId='me',
                    q=query,
                    maxResults=max_results
                )
            )

            messages = response.get('messages', [])
            results = []

            if messages:
                for msg_summary in messages:
                    full_msg = await aiogoogle.as_user(
                        gmail.users.messages.get(
                            userId='me',
                            id=msg_summary['id']
                        )
                    )

                    headers = full_msg['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                    
                    body = self._extract_message_text(full_msg['payload'])

                    results.append({
                        "id": msg_summary['id'],
                        "sender": sender,
                        "subject": subject,
                        "body": body
                    })
            
            return results

    
    async def send_email(self, to: str, subject: str, body: str):
        """
        Sends an email immediately.
        """
        # Create the payload
        # Note: 'me' is used as sender, Gmail API resolves this to the authenticated user
        message_payload = self._create_message('me', to, subject, body)

        async with Aiogoogle(client_creds=self.client_creds, user_creds=self.user_cred) as aiogoogle:
            gmail = await aiogoogle.discover('gmail', 'v1')

            try:
                sent_message = await aiogoogle.as_user(
                    gmail.users.messages.send(userId='me', json=message_payload)
                )
                return sent_message
            except Exception as e:
                print(f"An error occurred sending email: {e}")
                return None


    async def draft_email(self, to: str, subject: str, body: str):
        """
        Creates a draft email but does not send it.
        """

        message_payload = {
            'message': self._create_message('me', to, subject, body)
        }

        async with Aiogoogle(client_creds=self.client_creds, user_creds=self.user_cred) as aiogoogle:
            gmail = await aiogoogle.discover('gmail', 'v1')

            try:
                draft = await aiogoogle.as_user(
                    gmail.users.drafts.create(userId='me', json=message_payload)
                )
                print(f"Draft created with ID: {draft['id']}")
                return draft
            except Exception as e:
                print(f"An error occurred creating draft: {e}")
                return None


gmail_api = GmailAPI()