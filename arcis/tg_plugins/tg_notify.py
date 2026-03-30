from arcis.tgclient import get_tg_client
from arcis.config import Config
from arcis.logger import LOGGER
from arcis.core.llm.short_memory import db_client


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


async def notify_interrupt(interrupt_id: str, summary: str) -> bool:
    """
    Send an interrupt notification and save the message ID mapping.
    Allows the user to reply to this specific message to resolve the interrupt.
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
        msg = await bot.send_message(chat_id=int(chat_id), text=summary)
        
        # Save mapping: TG message ID -> Auto Flow interrupt ID
        db = db_client['arcis_short_memory']
        mapping_col = db['tg_interrupt_mappings']
        mapping_col.insert_one({
            "message_id": msg.id,
            "chat_id": msg.chat.id,
            "interrupt_id": interrupt_id,
        })
        
        LOGGER.info(f"TG interrupt notification sent successfully (Msg ID: {msg.id}).")
        return True
    except Exception as e:
        LOGGER.warning(f"TG interrupt notification failed: {e}")
        return False


async def notify_with_file(file_path: str, caption: str = "") -> bool:
    """
    Send a document/file to the owner via Telegram.
    Returns True if the file was sent successfully.
    """
    bot = get_tg_client()

    if bot is None:
        LOGGER.debug("TG file notify skipped: bot not configured.")
        return False

    chat_id = Config.ALLOWED_TG_USER_ID
    if not chat_id:
        LOGGER.debug("TG file notify skipped: ALLOWED_TG_USER_ID not set.")
        return False

    try:
        await bot.send_document(
            chat_id=int(chat_id),
            document=file_path,
            caption=caption or None
        )
        LOGGER.info(f"TG file sent: {file_path}")
        return True
    except Exception as e:
        LOGGER.warning(f"TG file send failed ({file_path}): {e}")
        return False


async def notify_with_files(file_paths: list, caption: str = "") -> bool:
    """
    Send multiple documents to the owner via Telegram.
    Returns True if ALL files were sent successfully.
    """
    if not file_paths:
        return True

    all_ok = True
    for path in file_paths:
        ok = await notify_with_file(path, caption)
        if not ok:
            all_ok = False
    return all_ok
