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