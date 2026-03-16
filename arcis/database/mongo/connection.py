from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from arcis import Config

# easy references
COLLECTIONS = {
    'users': 'users',
    'processed_emails': 'processed_emails',
    'settings': 'settings',
    'token_usage': 'token_usage',
    'user_emotions': 'user_emotions',
    'onboarding_sessions': 'onboarding_sessions',
    'scheduled_jobs': 'scheduled_jobs',
    'apscheduler_jobs': 'apscheduler_jobs',
    'notifications': 'notifications',
}

class Database:
    client: AsyncIOMotorClient
    db: AsyncIOMotorDatabase

    def __init__(self):
        self.mongodb_url = Config.DATABASE_URL
        self.database_name = Config.DATABASE_NAME
        self.client = None
        self.db = None
        
    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongodb_url)
        self.db = self.client[self.database_name]
        await self._create_indexes()
        
    async def disconnect(self):
        if self.client:
            self.client.close()

    async def _create_indexes(self):
        await self.db[COLLECTIONS['users']].create_index([("user_id", 1)])
        await self.db[COLLECTIONS['processed_emails']].create_index(
            [("email_id", 1)], 
            unique=True
        )
        await self.db[COLLECTIONS['scheduled_jobs']].create_index(
            [("status", 1), ("trigger_at", 1)]
        )
        await self.db[COLLECTIONS['scheduled_jobs']].create_index(
            [("status", 1), ("prefetch_at", 1)]
        )
        await self.db[COLLECTIONS['notifications']].create_index(
            [("created_at", 1)],
            expireAfterSeconds=30 * 24 * 3600  # auto-delete after 30 days
        )
        await self.db[COLLECTIONS['notifications']].create_index(
            [("read", 1), ("created_at", -1)]
        )


mongo = Database()