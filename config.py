import os
from os import getenv
from dotenv import load_dotenv

if not os.environ.get("ENV"):
    load_dotenv('.env', override=True)

class Config(object):
    try: 
        DATABASE_URL = getenv("DATABASE_URL")
        DATABASE_NAME = getenv("DATABASE_NAME", 'panda_db')
    except:
        print("CORE : Essential Configs are missing")
        exit(1)

    GEMINI_API = getenv('GEMINI_API')

    OAUTHLIB_INSECURE_TRANSPORT = getenv('OAUTHLIB_INSECURE_TRANSPORT', 1) # only for local testing
    GOOGLE_CLIENT_SECRETS_FILE = getenv('CLIENT_SECRETS_FILE', 'gmail_secret.json')
    GOOGLE_REDIRECT_URI = getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/')
