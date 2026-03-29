from arcis.tgclient import get_tg_client
from arcis.config import Config
from arcis.logger import LOGGER
from arcis.core.llm.short_memory import db_client


async def notify_incoming_dm(
    sender_name: str,
    original_text: str,
    draft_reply: str,
    original_chat_id: int,
    original_message_id: int,
) -> bool:
    """
    Notify the owner via the bot about an incoming external DM.
    Saves a tg_dm_mappings document so that when the owner replies,
    we know which chat/message to forward it to on the user session.

    Only called when TG_AUTO_SEND_REPLY != "true".
    """
    bot = get_tg_client()
    if bot is None:
        LOGGER.debug("DM notify skipped: bot not configured.")
        return False

    chat_id = Config.ALLOWED_TG_USER_ID
    if not chat_id:
        LOGGER.debug("DM notify skipped: ALLOWED_TG_USER_ID not set.")
        return False

    text = (
        f"💬 *{sender_name}* says:\n"
        f"_{original_text}_\n\n"
        f"📝 *Draft reply:*\n"
        f"{draft_reply}\n\n"
        f"↩️ _Reply to this message to send it — or just ignore._"
    )

    try:
        msg = await bot.send_message(chat_id=int(chat_id), text=text)

        # Save mapping so message_handler can route the reply back
        db = db_client["arcis_short_memory"]
        db["tg_dm_mappings"].insert_one({
            "bot_message_id": msg.id,
            "bot_chat_id": msg.chat.id,
            "original_chat_id": original_chat_id,
            "original_message_id": original_message_id,
            "sender_name": sender_name,
        })

        LOGGER.info(f"DM notification sent to owner (msg_id={msg.id}) for [{sender_name}].")
        return True
    except Exception as e:
        LOGGER.warning(f"DM notification failed: {e}")
        return False


async def notify_action_from_dm(
    sender_name: str,
    original_text: str,
    action_summary: str,
) -> bool:
    """
    Notify the owner after an ACTIONABLE DM was processed by auto_flow.
    """
    bot = get_tg_client()
    if bot is None:
        return False

    chat_id = Config.ALLOWED_TG_USER_ID
    if not chat_id:
        return False

    text = (
        f"🤖 *DM Auto-Handler* — [{sender_name}]\n\n"
        f"📩 Message: _{original_text}_\n\n"
        f"✅ Action taken:\n{action_summary}"
    )

    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except Exception as e:
        LOGGER.warning(f"DM action notify failed: {e}")
        return False
