import json

from abc import ABC

from panda import Config
from panda.models.errors import NotDoneGoogleAuthentication
from panda.database.mongo.connection import mongo, COLLECTIONS
 

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose"
]


class GoogleAPI(ABC):
    client_creds: dict

    @staticmethod
    def load_client_creds():
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


    @staticmethod
    async def load_user_creds(username: str = 'test_user'):
        """
        Get user JSON data from mongo db.

        Returns:
            json_data
        """
        user = await mongo.db[COLLECTIONS['users']].find_one({'username': username})
        if not user:
            raise NotDoneGoogleAuthentication

        creds = user.get('gmail_credentials')
        if not creds:
            raise NotDoneGoogleAuthentication

        return creds