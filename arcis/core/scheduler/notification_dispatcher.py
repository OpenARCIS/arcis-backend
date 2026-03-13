from datetime import datetime
from typing import Optional

from arcis import Config
from arcis.tg_plugins.tg_notify import notify_action
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER


class NotificationDispatcher:
    """
    Routes job notifications based on the global NOTIFICATION_CHANNEL config.
    Channels: "telegram", "web", "both"
    """

    @property
    def channel(self) -> str:
        return getattr(Config, "NOTIFICATION_CHANNEL", "both").lower()

    @property
    def _collection(self):
        return mongo.db[COLLECTIONS['notifications']]

    async def send(
        self,
        title: str,
        message: str,
        job_id: Optional[str] = None,
        level: str = "info",
    ):
        """
        Dispatch a notification to the configured channel(s).

        Args:
            title:   Short heading (e.g. "Reminder: Stand-up meeting")
            message: Full notification body
            job_id:  Optional linked scheduled job ID
            level:   "info" | "success" | "error"
        """
        channel = self.channel

        if channel in ("telegram", "both"):
            await self._send_telegram(title, message)

        if channel in ("web", "both"):
            await self._store_web(title, message, job_id, level)

    # ---- private helpers ----

    async def _send_telegram(self, title: str, message: str):
        """Send via Telegram, gracefully degrade on failure."""
        try:
            text = f"{title}\n{message}" if message != title else title
            await notify_action(text)
        except Exception as e:
            LOGGER.warning(f"NOTIFY: Telegram send failed (non-fatal): {e}")

    async def _store_web(
        self,
        title: str,
        message: str,
        job_id: Optional[str] = None,
        level: str = "info",
    ):
        """Insert a notification document for the web UI to consume."""
        try:
            doc = {
                "title": title,
                "message": message,
                "job_id": job_id,
                "level": level,
                "read": False,
                "created_at": datetime.now(),
            }
            await self._collection.insert_one(doc)
        except Exception as e:
            LOGGER.warning(f"NOTIFY: Web notification store failed: {e}")


# Singleton
dispatcher = NotificationDispatcher()
