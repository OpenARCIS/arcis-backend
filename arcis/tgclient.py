from arcis import Config

from pyrogram import Client

from .logger import LOGGER

plugins = dict(
    root="arcis/tg_plugins"
)

class Bot(Client):
    def __init__(self):
        super().__init__(
            "ARCIS-Telegram-Client",
            api_id=Config.TELEGRAM_API_ID,
            api_hash=Config.TELEGRAM_API_HASH,
            bot_token=Config.TG_BOT_TOKEN,
            plugins=plugins,
            workdir=Config.WORK_DIR,
            workers=100
        )

    async def start(self):
        await super().start()
        LOGGER.info("ARCIS - Telegram Client : Started Successfully")

    async def stop(self, *args):
        await super().stop()
        LOGGER.info('ARCIS - Telegram Client : Exited Successfully ! Bye..........')

tg_arcis = None

def get_tg_client():
    global tg_arcis
    if tg_arcis is not None:
        return tg_arcis
        
    if Config.TELEGRAM_API_ID and Config.TELEGRAM_API_HASH and Config.TG_BOT_TOKEN:
        tg_arcis = Bot()
    else:
        LOGGER.warning("Telegram Client configuration missing. Telegram bot will not be initialized.")
        
    return tg_arcis
