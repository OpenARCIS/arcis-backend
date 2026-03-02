from pyrogram import Client, filters, enums
from pyrogram.types import Message

from arcis.config import Config
from arcis.logger import LOGGER
from arcis.core.workflow_manual.manual_flow import run_workflow
from arcis.utils.markdown_utils import escape_markdown

@Client.on_message(filters.text & filters.private)
async def handle_direct_message(client: Client, message: Message):
    if str(message.from_user.id) != Config.ALLOWED_TG_USER_ID:
        LOGGER.warning(f"Unauthorized access attempt from user ID: {message.from_user.id}")
        await message.reply_text("Unauthorized access.")
        return

    user_input = message.text
    thread_id = str(message.chat.id)

    await client.send_chat_action(chat_id=message.chat.id, action=enums.ChatAction.TYPING)

    try:
        final_state = await run_workflow(user_input=user_input, thread_id=thread_id)
        
        if isinstance(final_state, dict) and final_state.get("type") == "interrupt":
            response_text = final_state.get("response", "Workflow interrupted. Need more info.")
        else:
            response_text = final_state.get("final_response", "Workflow completed without a specific text response.")

    except Exception as e:
        LOGGER.error(f"Error executing workflow: {e}")
        response_text = "An error occurred while processing your request."

    try:
        safe_response = escape_markdown(response_text)
        await message.reply_text(safe_response, parse_mode=enums.ParseMode.MARKDOWN_V2)
    except Exception as e:
         LOGGER.error(f"Error sending message back with markdown, trying without: {e}")
         await message.reply_text(response_text)
