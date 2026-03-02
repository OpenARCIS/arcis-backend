from arcis.tgclient import get_tg_client
from arcis.config import Config
from arcis.logger import LOGGER


async def notify_action(summary: str) -> bool:
    """
    Send a notification message to the owner via Telegram.
    Gracefully degrades if the bot is not configured or sending fails.
    Returns True if the message was sent successfully.
    """
    bot = get_tg_client()

    if bot is None:
        LOGGER.debug("TG notify skipped: bot not configured.")
        return False

    chat_id = Config.ALLOWED_TG_USER_ID
    if not chat_id:
        LOGGER.debug("TG notify skipped: ALLOWED_TG_USER_ID not set.")
        return False

    try:
        await bot.send_message(chat_id=int(chat_id), text=summary)
        return True
    except Exception as e:
        LOGGER.warning(f"TG notification failed: {e}")
        return False
