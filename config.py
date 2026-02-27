import os
from os import getenv
from dotenv import load_dotenv

if not os.environ.get("ENV"):
    load_dotenv('.env', override=True)

class Config:
    DATABASE_URL = getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("CORE : Essential Configs (DATABASE_URL) are missing")
        exit(1)

    DATABASE_NAME = getenv("DATABASE_NAME", 'arcis_db')

    GEMINI_API = getenv('GEMINI_API')
    OPENROUTER_API_KEY = getenv("OPENROUTER_API_KEY")

    OAUTHLIB_INSECURE_TRANSPORT = getenv('OAUTHLIB_INSECURE_TRANSPORT', 1) # only for local testing
    GOOGLE_CLIENT_SECRETS_FILE = getenv('CLIENT_SECRETS_FILE', 'google_credentials.json')
    GOOGLE_REDIRECT_URI = getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/')

    MISTRAL_API_KEY = getenv("MISTRAL_API_KEY")
    CEREBRAS_API_KEY = getenv("CEREBRAS_API_KEY")
    GROQ_API_KEY = getenv("GROQ_API_KEY")

    # Qdrant (Long-Term Memory)
    QDRANT_URL = getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = getenv("QDRANT_API_KEY", None)
    EMBEDDING_MODE = getenv("EMBEDDING_MODE", "offline")  # "offline" (FastEmbed) or "online" (Gemini)

    # TTS Config
    TTS_DEFAULT_VOICE = getenv("TTS_DEFAULT_VOICE", "alba")
