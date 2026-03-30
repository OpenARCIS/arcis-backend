from arcis import Config
from pyrogram import Client
from .logger import LOGGER

user_plugins = dict(
    root="arcis/tg_user_plugins"
)


class UserSession(Client):
    """
    Pyrogram client logged in as the OWNER (user session).
    Listens to incoming DMs from external contacts.
    """
    def __init__(self):
        super().__init__(
            name="ARCIS-User-Sessionn",
            api_id=Config.TELEGRAM_API_ID,
            api_hash=Config.TELEGRAM_API_HASH,
            session_string=Config.TG_USER_SESSION,
            plugins=user_plugins,
            workdir=Config.WORK_DIR,
            workers=10,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        LOGGER.info(f"ARCIS - User Session : Started as @{me.username} ({me.first_name})")

    async def stop(self, *args):
        await super().stop()
        LOGGER.info("ARCIS - User Session : Stopped.")


# Singleton
_user_session: UserSession | None = None


def get_user_session() -> UserSession | None:
    global _user_session

    if _user_session is not None:
        return _user_session

    if Config.TELEGRAM_API_ID and Config.TELEGRAM_API_HASH and Config.TG_USER_SESSION:
        _user_session = UserSession()
    else:
        LOGGER.warning(
            "User Session not configured. "
            "Set TG_USER_SESSION in .env (run scripts/gen_session.py to generate it)."
        )

    return _user_session
