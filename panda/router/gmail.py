from fastapi import APIRouter, Request, HTTPException
from aiogoogle import Aiogoogle
from datetime import datetime

from panda.core.external_api.google import SCOPES, GoogleAPI
from panda.database.mongo.connection import mongo, COLLECTIONS

gmail_router = APIRouter()


@gmail_router.get("/gmail/auth/login")
async def login():
    """
    Generates the Google Login URL using Aiogoogle.
    """
    aiogoogle = Aiogoogle(client_creds=GoogleAPI.load_client_creds())
    
    # Generate the authorization URL
    uri = aiogoogle.oauth2.authorization_url(
        client_creds=GoogleAPI.load_client_creds(),
        state="some_secure_state_string",
        access_type="offline",
        include_granted_scopes=True,
        prompt="consent",
        scopes=SCOPES
    )
    
    return {"auth_url": uri}


@gmail_router.get("/gmail/auth/callback")
async def callback(request: Request):
    """
    Exchanges the auth code for user credentials asynchronously and saves to MongoDB.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state") 

    if not code:
        raise HTTPException(status_code=400, detail="No code found")

    try:
        aiogoogle = Aiogoogle(client_creds=GoogleAPI.load_client_creds())

        user_creds = await aiogoogle.oauth2.build_user_creds(
            grant=code,
            client_creds=GoogleAPI.load_client_creds(),
        )
        
        await mongo.db[COLLECTIONS['users']].update_one(
            {"username": "test_user"}, 
            {
                "$set": {
                    "gmail_credentials": user_creds,
                    "auth_updated_at": datetime.now()
                }
            },
            upsert=True
        )

        return {"message": "Authentication successful! Credentials saved for test_user."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auth flow failed: {str(e)}")


@gmail_router.get("/gmail/auth/status")
async def auth_status():
    """
    Checks if the user is authenticated with Google.
    """
    user = await mongo.db[COLLECTIONS['users']].find_one({"username": "test_user"})
    if user and "gmail_credentials" in user:
        return True
    return False


@gmail_router.get("/gmail/auth/logout")
async def logout():
    """
    Logs out the user by removing Gmail credentials from the database.
    """
    await mongo.db[COLLECTIONS['users']].update_one(
        {"username": "test_user"},
        {"$unset": {"gmail_credentials": "", "auth_updated_at": ""}}
    )
    return {"message": "Logged out successfully"}

