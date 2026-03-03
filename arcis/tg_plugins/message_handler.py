from pyrogram import Client, filters, enums
from pyrogram.types import Message

from arcis.config import Config
from arcis.logger import LOGGER
from arcis.core.workflow_manual.manual_flow import run_workflow
from arcis.core.workflow_auto.auto_flow import resolve_interrupt
from arcis.core.llm.short_memory import db_client
from arcis.core.stt.stt_manager import transcribe_audio


@Client.on_message(filters.text & filters.private)
async def handle_direct_message(client: Client, message: Message):
    if str(message.from_user.id) != Config.ALLOWED_TG_USER_ID:
        LOGGER.warning(f"Unauthorized access attempt from user ID: {message.from_user.id} vs allowed {Config.ALLOWED_TG_USER_ID}")
        await message.reply_text("Unauthorized access.")
        return

    user_input = message.text
    thread_id = str(message.chat.id)

    await client.send_chat_action(chat_id=message.chat.id, action=enums.ChatAction.TYPING)

    # Check if this is a reply to an auto-flow interrupt
    if message.reply_to_message_id:
        db = db_client['arcis_short_memory']
        mapping = db['tg_interrupt_mappings'].find_one({
            "message_id": message.reply_to_message_id,
            "chat_id": message.chat.id
        })
        
        if mapping:
            LOGGER.info(f"Detected reply to auto flow interrupt: {mapping['interrupt_id']}")
            try:
                result = await resolve_interrupt(mapping['interrupt_id'], user_input)
                # Cleanup the mapping so it isn't used again
                db['tg_interrupt_mappings'].delete_one({"_id": mapping['_id']})
                
                if result.get("status") == "interrupted_again":
                    response_text = result.get("message", "More information needed.")
                else:
                    status_text = "✅ Task completed." if result.get("workflow_status") == "FINISHED" else "Resumed workflow."
                    response_text = f"{status_text}\n\n📝 {result.get('message', '')}"
            except Exception as e:
                LOGGER.error(f"Error resolving interrupt: {e}")
                response_text = f"An error occurred resolving the interrupt: {e}"
                
            try:
                await message.reply_text(response_text, parse_mode=enums.ParseMode.MARKDOWN)
            except Exception as e:
                LOGGER.error(f"Error sending message back with markdown, trying without: {e}")
                await message.reply_text(response_text)
            return

    # Normal manual flow processing
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
        await message.reply_text(response_text, parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
         LOGGER.error(f"Error sending message back with markdown, trying without: {e}")
         await message.reply_text(response_text)


@Client.on_message(filters.voice & filters.private)
async def handle_voice_message(client: Client, message: Message):
    """Handle incoming voice messages — transcribe via Groq then run workflow."""
    if str(message.from_user.id) != Config.ALLOWED_TG_USER_ID:
        LOGGER.warning(f"Unauthorized voice access attempt from user ID: {message.from_user.id}")
        await message.reply_text("Unauthorized access.")
        return

    thread_id = str(message.chat.id)

    await client.send_chat_action(chat_id=message.chat.id, action=enums.ChatAction.TYPING)

    # 1. Download voice note in-memory
    try:
        voice_file = await message.download(in_memory=True)
        audio_bytes = bytes(voice_file.getbuffer())
    except Exception as e:
        LOGGER.error(f"Error downloading voice message: {e}")
        await message.reply_text("Failed to download voice message.")
        return

    # 2. Transcribe (async, non-blocking)
    try:
        transcribed_text = await transcribe_audio(audio_bytes, filename="voice.ogg")
    except Exception as e:
        LOGGER.error(f"Error transcribing voice: {e}")
        await message.reply_text("Failed to transcribe voice message.")
        return

    if not transcribed_text:
        await message.reply_text("Could not understand the voice message. Please try again.")
        return

    # 3. Run the workflow with the transcribed text
    try:
        final_state = await run_workflow(user_input=transcribed_text, thread_id=thread_id)

        if isinstance(final_state, dict) and final_state.get("type") == "interrupt":
            ai_response = final_state.get("response", "Workflow interrupted. Need more info.")
        else:
            ai_response = final_state.get("final_response", "Workflow completed without a specific text response.")

    except Exception as e:
        LOGGER.error(f"Error executing workflow from voice: {e}")
        ai_response = "An error occurred while processing your request."

    # 4. Reply with transcription + AI response
    response_text = f'🎤 *"{transcribed_text}"*\n\n{ai_response}'

    try:
        await message.reply_text(response_text, parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.error(f"Error sending voice reply with markdown, trying without: {e}")
        await message.reply_text(f'🎤 "{transcribed_text}"\n\n{ai_response}')