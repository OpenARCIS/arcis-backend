import uuid

from pyrogram import Client, filters
from pyrogram.types import Message

from arcis.config import Config
from arcis.logger import LOGGER
from arcis.core.tg_dm.triage import classify_message
from arcis.core.tg_dm.draft_reply import generate_draft_reply, generate_ack_reply
from arcis.tg_plugins.dm_notify import notify_incoming_dm, notify_action_from_dm


async def _run_tg_dm_flow(text: str, sender_name: str) -> str:
    """
    Feed an ACTIONABLE DM into the dedicated TG DM pipeline.
    Returns a plain-text summary of what was done.
    """
    from arcis.core.workflow_tg_dm.tg_dm_flow import _compile_tg_dm_app
    from arcis.models.agents.state import AgentState

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    user_input = (
        f"Sender: {sender_name}\n"
        f"Message: {text}"
    )

    initial_state: AgentState = {
        "input": user_input,
        "plan": [],
        "context": {"source": "telegram_dm", "sender": sender_name},
        "last_tool_output": "",
        "final_response": "",
        "current_step_index": 0,
        "thread_id": thread_id,
        "next_node": None,
        "workflow_status": None
    }

    app = _compile_tg_dm_app()
    await app.ainvoke(initial_state, config)
    
    # We could check for interrupts here if we want full interrupt support
    # For now, extract the final response or the completed steps
    
    state_after = await app.aget_state(config)
    final = state_after.values

    # Prefer the replanner's final conversational response
    if final.get("final_response") and final["final_response"] != "Task handled.":
        return final["final_response"]

    completed = [s for s in final.get("plan", []) if s.get("status") == "completed"]
    if completed:
        steps = "\n".join(f"  • {s['description']}" for s in completed)
        return steps

    return final.get("final_response", "Request processed.")


@Client.on_message(filters.private & ~filters.me & ~filters.bot)
async def handle_incoming_dm(client: Client, message: Message):
    """
    Handles DMs sent to the owner's personal Telegram account by external contacts.
    This runs on the USER SESSION client, not the bot.
    """
    if not message.text:
        return  # Skip non-text messages (stickers, media, etc.)

    sender = message.from_user
    sender_name = sender.first_name or sender.username or str(sender.id)
    text = message.text.strip()

    LOGGER.info(f"[User Session] Incoming DM from {sender_name} (id={sender.id}): {text[:80]}")

    # ── Step 1: Triage ────────────────────────────────────────────────────────
    triage = await classify_message(text, sender_name)

    # ── Step 2: Route ─────────────────────────────────────────────────────────
    if triage.type == "IGNORE":
        LOGGER.info(f"[User Session] Message from [{sender_name}] classified as IGNORE — skipping.")
        return

    if triage.type == "SOCIAL":
        draft = await generate_draft_reply(text, sender_name)

        if Config.TG_AUTO_SEND_REPLY == "true":
            # Send the draft directly from the user session
            try:
                await message.reply(draft)
                LOGGER.info(f"[User Session] Auto-sent reply to [{sender_name}].")
            except Exception as e:
                LOGGER.error(f"[User Session] Failed to auto-send reply: {e}")
        else:
            # Notify the owner via bot and wait for their approval reply
            await notify_incoming_dm(
                sender_name=sender_name,
                original_text=text,
                draft_reply=draft,
                original_chat_id=message.chat.id,
                original_message_id=message.id,
            )

    elif triage.type == "ACTIONABLE":
        LOGGER.info(f"[User Session] Routing ACTIONABLE message from [{sender_name}] to TG DM flow.")

        try:
            action_summary = await _run_tg_dm_flow(text, sender_name)
        except Exception as e:
            LOGGER.error(f"[User Session] TG DM flow error for DM: {e}")
            action_summary = "Could not process request."

        # Always send an acknowledgment back to the sender
        ack = await generate_ack_reply(text, action_summary)
        try:
            await message.reply(ack)
            LOGGER.info(f"[User Session] Sent ACK to [{sender_name}]: {ack[:60]}")
        except Exception as e:
            LOGGER.error(f"[User Session] Failed to send ACK: {e}")

        # Notify owner what was done
        await notify_action_from_dm(
            sender_name=sender_name,
            original_text=text,
            action_summary=action_summary,
        )
