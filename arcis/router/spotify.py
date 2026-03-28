from fastapi import APIRouter, Request, HTTPException
from datetime import datetime

from arcis.core.external_api.spotify import spotify_api
from arcis.database.mongo.connection import mongo, COLLECTIONS

spotify_router = APIRouter()


@spotify_router.get("/spotify/auth/login")
async def login():
    """
    Generates the Spotify Login URL.
    """
    # Provide a state string for security (optional but recommended)
    uri = spotify_api.get_auth_url(state="some_secure_state_string")
    return {"auth_url": uri}


@spotify_router.get("/spotify/auth/callback")
async def callback(request: Request):
    """
    Exchanges the auth code for user credentials asynchronously and saves to MongoDB.
    """
    code = request.query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="No code found")

    try:
        # Exchange the code for tokens. The `SpotifyAPI` class handles 
        # saving the credentials to MongoDB under "spotify_credentials".
        result = await spotify_api.exchange_code(code)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # We can also update an auth timestamp if needed.
        await mongo.db[COLLECTIONS['users']].update_one(
            {"username": "test_user"}, 
            {
                "$set": {
                    "spotify_auth_updated_at": datetime.now()
                }
            },
            upsert=True
        )

        return {"message": "Authentication successful! Credentials saved for test_user."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auth flow failed: {str(e)}")


@spotify_router.get("/spotify/auth/status")
async def auth_status():
    """
    Checks if the user is authenticated with Spotify.
    """
    user = await mongo.db[COLLECTIONS['users']].find_one({"username": "test_user"})
    if user and "spotify_credentials" in user:
        return True
    return False


@spotify_router.get("/spotify/auth/logout")
async def logout():
    """
    Logs out the user by removing Spotify credentials from the database.
    """
    await mongo.db[COLLECTIONS['users']].update_one(
        {"username": "test_user"},
        {"$unset": {"spotify_credentials": "", "spotify_auth_updated_at": ""}}
    )
    
    # Reload the credentials into the application global instance to clear them
    try:
        await spotify_api.load_creds()
    except Exception:
        # SpotifyAuthError will be raised since creds are deleted, which is expected
        pass

    return {"message": "Logged out successfully"}
