import os
from os import getenv
from dotenv import load_dotenv
from arcis.logger import LOGGER

if not os.environ.get("ENV"):
    load_dotenv('.env', override=True)

class Config:
    DATABASE_URL = getenv("DATABASE_URL")
    if not DATABASE_URL:
        LOGGER.error("CORE : Essential Configs (DATABASE_URL) are missing")
        exit(1)

    DATABASE_NAME = getenv("DATABASE_NAME", 'arcis_db')

    AUTO_CHECK_INTERVAL = getenv("AUTO_CHECK_INTERVAL", 300)

    GEMINI_API = getenv('GEMINI_API')
    OPENROUTER_API_KEY = getenv("OPENROUTER_API_KEY")

    OAUTHLIB_INSECURE_TRANSPORT = getenv('OAUTHLIB_INSECURE_TRANSPORT', 1) # only for local testing
    GOOGLE_CLIENT_SECRETS_FILE = getenv('CLIENT_SECRETS_FILE', 'google_credentials.json')
    GOOGLE_REDIRECT_URI = getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/')

    MISTRAL_API_KEY = getenv("MISTRAL_API_KEY")
    CEREBRAS_API_KEY = getenv("CEREBRAS_API_KEY")
    GROQ_API_KEY = getenv("GROQ_API_KEY")
    NVIDIA_NIM_API_KEY = getenv("NVIDIA_NIM_API_KEY")

    # Qdrant (Long-Term Memory)
    QDRANT_URL = getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = getenv("QDRANT_API_KEY", None)
    EMBEDDING_MODE = getenv("EMBEDDING_MODE", "offline")  # "offline" (FastEmbed) or "online" (Gemini)

    # TTS Config
    TTS_DEFAULT_VOICE = getenv("TTS_DEFAULT_VOICE", "alba")

    # Telegram Config
    TELEGRAM_API_ID = getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = getenv("TELEGRAM_API_HASH")
    TG_BOT_TOKEN = getenv("TG_BOT_TOKEN")
    ALLOWED_TG_USER_ID = getenv("ALLOWED_TG_USER_ID")

    # MCP Config
    MCP_SERVERS_CONFIG_PATH = getenv("MCP_SERVERS_CONFIG_PATH", None)
    MCP_TOOL_THRESHOLD = int(getenv("MCP_TOOL_THRESHOLD", "30"))

    WORK_DIR = getenv("WORK_DIR", "./")

    # Scheduler Config
    SCHEDULER_PREFETCH_LEAD_MINUTES = int(getenv("SCHEDULER_PREFETCH_LEAD_MINUTES", "120"))

    # Recommendation Engine Config
    # How often (in seconds) the autonomous recommendation engine runs.
    # Default: 10800 = 3 hours
    RECOMMENDATION_INTERVAL = int(getenv("RECOMMENDATION_INTERVAL", "10800"))

    # Notification Config — where scheduled job notifications are sent
    # Options: "telegram", "web", "both"
    NOTIFICATION_CHANNEL = getenv("NOTIFICATION_CHANNEL", "both")

    # Spotify Config
    SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/callback/spotify")

    # Brave Search Config
    BRAVE_SEARCH_API_KEY = getenv("BRAVE_SEARCH_API_KEY")

    # TMDB (The Movie Database) Config
    TMDB_API_KEY = getenv("TMDB_API_KEY")

    # Simple Auth config
    AUTH_USERNAME = getenv("AUTH_USERNAME")
    AUTH_PASSWORD = getenv("AUTH_PASSWORD")
